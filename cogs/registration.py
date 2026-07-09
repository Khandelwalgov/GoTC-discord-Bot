import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore
import pytz
from services.access_control import has_logistics_access, logistics_denied_message
from services.translation import get_user_language, t

# --- VIEWS (DROPDOWNS) ---
class TierSelect(disnake.ui.Select):
    def __init__(self, ign, timezone, language_code):
        self.ign = ign
        self.timezone = timezone
        self.language_code = language_code
        super().__init__(
            placeholder=t("register.tier_placeholder", language_code),
            options=[disnake.SelectOption(label=f"Tier {i}", value=f"T{i}") for i in range(1, 13)],
        )

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)

        tier = self.values[0]
        data = {
            "ign": self.ign,
            "tier": tier,
            "timezone": self.timezone,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        try:
            # SAVING TO: guilds/{guild_id}/users/{user_id}
            user_ref = db.collection("guilds").document(str(inter.guild.id)).collection("users").document(str(inter.author.id))
            user_ref.set(data, merge=True)
            
            await inter.edit_original_message(
                content=t(
                    "register.complete",
                    self.language_code,
                    ign=self.ign,
                    tier=tier,
                    timezone=self.timezone,
                ),
                view=None
            )
        except Exception as e:
            await inter.edit_original_message(
                content=t("register.database_error", self.language_code, error=e)
            )


class TierView(disnake.ui.View):
    def __init__(self, ign, timezone, language_code):
        super().__init__(timeout=60)
        self.add_item(TierSelect(ign, timezone, language_code))

class AccessRemoveView(disnake.ui.View):
    def __init__(self, access_list, guild_id, language_code):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        options = [
            disnake.SelectOption(
                label=t("access.user_id_option", language_code, uid=uid),
                value=uid,
            )
            for uid in access_list[:25]
        ]
        self.add_item(AccessRemoveSelect(options, guild_id, language_code))

class AccessRemoveSelect(disnake.ui.Select):
    def __init__(self, options, guild_id, language_code):
        super().__init__(placeholder=t("access.remove_placeholder", language_code), options=options)
        self.guild_id = guild_id
        self.language_code = language_code

    async def callback(self, inter: disnake.MessageInteraction):
        uid = self.values[0]
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        
        user_ref.update({
            "access_list": firestore.ArrayRemove([uid])
        })
        await inter.response.edit_message(
            content=t("access.removed", self.language_code, uid=uid),
            view=None,
        )

# --- COG CLASS ---
class Registration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_ref(self, inter):
        """Helper to get the server-specific user reference"""
        return db.collection("guilds").document(str(inter.guild.id)).collection("users").document(str(inter.author.id))

    # 1. MAIN REGISTRATION WITH AUTOCOMPLETE
    @commands.slash_command(description="Start your GoTC profile registration")
    async def register(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        in_game_name: str = commands.Param(description="Your exact GoTC name"),
        timezone: str = commands.Param(description="Type your city/region (e.g. Kolkata)")
    ):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        if timezone not in pytz.all_timezones:
            return await inter.send(
                t("register.invalid_timezone", language_code, timezone=timezone),
                ephemeral=True
            )
        
        view = TierView(ign=in_game_name, timezone=timezone, language_code=language_code)
        await inter.send(t("register.select_tier_prompt", language_code), view=view, ephemeral=True)

    @register.autocomplete("timezone")
    async def tz_autocomplete(self, inter: disnake.ApplicationCommandInteraction, string: str):
        string = string.lower()
        choices = [tz for tz in pytz.common_timezones if string in tz.lower()]
        return choices[:25]

    @commands.slash_command(description="Admin/Logistics: register a member on their behalf")
    async def add_register(
        self,
        inter: disnake.ApplicationCommandInteraction,
        member: disnake.Member = commands.Param(description="Member to register"),
        in_game_name: str = commands.Param(description="Their exact GoTC name"),
        timezone: str = commands.Param(description="Timezone, e.g. Asia/Kolkata"),
        tier: str = commands.Param(choices=[f"T{i}" for i in range(1, 13)], description="Troop tier"),
    ):
        if not has_logistics_access(inter):
            return await inter.send(logistics_denied_message(), ephemeral=True)

        if timezone not in pytz.all_timezones:
            return await inter.send(
                f"`{timezone}` is not a valid timezone. Pick one from autocomplete.",
                ephemeral=True,
            )

        user_ref = (
            db.collection("guilds")
            .document(str(inter.guild.id))
            .collection("users")
            .document(str(member.id))
        )
        user_ref.set(
            {
                "ign": in_game_name,
                "tier": tier,
                "timezone": timezone,
                "registered_by": str(inter.author.id),
                "registered_via": "admin_proxy",
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.send(
            f"Registered {member.mention} as **{in_game_name}** / **{tier}** / **{timezone}**.",
            ephemeral=True,
        )

    @add_register.autocomplete("timezone")
    async def add_register_tz_autocomplete(self, inter: disnake.ApplicationCommandInteraction, string: str):
        string = string.lower()
        choices = [tz for tz in pytz.common_timezones if string in tz.lower()]
        return choices[:25]

    # 2. PROPER USER TAGGING (KEEP ACCESS)
    @commands.slash_command(description="Grant a user access to your Keep")
    async def add_access(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        member: disnake.Member = commands.Param(description="Tag the user you want to add")
    ):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        user_ref = self.get_user_ref(inter)
        user_ref.set({
            "access_list": firestore.ArrayUnion([str(member.id)]),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        
        embed = disnake.Embed(
            description=t("access.granted", language_code, member=member.mention),
            color=disnake.Color.blue()
        )
        await inter.send(embed=embed, ephemeral=True)

    @commands.slash_command(description="View and remove Keep access permissions")
    async def update_access(self, inter: disnake.ApplicationCommandInteraction):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        user_ref = self.get_user_ref(inter)
        user_data = user_ref.get().to_dict() or {}
        access_list = user_data.get("access_list", [])
        
        if not access_list:
            return await inter.send(t("access.empty", language_code), ephemeral=True)
        
        await inter.send(
            t("access.remove_prompt", language_code),
            view=AccessRemoveView(access_list, inter.guild.id, language_code),
            ephemeral=True,
        )

    @commands.slash_command(description="Update IGN for your Main or Alts")
    async def update_name(self, inter: disnake.ApplicationCommandInteraction, current_name: str, new_name: str):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        user_ref = self.get_user_ref(inter)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return await inter.send(t("update_name.not_registered", language_code), ephemeral=True)
            
        user_data = user_doc.to_dict()

        # Check Main Account
        if user_data.get("ign", "").lower() == current_name.lower():
            user_ref.update({"ign": new_name, "updated_at": firestore.SERVER_TIMESTAMP})
            return await inter.send(t("update_name.main_updated", language_code, new_name=new_name), ephemeral=True)

        # Check Alts
        alt_ref = user_ref.collection("alts").document(current_name)
        alt_doc = alt_ref.get()
        if alt_doc.exists:
            alt_data = alt_doc.to_dict()
            user_ref.collection("alts").document(new_name).set(alt_data)
            alt_ref.delete()
            return await inter.send(
                t("update_name.alt_updated", language_code, current_name=current_name, new_name=new_name),
                ephemeral=True,
            )

        await inter.send(t("update_name.not_found", language_code, current_name=current_name), ephemeral=True)

def setup(bot):
    bot.add_cog(Registration(bot))
