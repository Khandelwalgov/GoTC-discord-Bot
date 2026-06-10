import re

import disnake
from disnake.ext import commands
from database import db


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)

ROLE_DEFINITIONS = {
    "availability_open": {"name": "🌅 Weekend: Open", "color": disnake.Color.green()},
    "availability_mid": {"name": "🌤️ Weekend: Mid-Shift", "color": disnake.Color.teal()},
    "availability_close": {"name": "🌙 Weekend: Close", "color": disnake.Color.dark_blue()},
    "availability_all": {"name": "👑 Weekend: Throughout", "color": disnake.Color.gold()},
    "availability_absent": {"name": "❌ Weekend: Absent", "color": disnake.Color.dark_gray()},
    "type_infantry": {"name": "🛡️ Type: Infantry", "color": disnake.Color.dark_red()},
    "type_ranged": {"name": "🏹 Type: Ranged", "color": disnake.Color.dark_green()},
    "type_cavalry": {"name": "🐎 Type: Cavalry", "color": disnake.Color.orange()},
    "specialist_hitter": {"name": "⚔️ Specialist: Hitter", "color": disnake.Color.red()},
    "specialist_siege": {"name": "🪨 Specialist: Siege", "color": disnake.Color.light_gray()},
    "specialist_battlegrounds": {"name": "🔥 Specialist: Battlegrounds", "color": disnake.Color.purple()},
    "dragon_l41": {"name": "🐉 Dragon: L41+ (SoP Rally)", "color": disnake.Color.green()},
    "dragon_l50": {"name": "🐉 Dragon: L50+ (Creature Rally)", "color": disnake.Color.teal()},
    "dragon_l60": {"name": "🐉 Dragon: L60+ (Rein SoP/Keep)", "color": disnake.Color.blue()},
    "dragon_l65": {"name": "🐉 Dragon: L65+ (Rein Ally SoP)", "color": disnake.Color.purple()},
    "dragon_l69": {"name": "🐉 Dragon: L69 (Big Daddy)", "color": disnake.Color.gold()},
    "bg_all": {"name": "📣 Battlegrounds Ping", "color": disnake.Color.purple()},
    "bg_titans": {"name": "❄️ BG: Titans of the North", "color": disnake.Color.blue()},
    "bg_ranging": {"name": "🌲 BG: The Great Ranging", "color": disnake.Color.dark_green()},
}

for tier in range(1, 13):
    ROLE_DEFINITIONS[f"troop_t{tier}"] = {
        "name": f"⚜️ Troop: T{tier}",
        "color": disnake.Color.from_rgb(110 + tier * 8, 90 + tier * 7, 80 + tier * 5),
    }

AVAILABILITY_OPTION_KEYS = ["availability_open", "availability_mid", "availability_close"]
AVAILABILITY_EXCLUSIVE_KEYS = ["availability_all", "availability_absent"]
AVAILABILITY_KEYS = AVAILABILITY_OPTION_KEYS + AVAILABILITY_EXCLUSIVE_KEYS
TROOP_KEYS = [f"troop_t{tier}" for tier in range(1, 13)]
TYPE_KEYS = ["type_infantry", "type_ranged", "type_cavalry"]
SPECIALIST_KEYS = ["specialist_hitter", "specialist_siege", "specialist_battlegrounds"]
DRAGON_KEYS = ["dragon_l41", "dragon_l50", "dragon_l60", "dragon_l65", "dragon_l69"]
BG_ROLE_KEYS = ["bg_all", "bg_titans", "bg_ranging"]


def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))


async def defer_private(inter):
    await inter.response.defer(ephemeral=True, with_message=True)


async def private_done(inter, content):
    await inter.edit_original_message(content=content)


def panel_embed(title, description):
    embed = disnake.Embed(title=title, description=description, color=BRAND_COLOR)
    embed.set_footer(text="Role IDs are saved, so renamed roles keep working.")
    return embed


def role_label(role_key):
    return ROLE_DEFINITIONS[role_key]["name"]


def role_names_for_key(role_key):
    name = role_label(role_key)
    legacy_name = re.sub(r"^[^\w@#]+\s*", "", name).strip()
    names = [name]
    if legacy_name and legacy_name != name:
        names.append(legacy_name)
    return names


def get_role_config(guild_id):
    doc = guild_ref(guild_id).get()
    data = doc.to_dict() if doc.exists else {}
    return data.get("role_ids", {}) or {}


def find_role_by_key(guild, role_key):
    role_ids = get_role_config(guild.id)
    saved_id = role_ids.get(role_key)
    if saved_id:
        role = guild.get_role(int(saved_id))
        if role:
            return role

    for expected_name in role_names_for_key(role_key):
        role = disnake.utils.get(guild.roles, name=expected_name)
        if role:
            return role
    return None


async def ensure_role(guild, role_key):
    role_ids = get_role_config(guild.id)
    saved_id = role_ids.get(role_key)
    if saved_id:
        role = guild.get_role(int(saved_id))
        if role:
            return role, False

    definition = ROLE_DEFINITIONS[role_key]
    role = None
    for expected_name in role_names_for_key(role_key):
        role = disnake.utils.get(guild.roles, name=expected_name)
        if role:
            break
    created = False
    if not role:
        role = await guild.create_role(
            name=definition["name"],
            color=definition["color"],
            reason="Steward GoTC role setup",
        )
        created = True
    else:
        try:
            if role.name != definition["name"] or role.color != definition["color"]:
                await role.edit(name=definition["name"], color=definition["color"], reason="Steward GoTC role refresh")
        except disnake.Forbidden:
            pass

    guild_ref(guild.id).set({"role_ids": {role_key: role.id}}, merge=True)
    return role, created


async def ensure_roles(guild, role_keys):
    created = 0
    for role_key in role_keys:
        _, was_created = await ensure_role(guild, role_key)
        if was_created:
            created += 1
    return created


async def replace_single_role(inter, role_key, role_keys, success_message):
    await defer_private(inter)
    role = find_role_by_key(inter.guild, role_key)
    if not role:
        return await private_done(inter, f"Role `{role_label(role_key)}` was not found. Run `/setup_gotc_roles` first.")

    try:
        roles_to_remove = [find_role_by_key(inter.guild, key) for key in role_keys]
        await inter.author.remove_roles(*[r for r in roles_to_remove if r and r in inter.author.roles])
        await inter.author.add_roles(role)
        await private_done(inter, success_message)
    except disnake.Forbidden:
        await private_done(inter, "I need a higher Steward role to manage this. Move the bot role above the GoTC roles.")


class AvailabilityView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_availability(self, inter, role_key):
        await defer_private(inter)
        role = find_role_by_key(inter.guild, role_key)
        if not role:
            return await private_done(inter, f"Role `{role_label(role_key)}` was not found. Run `/setup_gotc_roles` first.")

        try:
            if role_key in AVAILABILITY_EXCLUSIVE_KEYS:
                to_remove = [find_role_by_key(inter.guild, key) for key in AVAILABILITY_KEYS]
                await inter.author.remove_roles(*[r for r in to_remove if r and r in inter.author.roles])
                await inter.author.add_roles(role)
                return await private_done(inter, f"Availability set to **{role.name}**.")

            exclusive_roles = [find_role_by_key(inter.guild, key) for key in AVAILABILITY_EXCLUSIVE_KEYS]
            await inter.author.remove_roles(*[r for r in exclusive_roles if r and r in inter.author.roles])

            if role in inter.author.roles:
                await inter.author.remove_roles(role)
                await private_done(inter, f"Removed **{role.name}**.")
            else:
                await inter.author.add_roles(role)
                await private_done(inter, f"Added **{role.name}**.")
        except disnake.Forbidden:
            await private_done(inter, "I need a higher Steward role to manage this. Move the bot role above the GoTC roles.")

    @disnake.ui.button(label="Open", style=disnake.ButtonStyle.green, custom_id="steward_availability_open")
    async def open_btn(self, button, inter):
        await self.toggle_availability(inter, "availability_open")

    @disnake.ui.button(label="Mid-Shift", style=disnake.ButtonStyle.blurple, custom_id="steward_availability_mid")
    async def mid_btn(self, button, inter):
        await self.toggle_availability(inter, "availability_mid")

    @disnake.ui.button(label="Close", style=disnake.ButtonStyle.secondary, custom_id="steward_availability_close")
    async def close_btn(self, button, inter):
        await self.toggle_availability(inter, "availability_close")

    @disnake.ui.button(label="Throughout", style=disnake.ButtonStyle.success, custom_id="steward_availability_throughout")
    async def all_btn(self, button, inter):
        await self.toggle_availability(inter, "availability_all")

    @disnake.ui.button(label="Absent", style=disnake.ButtonStyle.danger, custom_id="steward_availability_absent")
    async def absent_btn(self, button, inter):
        await self.toggle_availability(inter, "availability_absent")


class TierRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_tier_role",
        placeholder="Choose troop tier",
        options=[disnake.SelectOption(label=f"Tier {i}", value=f"troop_t{i}") for i in range(1, 13)],
    )
    async def select_tier(self, select, inter):
        role_key = select.values[0]
        await replace_single_role(inter, role_key, TROOP_KEYS, f"Troop tier updated to **{role_label(role_key)}**.")


class TypeRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_type_role",
        placeholder="Choose primary troop type",
        options=[
            disnake.SelectOption(label="Infantry", value="type_infantry"),
            disnake.SelectOption(label="Ranged", value="type_ranged"),
            disnake.SelectOption(label="Cavalry", value="type_cavalry"),
        ],
    )
    async def select_type(self, select, inter):
        role_key = select.values[0]
        await replace_single_role(inter, role_key, TYPE_KEYS, f"Primary troop type updated to **{role_label(role_key)}**.")


class SpecialtyRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, inter, role_key):
        await defer_private(inter)
        role = find_role_by_key(inter.guild, role_key)
        if not role:
            return await private_done(inter, f"Role `{role_label(role_key)}` was not found. Run `/setup_gotc_roles` first.")

        try:
            if role in inter.author.roles:
                await inter.author.remove_roles(role)
                await private_done(inter, f"Removed **{role.name}**.")
            else:
                await inter.author.add_roles(role)
                await private_done(inter, f"Added **{role.name}**.")
        except disnake.Forbidden:
            await private_done(inter, "I need a higher Steward role to manage this. Move the bot role above the GoTC roles.")

    @disnake.ui.button(label="Hitter", style=disnake.ButtonStyle.danger, custom_id="steward_specialty_hitter")
    async def hitter(self, button, inter):
        await self.toggle_role(inter, "specialist_hitter")

    @disnake.ui.button(label="Siege", style=disnake.ButtonStyle.secondary, custom_id="steward_specialty_siege")
    async def siege(self, button, inter):
        await self.toggle_role(inter, "specialist_siege")

    @disnake.ui.button(label="Battlegrounds", style=disnake.ButtonStyle.success, custom_id="steward_specialty_bg")
    async def bg(self, button, inter):
        await self.toggle_role(inter, "specialist_battlegrounds")


class DragonRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_dragon_role",
        placeholder="Choose dragon level",
        options=[
            disnake.SelectOption(label="L41+ SoP Rally", value="dragon_l41"),
            disnake.SelectOption(label="L50+ Creature Rally", value="dragon_l50"),
            disnake.SelectOption(label="L60+ Rein SoP/Keep", value="dragon_l60"),
            disnake.SelectOption(label="L65+ Rein Ally SoP", value="dragon_l65"),
            disnake.SelectOption(label="L69 Big Daddy", value="dragon_l69"),
        ],
    )
    async def select_dragon(self, select, inter):
        role_key = select.values[0]
        await replace_single_role(inter, role_key, DRAGON_KEYS, f"Dragon level updated to **{role_label(role_key)}**.")


class BattlegroundPingView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_bg_role(self, inter, role_key):
        await defer_private(inter)
        role = find_role_by_key(inter.guild, role_key)
        if not role:
            return await private_done(inter, f"Role `{role_label(role_key)}` was not found. Run `/setup_gotc_roles` first.")

        try:
            if role in inter.author.roles:
                await inter.author.remove_roles(role)
                return await private_done(inter, f"Removed **{role.name}**.")

            await inter.author.add_roles(role)
            await private_done(inter, f"Added **{role.name}**.")
        except disnake.Forbidden:
            await private_done(inter, "I need a higher Steward role to manage this. Move the bot role above the GoTC roles.")

    @disnake.ui.button(label="All BG", style=disnake.ButtonStyle.blurple, custom_id="steward_bg_ping_all")
    async def bg_all(self, button, inter):
        await self.toggle_bg_role(inter, "bg_all")

    @disnake.ui.button(label="Titans", style=disnake.ButtonStyle.primary, custom_id="steward_bg_ping_titans")
    async def titans(self, button, inter):
        await self.toggle_bg_role(inter, "bg_titans")

    @disnake.ui.button(label="Great Ranging", style=disnake.ButtonStyle.green, custom_id="steward_bg_ping_ranging")
    async def ranging(self, button, inter):
        await self.toggle_bg_role(inter, "bg_ranging")


class Weekend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.views_registered = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.views_registered:
            return
        self.bot.add_view(AvailabilityView())
        self.bot.add_view(TierRoleView())
        self.bot.add_view(TypeRoleView())
        self.bot.add_view(SpecialtyRoleView())
        self.bot.add_view(DragonRoleView())
        self.bot.add_view(BattlegroundPingView())
        self.views_registered = True

    @commands.slash_command(name="setup_gotc_roles", description="Create or verify all Steward GoTC roles")
    @commands.has_permissions(administrator=True)
    async def configure_weekend(self, inter):
        await inter.response.defer(ephemeral=True)
        created = await ensure_roles(inter.guild, ROLE_DEFINITIONS.keys())
        await inter.edit_original_message(
            content=f"GoTC roles verified and saved by ID. Created **{created}** missing roles."
        )

    @commands.slash_command(name="availability_report", description="Show current weekend availability by role")
    async def get_availability(self, inter):
        await inter.response.defer()
        embed = disnake.Embed(title="Weekend Availability", color=BRAND_COLOR)

        for role_key in AVAILABILITY_KEYS:
            role = find_role_by_key(inter.guild, role_key)
            if role:
                members = [member.mention for member in role.members]
                embed.add_field(name=role.name, value=", ".join(members) if members else "None", inline=False)

        await inter.edit_original_message(embed=embed)

    @commands.slash_command(name="availability_check", description="Reset and post the weekend availability panel")
    async def post_weekend_availability(self, inter):
        await inter.response.defer(ephemeral=True)
        for role_key in AVAILABILITY_KEYS:
            role = find_role_by_key(inter.guild, role_key)
            if not role:
                continue
            for member in role.members:
                try:
                    await member.remove_roles(role)
                except disnake.Forbidden:
                    return await inter.edit_original_message(
                        content="I need a higher Steward role before I can reset availability roles."
                    )

        embed = panel_embed(
            "Weekend Availability Check",
            "Open, Mid-Shift, and Close can be combined. Click again to remove. Throughout and Absent are exclusive.",
        )
        await inter.channel.send(embed=embed, view=AvailabilityView())
        await inter.edit_original_message(content="Availability panel posted.")

    @commands.slash_command(name="post_role_panel", description="Post the permanent GoTC role selection panel")
    @commands.has_permissions(administrator=True)
    async def setup_reaction_roles(self, inter):
        await inter.response.defer(ephemeral=True)
        panels = [
            ("Troop Tier", "Choose the highest troop tier you want shown on your profile.", TierRoleView()),
            ("Primary Troop Type", "Choose the troop type you usually lead with.", TypeRoleView()),
            ("Specialist Roles", "Toggle any extra jobs you can cover.", SpecialtyRoleView()),
            ("Dragon Level", "Choose the dragon threshold that best matches your account.", DragonRoleView()),
        ]

        for title, description, view in panels:
            await inter.channel.send(embed=panel_embed(title, description), view=view)

        await inter.edit_original_message(content="Role selection panels posted.")

    @commands.slash_command(name="post_battleground_ping_panel", description="Post BG ping opt-in buttons")
    @commands.has_permissions(administrator=True)
    async def post_battleground_ping_panel(self, inter):
        await inter.response.defer(ephemeral=True)
        embed = panel_embed(
            "Battleground Ping Opt-In",
            "Choose whether you want all battleground pings, Titans of the North pings, or The Great Ranging pings.",
        )
        await inter.channel.send(embed=embed, view=BattlegroundPingView())
        await inter.edit_original_message(content="Battleground ping panel posted.")


def setup(bot):
    bot.add_cog(Weekend(bot))
