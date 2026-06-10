import disnake
from disnake.ext import commands


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)

AVAILABILITY_ROLES = {
    "Open": "Weekend: Open",
    "Mid": "Weekend: Mid-Shift",
    "Close": "Weekend: Close",
    "All": "Weekend: Throughout",
    "Absent": "Weekend: Absent",
}

TROOP_TYPES = ["Infantry", "Ranged", "Cavalry"]
SPECIALIST_ROLES = {
    "Hitter": "Specialist: Hitter",
    "Siege": "Specialist: Siege",
    "Battlegrounds": "Specialist: Battlegrounds",
}
DRAGON_ROLES = {
    "L41": "Dragon: L41+ (SoP Rally)",
    "L50": "Dragon: L50+ (Creature Rally)",
    "L60": "Dragon: L60+ (Rein SoP/Keep)",
    "L65": "Dragon: L65+ (Rein Ally SoP)",
    "L69": "Dragon: L69 (Big Daddy)",
}


async def defer_private(inter):
    await inter.response.defer(ephemeral=True, with_message=True)


async def private_done(inter, content):
    await inter.edit_original_message(content=content)


def panel_embed(title, description):
    embed = disnake.Embed(title=title, description=description, color=BRAND_COLOR)
    embed.set_footer(text="Steward role panels survive Render restarts after redeploy.")
    return embed


async def replace_single_role(inter, role_name, role_names, success_message):
    await defer_private(inter)
    role = disnake.utils.get(inter.guild.roles, name=role_name)
    if not role:
        return await private_done(inter, f"Role `{role_name}` was not found. Run `/setup_gotc_roles` first.")

    try:
        roles_to_remove = [disnake.utils.get(inter.guild.roles, name=name) for name in role_names]
        await inter.author.remove_roles(*[r for r in roles_to_remove if r and r in inter.author.roles])
        await inter.author.add_roles(role)
        await private_done(inter, success_message)
    except disnake.Forbidden:
        await private_done(inter, "I need a higher Steward role to manage this. Move the bot role above the GoTC roles.")


class AvailabilityView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_role(self, inter, key):
        await replace_single_role(
            inter,
            AVAILABILITY_ROLES[key],
            AVAILABILITY_ROLES.values(),
            f"Availability set to **{key}**.",
        )

    @disnake.ui.button(label="Open", style=disnake.ButtonStyle.green, custom_id="steward_availability_open")
    async def open_btn(self, button, inter):
        await self.update_role(inter, "Open")

    @disnake.ui.button(label="Mid-Shift", style=disnake.ButtonStyle.blurple, custom_id="steward_availability_mid")
    async def mid_btn(self, button, inter):
        await self.update_role(inter, "Mid")

    @disnake.ui.button(label="Close", style=disnake.ButtonStyle.secondary, custom_id="steward_availability_close")
    async def close_btn(self, button, inter):
        await self.update_role(inter, "Close")

    @disnake.ui.button(label="Throughout", style=disnake.ButtonStyle.success, custom_id="steward_availability_throughout")
    async def all_btn(self, button, inter):
        await self.update_role(inter, "All")

    @disnake.ui.button(label="Absent", style=disnake.ButtonStyle.danger, custom_id="steward_availability_absent")
    async def absent_btn(self, button, inter):
        await self.update_role(inter, "Absent")


class TierRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_tier_role",
        placeholder="Choose troop tier",
        options=[disnake.SelectOption(label=f"Tier {i}", value=f"T{i}") for i in range(1, 13)],
    )
    async def select_tier(self, select, inter):
        tier = select.values[0]
        await replace_single_role(
            inter,
            f"Troop: {tier}",
            [f"Troop: T{i}" for i in range(1, 13)],
            f"Troop tier updated to **{tier}**.",
        )


class TypeRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_type_role",
        placeholder="Choose primary troop type",
        options=[disnake.SelectOption(label=troop_type, value=troop_type) for troop_type in TROOP_TYPES],
    )
    async def select_type(self, select, inter):
        troop_type = select.values[0]
        await replace_single_role(
            inter,
            f"Type: {troop_type}",
            [f"Type: {name}" for name in TROOP_TYPES],
            f"Primary troop type updated to **{troop_type}**.",
        )


class SpecialtyRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, inter, role_name):
        await defer_private(inter)
        role = disnake.utils.get(inter.guild.roles, name=role_name)
        if not role:
            return await private_done(inter, f"Role `{role_name}` was not found. Run `/setup_gotc_roles` first.")

        try:
            if role in inter.author.roles:
                await inter.author.remove_roles(role)
                await private_done(inter, f"Removed **{role_name}**.")
            else:
                await inter.author.add_roles(role)
                await private_done(inter, f"Added **{role_name}**.")
        except disnake.Forbidden:
            await private_done(inter, "I need a higher Steward role to manage this. Move the bot role above the GoTC roles.")

    @disnake.ui.button(label="Hitter", style=disnake.ButtonStyle.danger, custom_id="steward_specialty_hitter")
    async def hitter(self, button, inter):
        await self.toggle_role(inter, SPECIALIST_ROLES["Hitter"])

    @disnake.ui.button(label="Siege", style=disnake.ButtonStyle.secondary, custom_id="steward_specialty_siege")
    async def siege(self, button, inter):
        await self.toggle_role(inter, SPECIALIST_ROLES["Siege"])

    @disnake.ui.button(label="Battlegrounds", style=disnake.ButtonStyle.success, custom_id="steward_specialty_bg")
    async def bg(self, button, inter):
        await self.toggle_role(inter, SPECIALIST_ROLES["Battlegrounds"])


class DragonRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_dragon_role",
        placeholder="Choose dragon level",
        options=[
            disnake.SelectOption(label="L41+ SoP Rally", value="L41"),
            disnake.SelectOption(label="L50+ Creature Rally", value="L50"),
            disnake.SelectOption(label="L60+ Rein SoP/Keep", value="L60"),
            disnake.SelectOption(label="L65+ Rein Ally SoP", value="L65"),
            disnake.SelectOption(label="L69 Big Daddy", value="L69"),
        ],
    )
    async def select_dragon(self, select, inter):
        choice = select.values[0]
        await replace_single_role(
            inter,
            DRAGON_ROLES[choice],
            DRAGON_ROLES.values(),
            f"Dragon level updated to **{DRAGON_ROLES[choice]}**.",
        )


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
        self.views_registered = True

    @commands.slash_command(name="setup_gotc_roles", description="Create or verify all Steward GoTC roles")
    @commands.has_permissions(administrator=True)
    async def configure_weekend(self, inter):
        await inter.response.defer(ephemeral=True)
        all_roles = (
            list(AVAILABILITY_ROLES.values())
            + [f"Troop: T{i}" for i in range(1, 13)]
            + [f"Type: {name}" for name in TROOP_TYPES]
            + list(SPECIALIST_ROLES.values())
            + list(DRAGON_ROLES.values())
        )

        created = 0
        for role_name in all_roles:
            if not disnake.utils.get(inter.guild.roles, name=role_name):
                await inter.guild.create_role(name=role_name, reason="Steward GoTC role setup")
                created += 1

        await inter.edit_original_message(content=f"GoTC roles verified. Created **{created}** missing roles.")

    @commands.slash_command(name="availability_report", description="Show current weekend availability by role")
    async def get_availability(self, inter):
        await inter.response.defer()
        embed = disnake.Embed(title="Weekend Availability", color=BRAND_COLOR)

        for role_name in [
            AVAILABILITY_ROLES["All"],
            AVAILABILITY_ROLES["Open"],
            AVAILABILITY_ROLES["Mid"],
            AVAILABILITY_ROLES["Close"],
            AVAILABILITY_ROLES["Absent"],
        ]:
            role = disnake.utils.get(inter.guild.roles, name=role_name)
            if role:
                members = [member.mention for member in role.members]
                embed.add_field(name=role_name, value=", ".join(members) if members else "None", inline=False)

        await inter.edit_original_message(embed=embed)

    @commands.slash_command(name="availability_check", description="Reset and post the weekend availability panel")
    async def post_weekend_availability(self, inter):
        await inter.response.defer(ephemeral=True)
        for role_name in AVAILABILITY_ROLES.values():
            role = disnake.utils.get(inter.guild.roles, name=role_name)
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
            "Pick the slot you can cover this weekend. Your previous weekend availability role will be replaced.",
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


def setup(bot):
    bot.add_cog(Weekend(bot))
