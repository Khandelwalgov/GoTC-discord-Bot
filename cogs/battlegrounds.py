import re
from datetime import datetime, time, timedelta, timezone

import disnake
import pytz
from disnake.ext import commands, tasks
from firebase_admin import firestore

from database import db
from cogs.weekend import BRAND_COLOR, find_role_by_key


BG_TYPES = {
    "Titans of the North": {
        "role_key": "bg_titans",
        "short": "Titans",
    },
    "The Great Ranging": {
        "role_key": "bg_ranging",
        "short": "Great Ranging",
    },
}
REMINDER_MINUTES = [60, 30, 15, 0]


def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))


def event_ref(guild_id, event_id):
    return guild_ref(guild_id).collection("battleground_events").document(str(event_id))


async def get_user_tz(guild_id, user_id):
    doc = (
        guild_ref(guild_id)
        .collection("users")
        .document(str(user_id))
        .get()
    )
    if doc.exists:
        return doc.to_dict().get("timezone", "UTC")
    return "UTC"


def parse_event_time(raw_time, timezone_name):
    clean = raw_time.strip().lower().replace(" ", "")
    parsed = None

    for fmt in ("%I:%M%p", "%I%p"):
        try:
            parsed = datetime.strptime(clean, fmt).time()
            break
        except ValueError:
            pass

    if not parsed:
        digits = re.sub(r"[^0-9]", "", clean)
        if len(digits) in (3, 4):
            digits = digits.zfill(4)
            hour, minute = int(digits[:2]), int(digits[2:])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                parsed = time(hour, minute)

    if not parsed:
        raise ValueError("Use a time like `8pm`, `8:30pm`, or `2030`.")

    user_tz = pytz.timezone(timezone_name)
    now = datetime.now(user_tz)
    local_dt = user_tz.localize(datetime.combine(now.date(), parsed))
    if local_dt <= now:
        local_dt += timedelta(days=1)
    return local_dt.astimezone(timezone.utc)


def build_event_embed(event_data):
    bg_type = event_data.get("type", "Battleground")
    starts_at = event_data.get("starts_at")
    participants = event_data.get("participants", []) or []
    unix = int(starts_at.timestamp()) if hasattr(starts_at, "timestamp") else int(event_data.get("starts_at_unix", 0))

    embed = disnake.Embed(
        title=f"Battleground: {bg_type}",
        description=f"Starts <t:{unix}:F> (<t:{unix}:R>)",
        color=BRAND_COLOR,
    )
    roster = "\n".join(f"- <@{user_id}>" for user_id in participants)
    embed.add_field(name=f"Signed Up ({len(participants)})", value=roster or "No signups yet.", inline=False)
    embed.set_footer(text="Use the buttons below to sign up or leave.")
    return embed


async def refresh_event_message(bot, guild_id, event_id, event_data):
    channel = bot.get_channel(int(event_data.get("channel_id", 0)))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(event_id))
        await message.edit(embed=build_event_embed(event_data), view=BattlegroundSignupView())
    except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
        pass


class BattlegroundSignupView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="Sign Up", style=disnake.ButtonStyle.success, custom_id="steward_bg_event_signup")
    async def signup(self, button, inter):
        await inter.response.defer(ephemeral=True, with_message=True)
        ref = event_ref(inter.guild.id, str(inter.message.id))
        doc = ref.get()
        if not doc.exists:
            return await inter.edit_original_message(content="This battleground event is no longer available.")

        event_data = doc.to_dict() or {}
        participants = event_data.get("participants", []) or []
        user_id = str(inter.author.id)
        if user_id not in participants:
            participants.append(user_id)

        event_data["participants"] = participants
        ref.set({"participants": participants, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        await refresh_event_message(inter.client, inter.guild.id, str(inter.message.id), event_data)
        await inter.edit_original_message(content="You are signed up.")

    @disnake.ui.button(label="Leave", style=disnake.ButtonStyle.secondary, custom_id="steward_bg_event_leave")
    async def leave(self, button, inter):
        await inter.response.defer(ephemeral=True, with_message=True)
        ref = event_ref(inter.guild.id, str(inter.message.id))
        doc = ref.get()
        if not doc.exists:
            return await inter.edit_original_message(content="This battleground event is no longer available.")

        event_data = doc.to_dict() or {}
        user_id = str(inter.author.id)
        participants = [uid for uid in event_data.get("participants", []) if uid != user_id]
        event_data["participants"] = participants
        ref.set({"participants": participants, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        await refresh_event_message(inter.client, inter.guild.id, str(inter.message.id), event_data)
        await inter.edit_original_message(content="You were removed from the signup list.")


class Battlegrounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.views_registered = False
        self.bg_reminder_loop.start()

    def cog_unload(self):
        self.bg_reminder_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.views_registered:
            self.bot.add_view(BattlegroundSignupView())
            self.views_registered = True

    @commands.slash_command(name="create_battlegrounds_event", description="Create a BG signup with timed reminders")
    async def create_battlegrounds_event(
        self,
        inter: disnake.ApplicationCommandInteraction,
        type: str = commands.Param(choices=list(BG_TYPES.keys()), description="Battleground type"),
        time: str = commands.Param(description="Your local time, e.g. 8pm, 8:30pm, or 2030"),
    ):
        await inter.response.defer(ephemeral=True)
        timezone_name = await get_user_tz(inter.guild.id, inter.author.id)

        try:
            starts_at = parse_event_time(time, timezone_name)
        except ValueError as exc:
            return await inter.edit_original_message(content=str(exc))

        event_data = {
            "type": type,
            "guild_id": str(inter.guild.id),
            "channel_id": str(inter.channel.id),
            "created_by": str(inter.author.id),
            "creator_timezone": timezone_name,
            "starts_at": starts_at,
            "starts_at_unix": int(starts_at.timestamp()),
            "participants": [],
            "sent_reminders": [],
            "status": "open",
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        ping_roles = []
        all_role = find_role_by_key(inter.guild, "bg_all")
        type_role = find_role_by_key(inter.guild, BG_TYPES[type]["role_key"])
        if all_role:
            ping_roles.append(all_role.mention)
        if type_role:
            ping_roles.append(type_role.mention)

        content = " ".join(ping_roles) if ping_roles else None
        message = await inter.channel.send(content=content, embed=build_event_embed(event_data), view=BattlegroundSignupView())
        event_data["message_id"] = str(message.id)
        event_ref(inter.guild.id, str(message.id)).set(event_data, merge=True)

        await inter.edit_original_message(
            content=f"Battleground event created for <t:{int(starts_at.timestamp())}:F>."
        )

    @tasks.loop(minutes=1)
    async def bg_reminder_loop(self):
        now = datetime.now(timezone.utc)
        guilds = db.collection("guilds").stream()

        for guild_doc in guilds:
            events = guild_doc.reference.collection("battleground_events").where("status", "==", "open").stream()
            for event_doc in events:
                event_data = event_doc.to_dict() or {}
                starts_at = event_data.get("starts_at")
                if not starts_at:
                    continue

                starts_at = starts_at.astimezone(timezone.utc)
                minutes_left = int((starts_at - now).total_seconds() // 60)
                sent = set(event_data.get("sent_reminders", []) or [])
                due = [m for m in REMINDER_MINUTES if minutes_left <= m and str(m) not in sent]
                if not due:
                    continue

                reminder_minute = max(due)
                await self.send_reminder(guild_doc.id, event_doc.id, event_data, reminder_minute)
                sent.add(str(reminder_minute))
                update_data = {"sent_reminders": sorted(sent), "updated_at": firestore.SERVER_TIMESTAMP}
                if reminder_minute == 0:
                    update_data["status"] = "started"
                event_doc.reference.set(update_data, merge=True)

    @bg_reminder_loop.before_loop
    async def before_bg_reminder_loop(self):
        await self.bot.wait_until_ready()

    async def send_reminder(self, guild_id, event_id, event_data, minutes_left):
        channel = self.bot.get_channel(int(event_data.get("channel_id", 0)))
        if not channel:
            return

        participants = event_data.get("participants", []) or []
        if not participants:
            return

        mentions = " ".join(f"<@{user_id}>" for user_id in participants)
        label = "now" if minutes_left == 0 else f"in {minutes_left} minutes"
        await channel.send(
            f"{mentions}\n**{event_data.get('type')}** starts {label}. Get ready!"
        )


def setup(bot):
    bot.add_cog(Battlegrounds(bot))
