import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore
from services.access_control import has_logistics_access, logistics_denied_message

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
            ["Resources", "Placeholding", "Full Account", "Attack", "Defense", "Reinforcement", "Rally"]
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
            disnake.ui.TextInput(label="Marcher Attack vs Player at Seat of Power", custom_id="m_att", placeholder="Primary troop only: marcher attack vs player at seat of power"),
            disnake.ui.TextInput(label="Marcher Defense vs Player at Seat of Power", custom_id="m_def", placeholder="Primary troop only: marcher defense vs player at seat of power"),
            disnake.ui.TextInput(label="Marcher Health vs Player at Seat of Power", custom_id="m_health", placeholder="Primary troop only: marcher health vs player at seat of power"),
            disnake.ui.TextInput(label="Rally Cap", custom_id="r_cap", placeholder="Your rally capacity"),
            disnake.ui.TextInput(label="Rally Cap vs SoP", custom_id="r_sop", placeholder="Rally cap used at seat of power"),
        ]
        super().__init__(title="Attack Stats - Primary Troop", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        path.set({"attack_stats": inter.text_values}, merge=True)
        await inter.edit_original_message(content=f"⚔️ Attack stats updated for **{self.target_name}**.")

class DefenseStatsModal(disnake.ui.Modal):
    def __init__(self, target_name: str, is_alt: bool, guild_id: int):
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        components = [
            disnake.ui.TextInput(label="Defense vs Player at Seat of Power", custom_id="s_def", placeholder="Primary troop only: defense vs player at seat of power"),
            disnake.ui.TextInput(label="Attack vs Player at Seat of Power", custom_id="s_att", placeholder="Primary troop only: attack vs player at seat of power"),
            disnake.ui.TextInput(label="Health vs Player at Seat of Power", custom_id="s_health", placeholder="Primary troop only: health vs player at seat of power"),
            disnake.ui.TextInput(label="Reinforcement Cap at Owned Seat of Power", custom_id="rein_sop", placeholder="Reinforcement cap at owned seat of power"),
        ]
        super().__init__(title="Defense Stats - Primary Troop", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        path.set({"defence_stats": inter.text_values}, merge=True)
        await inter.edit_original_message(content=f"🛡️ Defense stats updated for **{self.target_name}**.")


class DragonStatsModal(disnake.ui.Modal):
    def __init__(self, stat_type: str, target_name: str, is_alt: bool, guild_id: int):
        self.stat_type = stat_type
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id

        if stat_type == "attack":
            components = [
                disnake.ui.TextInput(label="Dragon Marcher Attack vs Player at SoP", custom_id="dragon_m_att", placeholder="Dragon marcher attack vs player at seat of power"),
                disnake.ui.TextInput(label="Dragon Marcher Defense vs Player at SoP", custom_id="dragon_m_def", placeholder="Dragon marcher defense vs player at seat of power"),
                disnake.ui.TextInput(label="Dragon Marcher Health vs Player at SoP", custom_id="dragon_m_health", placeholder="Dragon marcher health vs player at seat of power"),
                disnake.ui.TextInput(label="Dragon Attack vs Dragon", custom_id="dragon_att_vs_dragon", placeholder="Dragon attack vs dragon"),
            ]
            title = "Dragon Attack Upgrade Stats"
        else:
            components = [
                disnake.ui.TextInput(label="Dragon Defense vs Player at SoP", custom_id="dragon_def_player_sop", placeholder="Dragon defense vs player at seat of power"),
                disnake.ui.TextInput(label="Dragon Attack vs Player at SoP", custom_id="dragon_att_player_sop", placeholder="Dragon attack vs player at seat of power"),
                disnake.ui.TextInput(label="Dragon Health vs Player at SoP", custom_id="dragon_health_player_sop", placeholder="Dragon health vs player at seat of power"),
                disnake.ui.TextInput(label="Dragon Defense vs Dragon", custom_id="dragon_def_vs_dragon", placeholder="Dragon defense vs dragon"),
            ]
            title = "Dragon Defense Upgrade Stats"

        super().__init__(title=title, components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        stat_field = "dragon_attack_stats" if self.stat_type == "attack" else "dragon_defense_stats"
        path.set({stat_field: inter.text_values, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        await inter.edit_original_message(
            content=f"Dragon {self.stat_type} upgrade stats updated for **{self.target_name}**."
        )

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
                disnake.ui.TextInput(label="Marcher Attack vs Player at Seat of Power", custom_id="m_att", placeholder="Primary troop only: marcher attack vs player at seat of power"),
                disnake.ui.TextInput(label="Marcher Defense vs Player at Seat of Power", custom_id="m_def", placeholder="Primary troop only: marcher defense vs player at seat of power"),
                disnake.ui.TextInput(label="Marcher Health vs Player at Seat of Power", custom_id="m_health", placeholder="Primary troop only: marcher health vs player at seat of power"),
                disnake.ui.TextInput(label="Rally Cap", custom_id="r_cap", placeholder="Your rally capacity"),
                disnake.ui.TextInput(label="Rally Cap vs SoP", custom_id="r_sop", placeholder="Rally cap used at seat of power"),
            ]
        else:
            components = [
                disnake.ui.TextInput(label="Defense vs Player at Seat of Power", custom_id="s_def", placeholder="Primary troop only: defense vs player at seat of power"),
                disnake.ui.TextInput(label="Attack vs Player at Seat of Power", custom_id="s_att", placeholder="Primary troop only: attack vs player at seat of power"),
                disnake.ui.TextInput(label="Health vs Player at Seat of Power", custom_id="s_health", placeholder="Primary troop only: health vs player at seat of power"),
                disnake.ui.TextInput(label="Reinforcement Cap at Owned Seat of Power", custom_id="rein_sop", placeholder="Reinforcement cap at owned seat of power"),
            ]

        super().__init__(
            title=f"{stat_type.capitalize()} Stats - Primary Troop",
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

    @commands.slash_command(name="update_defense", description="Update Defense/Stationary stats")
    async def update_defense(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(description="Enter 'main' or Alt Name")):
        is_valid, is_alt = await self.validate_target(inter, target)
        if is_valid:
            await inter.response.send_modal(DefenseStatsModal(target, is_alt, inter.guild.id))

    @commands.slash_command(name="upgrade_dragon_attack_stats", description="Update dragon attack upgrade stats")
    async def upgrade_dragon_attack_stats(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(default="main", description="Enter 'main' or Alt Name")):
        is_valid, is_alt = await self.validate_target(inter, target)
        if is_valid:
            await inter.response.send_modal(DragonStatsModal("attack", target, is_alt, inter.guild.id))

    @commands.slash_command(name="upgrade_dragon_defense_stats", description="Update dragon defense upgrade stats")
    async def upgrade_dragon_defense_stats(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(default="main", description="Enter 'main' or Alt Name")):
        is_valid, is_alt = await self.validate_target(inter, target)
        if is_valid:
            await inter.response.send_modal(DragonStatsModal("defense", target, is_alt, inter.guild.id))

    @commands.slash_command(description="Admin/Logistics: update a member's stats on their behalf")
    async def add_update(
        self,
        inter: disnake.ApplicationCommandInteraction,
        member: disnake.Member = commands.Param(description="Member whose stats should be updated"),
        stat_type: str = commands.Param(choices=["attack", "defense"], description="Stats to update"),
        target: str = commands.Param(default="main", description="main or an existing alt name"),
    ):
        if not has_logistics_access(inter):
            return await inter.send(logistics_denied_message(), ephemeral=True)

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
