import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore

# --- VIEWS ---
class AltTypeView(disnake.ui.View):
    def __init__(self, alt_name, guild_id):
        super().__init__(timeout=60)
        self.alt_name = alt_name
        self.guild_id = guild_id

    @disnake.ui.string_select(
        placeholder="Select Alt Purpose...",
        options=[
            disnake.SelectOption(label=p, value=p) for p in 
            ["Resources", "Placeholding", "Full Account", "Attack", "Defence", "Reinforcement", "Rally"]
        ]
    )
    async def select_purpose(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        alt_data = {
            "purpose": select.values[0],
            "created_at": firestore.SERVER_TIMESTAMP
        }
        try:
            # Server-Isolated Path
            db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id)).collection("alts").document(self.alt_name).set(alt_data, merge=True)
            await inter.edit_original_message(
                content=f"✅ Alt **{self.alt_name}** registered as **{select.values[0]}**!",
                view=None
            )
        except Exception as e:
            await inter.edit_original_message(content=f"❌ Error registering alt: {e}")

# --- MODALS ---
class AttackStatsModal(disnake.ui.Modal):
    def __init__(self, target_name: str, is_alt: bool, guild_id: int):
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        components = [
            disnake.ui.TextInput(label="Marching Attack vs SoP", custom_id="m_att"),
            disnake.ui.TextInput(label="Marching Health vs SoP", custom_id="m_health"),
            disnake.ui.TextInput(label="Marching Defence vs SoP", custom_id="m_def"),
            disnake.ui.TextInput(label="Rally Cap", custom_id="r_cap"),
            disnake.ui.TextInput(label="Rally Cap vs SoP", custom_id="r_sop"),
        ]
        super().__init__(title=f"Attack Stats: {target_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        path.set({"attack_stats": inter.text_values}, merge=True)
        await inter.edit_original_message(content=f"⚔️ Attack stats updated for **{self.target_name}**.")

class DefenceStatsModal(disnake.ui.Modal):
    def __init__(self, target_name: str, is_alt: bool, guild_id: int):
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        components = [
            disnake.ui.TextInput(label="Attack at SoP (Stationary)", custom_id="s_att"),
            disnake.ui.TextInput(label="Defence at SoP (Stationary)", custom_id="s_def"),
            disnake.ui.TextInput(label="Health at SoP (Stationary)", custom_id="s_health"),
            disnake.ui.TextInput(label="Reinforcement Cap vs SoP", custom_id="rein_sop"),
        ]
        super().__init__(title=f"Defence Stats: {target_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        path.set({"defence_stats": inter.text_values}, merge=True)
        await inter.edit_original_message(content=f"🛡️ Defence stats updated for **{self.target_name}**.")

class ProxyStatsModal(disnake.ui.Modal):
    def __init__(
        self,
        stat_type: str,
        target_member_id: int,
        target_member_display: str,
        target_name: str,
        is_alt: bool,
        guild_id: int,
        admin_id: int,
    ):
        self.stat_type = stat_type
        self.target_member_id = target_member_id
        self.target_member_display = target_member_display
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        self.admin_id = admin_id

        if stat_type == "attack":
            components = [
                disnake.ui.TextInput(label="Marching Attack vs SoP", custom_id="m_att"),
                disnake.ui.TextInput(label="Marching Health vs SoP", custom_id="m_health"),
                disnake.ui.TextInput(label="Marching Defence vs SoP", custom_id="m_def"),
                disnake.ui.TextInput(label="Rally Cap", custom_id="r_cap"),
                disnake.ui.TextInput(label="Rally Cap vs SoP", custom_id="r_sop"),
            ]
        else:
            components = [
                disnake.ui.TextInput(label="Attack at SoP (Stationary)", custom_id="s_att"),
                disnake.ui.TextInput(label="Defence at SoP (Stationary)", custom_id="s_def"),
                disnake.ui.TextInput(label="Health at SoP (Stationary)", custom_id="s_health"),
                disnake.ui.TextInput(label="Reinforcement Cap vs SoP", custom_id="rein_sop"),
            ]

        super().__init__(
            title=f"{stat_type.capitalize()} Stats: {target_member_display}",
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = (
            db.collection("guilds")
            .document(str(self.guild_id))
            .collection("users")
            .document(str(self.target_member_id))
        )
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        stat_field = "attack_stats" if self.stat_type == "attack" else "defence_stats"
        path.set(
            {
                stat_field: inter.text_values,
                "stats_updated_by": str(self.admin_id),
                "stats_updated_via": "admin_proxy",
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.edit_original_message(
            content=(
                f"{self.stat_type.capitalize()} stats updated for "
                f"**{self.target_member_display}** / **{self.target_name}**."
            )
        )

# --- COG ---
class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def validate_target(self, inter, target):
        if target.lower() == "main":
            return True, False

        user_ref = db.collection("guilds").document(str(inter.guild.id)).collection("users").document(str(inter.author.id))
        alt_doc = user_ref.collection("alts").document(target).get()
        
        if alt_doc.exists:
            return True, True
        
        alts_stream = user_ref.collection("alts").stream()
        registered_alts = [a.id for a in alts_stream]
        alt_list_str = ", ".join(registered_alts) if registered_alts else "None"
        
        await inter.send(
            content=f"❌ **{target}** is not a registered alt in this server.\n\n"
                    f"**Your registered alts:** {alt_list_str}",
            ephemeral=True
        )
        return False, False

    @commands.slash_command(description="Register a new Alt account")
    async def add_alt(self, inter: disnake.ApplicationCommandInteraction, name: str):
        await inter.send(f"What is the purpose of **{name}**?", view=AltTypeView(name, inter.guild.id), ephemeral=True)

    @commands.slash_command(description="Update Attack/Rally stats")
    async def update_attack(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(description="Enter 'main' or Alt Name")):
        is_valid, is_alt = await self.validate_target(inter, target)
        if is_valid:
            await inter.response.send_modal(AttackStatsModal(target, is_alt, inter.guild.id))

    @commands.slash_command(description="Update Defence/Stationary stats")
    async def update_defence(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(description="Enter 'main' or Alt Name")):
        is_valid, is_alt = await self.validate_target(inter, target)
        if is_valid:
            await inter.response.send_modal(DefenceStatsModal(target, is_alt, inter.guild.id))

    @commands.slash_command(description="Admin: update a member's stats on their behalf")
    @commands.has_permissions(administrator=True)
    async def add_update(
        self,
        inter: disnake.ApplicationCommandInteraction,
        member: disnake.Member = commands.Param(description="Member whose stats should be updated"),
        stat_type: str = commands.Param(choices=["attack", "defence"], description="Stats to update"),
        target: str = commands.Param(default="main", description="main or an existing alt name"),
    ):
        is_alt = target.lower() != "main"
        if is_alt:
            alt_doc = (
                db.collection("guilds")
                .document(str(inter.guild.id))
                .collection("users")
                .document(str(member.id))
                .collection("alts")
                .document(target)
                .get()
            )
            if not alt_doc.exists:
                return await inter.send(
                    f"That alt is not registered under {member.mention}. Ask them/admin to add the alt first.",
                    ephemeral=True,
                )

        await inter.response.send_modal(
            ProxyStatsModal(
                stat_type=stat_type,
                target_member_id=member.id,
                target_member_display=member.display_name,
                target_name=target,
                is_alt=is_alt,
                guild_id=inter.guild.id,
                admin_id=inter.author.id,
            )
        )

def setup(bot):
    bot.add_cog(Stats(bot))
