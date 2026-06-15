import io
import json
from datetime import date, datetime, timedelta

import disnake
from disnake.ext import commands, tasks
from firebase_admin import firestore

from database import db
from services.roster_engine import build_update_draft
from services.roster_exporter import export_csv, export_json, export_text, template_csv
from services.roster_parser import (
    REQUIRED_COLUMNS,
    classify_ta_expiry,
    parse_roster_csv,
    parse_update_csv,
    parse_update_text,
    summarize_entries,
    validate_entries,
)


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)
DEFAULT_ROSTER_ID = "main"
VALID_ALT_FILTERS = ["all", "pa", "ta", "expired", "expiring"]


def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))


def roster_ref(guild_id, roster_id=DEFAULT_ROSTER_ID):
    return guild_ref(guild_id).collection("legion_rosters").document(roster_id)


def draft_ref(guild_id, roster_id, draft_id):
    return roster_ref(guild_id, roster_id).collection("drafts").document(draft_id)


def today_iso():
    return date.today().isoformat()


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


async def attachment_text(file):
    raw = await file.read()
    return raw.decode("utf-8-sig")


def make_file(content, filename, content_type="text/plain"):
    return disnake.File(io.BytesIO(content.encode("utf-8")), filename=filename)


def chunk_lines(lines, limit=3500):
    text = "\n".join(lines)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n... truncated"


def is_admin(inter):
    permissions = getattr(inter.author, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def summary_embed(title, summary, errors=None, warnings=None):
    embed = disnake.Embed(title=title, color=BRAND_COLOR)
    embed.add_field(
        name="Counts",
        value=(
            f"Total: **{summary['total']}**\n"
            f"T1: **{summary['T1']}** | T2: **{summary['T2']}** | "
            f"T3: **{summary['T3']}** | T4: **{summary['T4']}**\n"
            f"PA: **{summary['PA']}** | TA: **{summary['TA']}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Temporary Alts",
        value=(
            f"Missing expiry fixed: **{summary['fixed_expiry_count']}**\n"
            f"Expired: **{summary['expired_ta_count']}**\n"
            f"Expiring soon: **{summary['expiring_ta_count']}**"
        ),
        inline=False,
    )
    if errors:
        embed.add_field(name="Errors", value=chunk_lines([f"- {item}" for item in errors], 1000), inline=False)
    if warnings:
        embed.add_field(name="Warnings", value=chunk_lines([f"- {item}" for item in warnings], 1000), inline=False)
    return embed


def draft_embed(draft):
    embed = disnake.Embed(title="Roster Draft Preview", color=BRAND_COLOR)
    sections = [
        ("Forced changes", draft.get("forced_changes", [])),
        ("Cascade changes", draft.get("cascade_changes", [])),
        ("Alt corrections", draft.get("alt_corrections", [])),
        ("Benched/Removed", draft.get("benched", [])),
        ("Capacity", draft.get("capacity", [])),
        ("Conflicts", draft.get("conflicts", [])),
        ("Warnings", draft.get("validation_warnings", [])),
    ]
    for name, values in sections:
        if values:
            embed.add_field(name=name, value=chunk_lines([f"- {item}" for item in values], 1000), inline=False)
    embed.add_field(
        name="Totals",
        value=(
            f"Unchanged: **{draft.get('unchanged_count', 0)}**\n"
            f"Moved: **{draft.get('moved_count', 0)}**\n"
            f"Added: **{draft.get('added_count', 0)}**\n"
            f"Benched/Removed: **{draft.get('removed_count', 0)}**"
        ),
        inline=False,
    )
    if draft.get("validation_errors"):
        embed.add_field(
            name="Validation Errors",
            value=chunk_lines([f"- {item}" for item in draft["validation_errors"]], 1000),
            inline=False,
        )
    return embed


class StoredDraftView(disnake.ui.View):
    def __init__(self, guild_id, roster_id, draft_id, allow_apply=True):
        super().__init__(timeout=900)
        self.guild_id = str(guild_id)
        self.roster_id = roster_id
        self.draft_id = draft_id
        if not allow_apply:
            self.apply.disabled = True

    @disnake.ui.button(label="Apply Draft", style=disnake.ButtonStyle.success)
    async def apply(self, button, inter):
        await inter.response.defer(ephemeral=True)
        if not is_admin(inter):
            return await inter.edit_original_message(content="Only server administrators can apply roster drafts.")
        doc = draft_ref(self.guild_id, self.roster_id, self.draft_id).get()
        if not doc.exists:
            return await inter.edit_original_message(content="Draft was not found or already cleared.")

        draft = doc.to_dict() or {}
        if draft.get("validation_errors"):
            return await inter.edit_original_message(content="This draft has validation errors and cannot be applied.")
        if draft.get("conflicts") and draft.get("mode") == "ask":
            return await inter.edit_original_message(content="This draft has conflicts. Re-run with MODE:auto or resolve them first.")

        await apply_entries(self.guild_id, self.roster_id, draft.get("entries", []), draft)
        doc.reference.set({"status": "applied", "applied_at": firestore.SERVER_TIMESTAMP}, merge=True)
        await inter.edit_original_message(content="Draft applied.")

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.danger)
    async def cancel(self, button, inter):
        await inter.response.defer(ephemeral=True)
        draft_ref(self.guild_id, self.roster_id, self.draft_id).set(
            {"status": "cancelled", "cancelled_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
        await inter.edit_original_message(content="Draft cancelled.")

    @disnake.ui.button(label="Export Draft", style=disnake.ButtonStyle.secondary)
    async def export(self, button, inter):
        await inter.response.defer(ephemeral=True)
        doc = draft_ref(self.guild_id, self.roster_id, self.draft_id).get()
        if not doc.exists:
            return await inter.edit_original_message(content="Draft was not found.")
        entries = (doc.to_dict() or {}).get("entries", [])
        await inter.edit_original_message(
            content="Draft CSV export:",
            file=make_file(export_csv(entries), "legion_roster_draft.csv", "text/csv"),
        )


async def load_roster(guild_id, roster_id=DEFAULT_ROSTER_ID):
    ref = roster_ref(guild_id, roster_id)
    doc = ref.get()
    metadata = doc.to_dict() if doc.exists else None
    entries = [snap.to_dict() for snap in ref.collection("entries").stream()]
    entries.sort(key=lambda item: int(item["serial"]))
    return metadata, entries


async def apply_entries(guild_id, roster_id, entries, draft=None):
    ref = roster_ref(guild_id, roster_id)
    batch = db.batch()
    for snap in ref.collection("entries").stream():
        batch.delete(snap.reference)
    for entry in entries:
        clean = {
            "serial": int(entry["serial"]),
            "name": entry["name"],
            "seat_tier": entry["seat_tier"],
            "parent_serial": entry.get("parent_serial"),
            "type": entry.get("type", ""),
            "expiry": entry.get("expiry"),
        }
        batch.set(ref.collection("entries").document(str(clean["serial"])), clean)
    metadata = (draft or {}).get("metadata", {})
    roster_update = {
        "name": metadata.get("name", "Main Legion"),
        "status": "active",
        "default_ta_expiry_days": metadata.get("default_ta_expiry_days", 30),
        "ta_warning_days": metadata.get("ta_warning_days", 1),
        "expiry_channel_id": metadata.get("expiry_channel_id"),
        "updated_at": firestore.SERVER_TIMESTAMP,
        "latest_added_names": draft.get("added", []) if draft else [],
    }
    if metadata.get("created_by"):
        roster_update["created_by"] = metadata["created_by"]
    batch.set(ref, roster_update, merge=True)
    batch.commit()


class Roster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.expiry_alert_loop.start()

    def cog_unload(self):
        self.expiry_alert_loop.cancel()

    @commands.slash_command(name="roster_template", description="Get the Legion roster CSV template")
    async def roster_template(self, inter):
        await inter.response.defer(ephemeral=True)
        explanation = (
            "CSV columns: `serial,name,seat_tier,parent_serial,type,expiry`\n"
            "Blank `type` means normal account. `PA` means permanent alt. `TA` means temporary alt.\n"
            "`expiry` uses YYYY-MM-DD and is only needed for TA."
        )
        await inter.edit_original_message(
            content=explanation,
            file=make_file(template_csv(), "legion_roster_template.csv", "text/csv"),
        )

    @commands.slash_command(name="roster_import", description="Import a full Legion roster CSV")
    @commands.has_permissions(administrator=True)
    async def roster_import(
        self,
        inter,
        file: disnake.Attachment,
        roster_name: str = commands.Param(default="Main Legion"),
        replace_existing: bool = commands.Param(default=False),
    ):
        await inter.response.defer(ephemeral=True)
        metadata, existing = await load_roster(inter.guild.id)
        if existing and not replace_existing:
            return await inter.edit_original_message(
                content="A roster already exists. Re-run with `replace_existing:True` to create an apply preview."
            )

        default_days = (metadata or {}).get("default_ta_expiry_days", 30)
        warning_days = (metadata or {}).get("ta_warning_days", 1)
        entries, errors, warnings, fixed = parse_roster_csv(await attachment_text(file), default_days)
        summary = summarize_entries(entries, fixed, ta_warning_days=warning_days, errors=errors, warnings=warnings)
        embed = summary_embed("Roster Import Preview", summary, errors, warnings)
        if errors:
            return await inter.edit_original_message(embed=embed)

        draft_id = f"import_{int(datetime.utcnow().timestamp())}_{inter.author.id}"
        draft_ref(inter.guild.id, DEFAULT_ROSTER_ID, draft_id).set(
            {
                "kind": "import",
                "status": "preview",
                "entries": entries,
                "added": [entry["name"] for entry in entries if entry.get("type") == "TA"],
                "metadata": {
                    "name": roster_name,
                    "default_ta_expiry_days": default_days,
                    "ta_warning_days": warning_days,
                    "expiry_channel_id": (metadata or {}).get("expiry_channel_id"),
                    "created_by": str(inter.author.id),
                },
                "summary": summary,
                "created_by": str(inter.author.id),
                "created_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.edit_original_message(
            embed=embed,
            view=StoredDraftView(inter.guild.id, DEFAULT_ROSTER_ID, draft_id, allow_apply=True),
        )

    @commands.slash_command(name="roster_validate", description="Validate the current Legion roster")
    async def roster_validate(self, inter):
        await inter.response.defer(ephemeral=True)
        metadata, entries = await load_roster(inter.guild.id)
        if not metadata or not entries:
            return await inter.edit_original_message(content="No active roster found. Use `/roster_import` first.")
        clean, errors, warnings = validate_entries(entries, ta_warning_days=metadata.get("ta_warning_days", 1))
        summary = summarize_entries(clean, ta_warning_days=metadata.get("ta_warning_days", 1), errors=errors, warnings=warnings)
        await inter.edit_original_message(embed=summary_embed("Roster Validation", summary, errors, warnings))

    @commands.slash_command(name="roster_export", description="Export the current Legion roster")
    async def roster_export(
        self,
        inter,
        format: str = commands.Param(choices=["csv", "json", "text"]),
    ):
        await inter.response.defer(ephemeral=True)
        metadata, entries = await load_roster(inter.guild.id)
        if not entries:
            return await inter.edit_original_message(content="No active roster found.")

        if format == "csv":
            return await inter.edit_original_message(
                content="Roster CSV export:",
                file=make_file(export_csv(entries), "legion_roster.csv", "text/csv"),
            )
        if format == "json":
            return await inter.edit_original_message(
                content="Roster JSON export:",
                file=make_file(export_json(metadata, entries), "legion_roster.json", "application/json"),
            )

        text = export_text(entries)
        if len(text) > 1800:
            return await inter.edit_original_message(
                content="Roster text export:",
                file=make_file(text, "legion_roster.txt"),
            )
        await inter.edit_original_message(content=f"```text\n{text}\n```")

    @commands.slash_command(name="roster_update_positions", description="Create a weekly Legion roster update draft")
    @commands.has_permissions(administrator=True)
    async def roster_update_positions(
        self,
        inter,
        file: disnake.Attachment = commands.Param(default=None),
        text: str = commands.Param(default=None, description="Paste T1/T2/T3/T4 update text"),
        mode: str = commands.Param(default="ask", choices=["ask", "auto", "random"], description="How to handle automatic moves"),
    ):
        await inter.response.defer(ephemeral=True)
        metadata, entries = await load_roster(inter.guild.id)
        if not entries:
            return await inter.edit_original_message(content="No active roster found. Use `/roster_import` first.")
        if not file and not text:
            return await inter.edit_original_message(content="Provide either a CSV file or pasted roster update text.")

        if file:
            update_request, errors, warnings = parse_update_csv(
                await attachment_text(file),
                metadata.get("default_ta_expiry_days", 30),
            )
        else:
            update_request = parse_update_text(text)
            errors, warnings = [], []
        update_request["mode"] = mode

        if errors:
            return await inter.edit_original_message(content=chunk_lines([f"- {item}" for item in errors]))

        draft = build_update_draft(
            entries,
            update_request,
            default_ta_expiry_days=metadata.get("default_ta_expiry_days", 30),
            ta_warning_days=metadata.get("ta_warning_days", 1),
        )
        draft["validation_warnings"] = warnings + draft.get("validation_warnings", [])
        draft_id = f"update_{int(datetime.utcnow().timestamp())}_{inter.author.id}"
        allow_apply = not draft.get("validation_errors") and not (draft.get("conflicts") and draft.get("mode") == "ask")
        draft_ref(inter.guild.id, DEFAULT_ROSTER_ID, draft_id).set(
            {
                **draft,
                "kind": "weekly_update",
                "status": "preview",
                "metadata": {
                    "name": metadata.get("name", "Main Legion"),
                    "default_ta_expiry_days": metadata.get("default_ta_expiry_days", 30),
                    "ta_warning_days": metadata.get("ta_warning_days", 1),
                    "expiry_channel_id": metadata.get("expiry_channel_id"),
                    "created_by": metadata.get("created_by", str(inter.author.id)),
                },
                "created_by": str(inter.author.id),
                "created_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.edit_original_message(
            embed=draft_embed(draft),
            view=StoredDraftView(inter.guild.id, DEFAULT_ROSTER_ID, draft_id, allow_apply=allow_apply),
        )

    @commands.slash_command(name="roster_alts", description="Show roster PA/TA entries")
    async def roster_alts(
        self,
        inter,
        filter: str = commands.Param(default="all", choices=VALID_ALT_FILTERS),
    ):
        await inter.response.defer(ephemeral=True)
        metadata, entries = await load_roster(inter.guild.id)
        if not entries:
            return await inter.edit_original_message(content="No active roster found.")
        expired, expiring = classify_ta_expiry(entries, ta_warning_days=(metadata or {}).get("ta_warning_days", 1))
        expired_names = {entry["name"] for entry in expired}
        expiring_names = {entry["name"] for entry in expiring}
        by_serial = {int(entry["serial"]): entry for entry in entries}

        rows = []
        for entry in entries:
            if entry.get("type") not in {"PA", "TA"}:
                continue
            status = "active"
            if entry["name"] in expired_names:
                status = "expired"
            elif entry["name"] in expiring_names:
                status = "expiring soon"
            if filter == "pa" and entry.get("type") != "PA":
                continue
            if filter == "ta" and entry.get("type") != "TA":
                continue
            if filter == "expired" and status != "expired":
                continue
            if filter == "expiring" and status != "expiring soon":
                continue
            parent = by_serial.get(int(entry["parent_serial"])) if entry.get("parent_serial") else None
            rows.append(
                f"{entry['name']} | #{entry['serial']} | {entry['seat_tier']} | "
                f"parent: {parent['name'] if parent else entry.get('parent_serial')} | "
                f"{entry.get('type', '')} | expiry: {entry.get('expiry') or '-'} | {status}"
            )

        if not rows:
            return await inter.edit_original_message(content="No matching roster alts found.")
        output = "\n".join(rows)
        if len(output) > 1800:
            return await inter.edit_original_message(content="Roster alts export:", file=make_file(output, "roster_alts.txt"))
        await inter.edit_original_message(content=f"```text\n{output}\n```")

    @commands.slash_command(name="roster_update_expiry", description="Batch update temporary alt expiry dates")
    @commands.has_permissions(administrator=True)
    async def roster_update_expiry(
        self,
        inter,
        mode: str = commands.Param(choices=["all_ta", "new_ta", "specific"]),
        names: str = commands.Param(default=None, description="Comma-separated names for specific mode"),
        days: int = commands.Param(default=None),
        expiry: str = commands.Param(default=None, description="YYYY-MM-DD"),
    ):
        await inter.response.defer(ephemeral=True)
        metadata, entries = await load_roster(inter.guild.id)
        if not entries:
            return await inter.edit_original_message(content="No active roster found.")
        if days is None and expiry is None:
            return await inter.edit_original_message(content="Provide either `days` or `expiry`.")
        if expiry:
            try:
                new_expiry = parse_date(expiry).isoformat()
            except ValueError:
                return await inter.edit_original_message(content="Expiry must use YYYY-MM-DD.")
        else:
            new_expiry = (date.today() + timedelta(days=days)).isoformat()

        target_names = None
        if mode == "specific":
            if not names:
                return await inter.edit_original_message(content="Specific mode requires `names`.")
            target_names = {item.strip().lower() for item in names.split(",") if item.strip()}
        elif mode == "new_ta":
            latest = set(name.lower() for name in (metadata or {}).get("latest_added_names", []))
            if not latest:
                return await inter.edit_original_message(content="No latest added TA metadata is available yet.")
            target_names = latest

        updated = []
        batch = db.batch()
        ref = roster_ref(inter.guild.id)
        for entry in entries:
            if entry.get("type") != "TA":
                continue
            if target_names is not None and entry["name"].lower() not in target_names:
                continue
            entry["expiry"] = new_expiry
            batch.set(ref.collection("entries").document(str(entry["serial"])), entry, merge=True)
            updated.append(entry["name"])
        if updated:
            batch.set(ref, {"updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            batch.commit()
        await inter.edit_original_message(content=chunk_lines([f"Updated {name} -> {new_expiry}" for name in updated]) or "No TAs matched.")

    @commands.slash_command(name="roster_config", description="Configure Legion roster expiry settings")
    @commands.has_permissions(administrator=True)
    async def roster_config(
        self,
        inter,
        default_ta_expiry_days: int = commands.Param(default=None),
        ta_warning_days: int = commands.Param(default=None),
        expiry_channel: disnake.TextChannel = commands.Param(default=None),
    ):
        await inter.response.defer(ephemeral=True)
        updates = {"updated_at": firestore.SERVER_TIMESTAMP}
        if default_ta_expiry_days is not None:
            updates["default_ta_expiry_days"] = max(1, default_ta_expiry_days)
        if ta_warning_days is not None:
            updates["ta_warning_days"] = max(0, ta_warning_days)
        if expiry_channel is not None:
            updates["expiry_channel_id"] = expiry_channel.id
        updates.setdefault("name", "Main Legion")
        updates.setdefault("status", "active")
        roster_ref(inter.guild.id).set(updates, merge=True)
        await inter.edit_original_message(content="Roster config updated.")

    @tasks.loop(hours=24)
    async def expiry_alert_loop(self):
        today = date.today()
        for guild_doc in db.collection("guilds").stream():
            for roster_doc in guild_doc.reference.collection("legion_rosters").where("status", "==", "active").stream():
                metadata = roster_doc.to_dict() or {}
                channel_id = metadata.get("expiry_channel_id")
                if not channel_id:
                    continue
                if metadata.get("last_expiry_alert_date") == today.isoformat():
                    continue
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    continue
                entries = [snap.to_dict() for snap in roster_doc.reference.collection("entries").stream()]
                expired, expiring = classify_ta_expiry(entries, today=today, ta_warning_days=metadata.get("ta_warning_days", 1))
                if not expired and not expiring:
                    roster_doc.reference.set({"last_expiry_alert_date": today.isoformat()}, merge=True)
                    continue

                lines = ["Temporary Alt Expiry Warning", ""]
                if expiring:
                    lines.append("Expiring soon:")
                    lines.extend([f"- {entry['name']} | {entry['seat_tier']} | expires {entry['expiry']}" for entry in expiring])
                    lines.append("")
                if expired:
                    lines.append("Expired:")
                    for entry in expired:
                        days = (today - parse_date(entry["expiry"])).days
                        lines.append(f"- {entry['name']} | expired {days} days ago")
                    lines.append("")
                lines.append("Use /roster_alts filter:expired or /roster_update_expiry to manage them.")
                await channel.send(chunk_lines(lines, 1900))
                roster_doc.reference.set({"last_expiry_alert_date": today.isoformat()}, merge=True)

    @expiry_alert_loop.before_loop
    async def before_expiry_alert_loop(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Roster(bot))
