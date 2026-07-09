import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore
from services.access_control import has_logistics_access, logistics_denied_message
from services.translation import get_user_language, t


ALT_PURPOSES = ["Resources", "Placeholding", "Full Account", "Attack", "Defense", "Reinforcement", "Rally"]


def translated_input(language_code, custom_id):
    return disnake.ui.TextInput(
        label=t(f"stats.modal.{custom_id}.label", language_code),
        custom_id=custom_id,
        placeholder=t(f"stats.modal.{custom_id}.placeholder", language_code),
    )

# --- VIEWS ---
class AltTypeSelect(disnake.ui.Select):
    def __init__(self, alt_name, guild_id, language_code):
        self.alt_name = alt_name
        self.guild_id = guild_id
        self.language_code = language_code
        super().__init__(
            placeholder=t("alt.purpose_placeholder", language_code),
            options=[
                disnake.SelectOption(
                    label=t(f"alt.purpose.{p.lower().replace(' ', '_')}", language_code),
                    value=p,
                )
                for p in ALT_PURPOSES
            ],
        )

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        alt_data = {
            "purpose": self.values[0],
            "created_at": firestore.SERVER_TIMESTAMP
        }
        try:
            # Server-Isolated Path
            db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id)).collection("alts").document(self.alt_name).set(alt_data, merge=True)
            await inter.edit_original_message(
                content=t(
                    "alt.registered",
                    self.language_code,
                    alt_name=self.alt_name,
                    purpose=t(f"alt.purpose.{self.values[0].lower().replace(' ', '_')}", self.language_code),
                ),
                view=None
            )
        except Exception as e:
            await inter.edit_original_message(content=t("alt.error", self.language_code, error=e))


class AltTypeView(disnake.ui.View):
    def __init__(self, alt_name, guild_id, language_code):
        super().__init__(timeout=60)
        self.add_item(AltTypeSelect(alt_name, guild_id, language_code))

# --- MODALS ---
class AttackStatsModal(disnake.ui.Modal):
    def __init__(self, target_name: str, is_alt: bool, guild_id: int, language_code: str):
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        self.language_code = language_code
        components = [
            translated_input(language_code, "m_att"),
            translated_input(language_code, "m_def"),
            translated_input(language_code, "m_health"),
            translated_input(language_code, "r_cap"),
            translated_input(language_code, "r_sop"),
        ]
        super().__init__(title=t("stats.attack_title", language_code), components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        path.set({"attack_stats": inter.text_values}, merge=True)
        await inter.edit_original_message(
            content=t("stats.attack_updated", self.language_code, target=self.target_name)
        )

class DefenseStatsModal(disnake.ui.Modal):
    def __init__(self, target_name: str, is_alt: bool, guild_id: int, language_code: str):
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        self.language_code = language_code
        components = [
            translated_input(language_code, "s_def"),
            translated_input(language_code, "s_att"),
            translated_input(language_code, "s_health"),
            translated_input(language_code, "rein_sop"),
        ]
        super().__init__(title=t("stats.defense_title", language_code), components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        path.set({"defence_stats": inter.text_values}, merge=True)
        await inter.edit_original_message(
            content=t("stats.defense_updated", self.language_code, target=self.target_name)
        )


class DragonStatsModal(disnake.ui.Modal):
    def __init__(self, stat_type: str, target_name: str, is_alt: bool, guild_id: int, language_code: str):
        self.stat_type = stat_type
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        self.language_code = language_code

        if stat_type == "attack":
            components = [
                translated_input(language_code, "dragon_m_att"),
                translated_input(language_code, "dragon_m_def"),
                translated_input(language_code, "dragon_m_health"),
                translated_input(language_code, "dragon_att_vs_dragon"),
            ]
            title = t("stats.dragon_attack_title", language_code)
        else:
            components = [
                translated_input(language_code, "dragon_def_player_sop"),
                translated_input(language_code, "dragon_att_player_sop"),
                translated_input(language_code, "dragon_health_player_sop"),
            ]
            title = t("stats.dragon_defense_title", language_code)

        super().__init__(title=title, components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        path = user_ref.collection("alts").document(self.target_name) if self.is_alt else user_ref
        stat_field = "dragon_attack_stats" if self.stat_type == "attack" else "dragon_defense_stats"
        path.set({stat_field: inter.text_values, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        await inter.edit_original_message(
            content=t(f"stats.dragon_{self.stat_type}_updated", self.language_code, target=self.target_name)
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
        language_code: str,
    ):
        self.stat_type = stat_type
        self.target_member_id = target_member_id
        self.target_member_display = target_member_display
        self.target_name = target_name
        self.is_alt = is_alt
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.language_code = language_code

        if stat_type == "attack":
            components = [
                translated_input(language_code, "m_att"),
                translated_input(language_code, "m_def"),
                translated_input(language_code, "m_health"),
                translated_input(language_code, "r_cap"),
                translated_input(language_code, "r_sop"),
            ]
            title = t("stats.attack_title", language_code)
        else:
            components = [
                translated_input(language_code, "s_def"),
                translated_input(language_code, "s_att"),
                translated_input(language_code, "s_health"),
                translated_input(language_code, "rein_sop"),
            ]
            title = t("stats.defense_title", language_code)

        super().__init__(
            title=title,
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
            content=t(
                "stats.proxy_updated",
                self.language_code,
                stat_type=t(f"stats.stat_type.{self.stat_type}", self.language_code),
                member=self.target_member_display,
                target=self.target_name,
            )
        )

# --- COG ---
class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def validate_target(self, inter, target, language_code):
        if target.lower() == "main":
            return True, False

        user_ref = db.collection("guilds").document(str(inter.guild.id)).collection("users").document(str(inter.author.id))
        alt_doc = user_ref.collection("alts").document(target).get()
        
        if alt_doc.exists:
            return True, True
        
        alts_stream = user_ref.collection("alts").stream()
        registered_alts = [a.id for a in alts_stream]
        alt_list_str = ", ".join(registered_alts) if registered_alts else t("stats.none", language_code)
        
        await inter.send(
            content=t(
                "stats.target_invalid",
                language_code,
                target=target,
                alt_list=alt_list_str,
            ),
            ephemeral=True
        )
        return False, False

    @commands.slash_command(description="Register a new Alt account")
    async def add_alt(self, inter: disnake.ApplicationCommandInteraction, name: str):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        await inter.send(
            t("alt.purpose_prompt", language_code, alt_name=name),
            view=AltTypeView(name, inter.guild.id, language_code),
            ephemeral=True,
        )

    @commands.slash_command(description="Update Attack/Rally stats")
    async def update_attack(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(description="Enter 'main' or Alt Name")):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        is_valid, is_alt = await self.validate_target(inter, target, language_code)
        if is_valid:
            await inter.response.send_modal(AttackStatsModal(target, is_alt, inter.guild.id, language_code))

    @commands.slash_command(name="update_defense", description="Update Defense/Stationary stats")
    async def update_defense(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(description="Enter 'main' or Alt Name")):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        is_valid, is_alt = await self.validate_target(inter, target, language_code)
        if is_valid:
            await inter.response.send_modal(DefenseStatsModal(target, is_alt, inter.guild.id, language_code))

    @commands.slash_command(name="update_dragon_attack_stats", description="Update dragon attack stats")
    async def update_dragon_attack_stats(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(default="main", description="Enter 'main' or Alt Name")):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        is_valid, is_alt = await self.validate_target(inter, target, language_code)
        if is_valid:
            await inter.response.send_modal(DragonStatsModal("attack", target, is_alt, inter.guild.id, language_code))

    @commands.slash_command(name="update_dragon_defense_stats", description="Update dragon defense stats")
    async def update_dragon_defense_stats(self, inter: disnake.ApplicationCommandInteraction, target: str = commands.Param(default="main", description="Enter 'main' or Alt Name")):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        is_valid, is_alt = await self.validate_target(inter, target, language_code)
        if is_valid:
            await inter.response.send_modal(DragonStatsModal("defense", target, is_alt, inter.guild.id, language_code))

    @commands.slash_command(description="Admin/Logistics: update a member's stats on their behalf")
    async def add_update(
        self,
        inter: disnake.ApplicationCommandInteraction,
        member: disnake.Member = commands.Param(description="Member whose stats should be updated"),
        stat_type: str = commands.Param(choices=["attack", "defense"], description="Stats to update"),
        target: str = commands.Param(default="main", description="main or an existing alt name"),
    ):
        language_code = get_user_language(inter.guild.id, inter.author.id)
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
                language_code=language_code,
            )
        )

def setup(bot):
    bot.add_cog(Stats(bot))
