import disnake
from disnake.ext import commands

# --- AVAILABILITY VIEW ---
class AvailabilityView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.options = {
            "Open": "🌅 Weekend: Open",
            "Mid-Shift": "🌤️ Weekend: Mid-Shift",
            "Close": "🌑 Weekend: Close",
            "Throughout": "👑 Weekend: Throughout",
            "Absent": "❌ Weekend: Absent"
        }

    async def update_role(self, inter, label):
        await inter.response.defer(ephemeral=True)
        role_name = self.options[label]
        role = disnake.utils.get(inter.guild.roles, name=role_name)
        
        if not role:
            return await inter.edit_original_message(content=f"❌ Role `{role_name}` not found. Run `/configure_weekend`.")
            
        try:
            to_remove = [disnake.utils.get(inter.guild.roles, name=n) for n in self.options.values()]
            await inter.author.remove_roles(*[r for r in to_remove if r and r in inter.author.roles])
            
            await inter.author.add_roles(role)
            await inter.edit_original_message(content=f"✅ Availability set to **{label}**")
        except disnake.Forbidden:
            await inter.edit_original_message(content="❌ Missing Permissions! Move 'Steward' role to the TOP in Server Settings.")

    @disnake.ui.button(label="Open", style=disnake.ButtonStyle.green)
    async def open_btn(self, b, i): await self.update_role(i, "Open")
    
    @disnake.ui.button(label="Mid-Shift", style=disnake.ButtonStyle.blurple)
    async def mid_btn(self, b, i): await self.update_role(i, "Mid-Shift")
    
    @disnake.ui.button(label="Close", style=disnake.ButtonStyle.secondary)
    async def close_btn(self, b, i): await self.update_role(i, "Close")
    
    @disnake.ui.button(label="Throughout", style=disnake.ButtonStyle.success)
    async def all_btn(self, b, i): await self.update_role(i, "Throughout")
    
    @disnake.ui.button(label="Absent", style=disnake.ButtonStyle.danger)
    async def abs_btn(self, b, i): await self.update_role(i, "Absent")

# --- REACTION ROLE VIEWS ---
class TierRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_tier_role",
        placeholder="Choose your Troop Tier (T1-T12)...",
        options=[disnake.SelectOption(label=f"Tier {i}", value=f"T{i}") for i in range(1, 13)]
    )
    async def select_tier(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        role_name = f"Troop: {select.values[0]}"
        role = disnake.utils.get(inter.guild.roles, name=role_name)
        
        try:
            tier_roles = [disnake.utils.get(inter.guild.roles, name=f"Troop: T{i}") for i in range(1, 13)]
            await inter.author.remove_roles(*[r for r in tier_roles if r and r in inter.author.roles])
            if role: await inter.author.add_roles(role)
            await inter.edit_original_message(content=f"✅ Updated to **{role_name}**")
        except disnake.Forbidden:
            await inter.edit_original_message(content="❌ Missing Permissions! Move 'Steward' role to the TOP.")

class TypeRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        custom_id="select_type_role",
        placeholder="Choose your Primary Troop Type...",
        options=[
            disnake.SelectOption(label="Infantry", emoji="🛡️"),
            disnake.SelectOption(label="Ranged", emoji="🏹"),
            disnake.SelectOption(label="Cavalry", emoji="🐎")
        ]
    )
    async def select_type(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        role_name = f"Type: {select.values[0]}"
        role = disnake.utils.get(inter.guild.roles, name=role_name)
        
        try:
            type_roles = [disnake.utils.get(inter.guild.roles, name=f"Type: {t}") for t in ["Infantry", "Ranged", "Cavalry"]]
            await inter.author.remove_roles(*[r for r in type_roles if r and r in inter.author.roles])
            if role: await inter.author.add_roles(role)
            await inter.edit_original_message(content=f"✅ Updated to **{role_name}**")
        except disnake.Forbidden:
            await inter.edit_original_message(content="❌ Missing Permissions! Move 'Steward' role to the TOP.")

class SpecialtyRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, inter, role_name):
        await inter.response.defer(ephemeral=True)
        role = disnake.utils.get(inter.guild.roles, name=role_name)
        if not role:
            return await inter.edit_original_message(content=f"❌ Role `{role_name}` not found.")
            
        try:
            if role in inter.author.roles:
                await inter.author.remove_roles(role)
                await inter.edit_original_message(content=f"❌ Removed **{role_name}**")
            else:
                await inter.author.add_roles(role)
                await inter.edit_original_message(content=f"✅ Added **{role_name}**")
        except disnake.Forbidden:
            await inter.edit_original_message(content="❌ Missing Permissions! Move 'Steward' role to the TOP.")

    @disnake.ui.button(label="Hitter Squad", style=disnake.ButtonStyle.danger)
    async def hitter(self, b, i): await self.toggle_role(i, "Specialist: Hitter")

    @disnake.ui.button(label="Siege", style=disnake.ButtonStyle.secondary)
    async def siege(self, b, i): await self.toggle_role(i, "Specialist: Siege")

    @disnake.ui.button(label="Battlegrounds", style=disnake.ButtonStyle.success)
    async def bg(self, b, i): await self.toggle_role(i, "Specialist: Battlegrounds")

# --- MESSAGE #4: DRAGON ROLES ---
class DragonRoleView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.dragon_options = {
            "L41": "Dragon: L41+ (SoP Rally)",
            "L50": "Dragon: L50+ (Creature Rally)",
            "L60": "Dragon: L60+ (Rein SoP/Keep)",
            "L65": "Dragon: L65+ (Rein Ally SoP)",
            "L69": "Dragon: L69 (Big Daddy)"
        }

    @disnake.ui.string_select(
        custom_id="select_dragon_role",
        placeholder="Choose your Dragon Level threshold...",
        options=[
            disnake.SelectOption(label="L41+: SoP Rally", value="L41"),
            disnake.SelectOption(label="L50+: Creature Rally", value="L50"),
            disnake.SelectOption(label="L60+: Rein own SoP and rein keeps", value="L60"),
            disnake.SelectOption(label="L65+: Rein Ally SoP", value="L65"),
            disnake.SelectOption(label="L69: Big Daddy", value="L69")
        ]
    )
    async def select_dragon(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        choice = select.values[0]
        role_name = self.dragon_options[choice]
        role = disnake.utils.get(inter.guild.roles, name=role_name)

        try:
            to_remove = [disnake.utils.get(inter.guild.roles, name=n) for n in self.dragon_options.values()]
            await inter.author.remove_roles(*[r for r in to_remove if r and r in inter.author.roles])
            
            if role: await inter.author.add_roles(role)
            await inter.edit_original_message(content=f"✅ Dragon status updated to **{role_name}**")
        except disnake.Forbidden:
            await inter.edit_original_message(content="❌ Missing Permissions! Move 'Steward' role to the TOP.")

# --- THE COG ---
class Weekend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Step 1: Create all necessary roles")
    @commands.has_permissions(administrator=True)
    async def configure_weekend(self, inter):
        await inter.response.defer(ephemeral=True)
        avail = ["🌅 Weekend: Open", "🌤️ Weekend: Mid-Shift", "🌑 Weekend: Close", "👑 Weekend: Throughout", "❌ Weekend: Absent"]
        tiers = [f"Troop: T{i}" for i in range(1, 13)]
        types = ["Type: Infantry", "Type: Ranged", "Type: Cavalry"]
        specs = ["Specialist: Hitter", "Specialist: Siege", "Specialist: Battlegrounds"]
        dragons = ["Dragon: L41+ (SoP Rally)", "Dragon: L50+ (Creature Rally)", "Dragon: L60+ (Rein SoP/Keep)", "Dragon: L65+ (Rein Ally SoP)", "Dragon: L69 (Big Daddy)"]
        
        all_roles = avail + tiers + types + specs + dragons
        for r_name in all_roles:
            if not disnake.utils.get(inter.guild.roles, name=r_name):
                await inter.guild.create_role(name=r_name, reason="Steward Role Setup")
        
        await inter.edit_original_message(content="✅ All GoTC roles (including Dragon levels) created/verified.")

    @commands.slash_command(description="Council Only: See who is available when")
    async def get_availability(self, inter):
        await inter.response.defer()
        roles = ["👑 Weekend: Throughout", "🌅 Weekend: Open", "🌤️ Weekend: Mid-Shift", "🌑 Weekend: Close", "❌ Weekend: Absent"]
        embed = disnake.Embed(title="📅 Allegiance Weekend Availability", color=disnake.Color.gold())
        
        for r_name in roles:
            role = disnake.utils.get(inter.guild.roles, name=r_name)
            if role:
                members = [m.mention for m in role.members]
                val = ", ".join(members) if members else "None"
                embed.add_field(name=r_name, value=val, inline=False)
        
        await inter.edit_original_message(embed=embed)
        
    @commands.slash_command(description="Step 2: Post Availability Selection")
    async def post_weekend_availability(self, inter):
        # We don't defer here because we want to send a NEW message to the channel
        roles_to_clear = ["🌅 Weekend: Open", "🌤️ Weekend: Mid-Shift", "🌑 Weekend: Close", "👑 Weekend: Throughout", "❌ Weekend: Absent"]
        for r_name in roles_to_clear:
            role = disnake.utils.get(inter.guild.roles, name=r_name)
            if role:
                for member in role.members:
                    try:
                        await member.remove_roles(role)
                    except:
                        pass
        
        await inter.send("📊 **Weekend Availability Check**\nSelect your status:", view=AvailabilityView())

    @commands.slash_command(description="Step 3: Setup Permanent Role Selection")
    @commands.has_permissions(administrator=True)
    async def setup_reaction_roles(self, inter):
        await inter.response.defer(ephemeral=True)
        
        await inter.channel.send("📜 **Troop Tier Selection**", view=TierRoleView())
        await inter.channel.send("⚔️ **Primary Troop Type**", view=TypeRoleView())
        await inter.channel.send("🌟 **Additional Specialist Roles**", view=SpecialtyRoleView())
        await inter.channel.send("🐉 **Dragon Level Roles**", view=DragonRoleView())
        
        await inter.edit_original_message(content="✅ All 4 role selection messages posted.")

def setup(bot):
    bot.add_cog(Weekend(bot))