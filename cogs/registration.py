import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore
import pytz

# --- VIEWS (DROPDOWNS) ---
class TierView(disnake.ui.View):
    def __init__(self, ign, timezone):
        super().__init__(timeout=60)
        self.ign = ign
        self.timezone = timezone

    @disnake.ui.string_select(
        placeholder="Select your Troop Tier...",
        options=[disnake.SelectOption(label=f"Tier {i}", value=f"T{i}") for i in range(1, 13)]
    )
    async def select_tier(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)

        tier = select.values[0]
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
                content=f"✅ **Registration Complete!**\n**IGN:** {self.ign}\n**Tier:** {tier}\n**TZ:** {self.timezone}\n\nUse `/add_access` to tag friends or `/update_stats` for combat data.",
                view=None
            )
        except Exception as e:
            await inter.edit_original_message(content=f"❌ **Database Error:** {e}")

class AccessRemoveView(disnake.ui.View):
    def __init__(self, access_list, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        options = [disnake.SelectOption(label=f"User ID: {uid}", value=uid) for uid in access_list[:25]]
        self.add_item(AccessRemoveSelect(options, guild_id))

class AccessRemoveSelect(disnake.ui.Select):
    def __init__(self, options, guild_id):
        super().__init__(placeholder="Select a user to remove access...", options=options)
        self.guild_id = guild_id

    async def callback(self, inter: disnake.MessageInteraction):
        uid = self.values[0]
        user_ref = db.collection("guilds").document(str(self.guild_id)).collection("users").document(str(inter.author.id))
        
        user_ref.update({
            "access_list": firestore.ArrayRemove([uid])
        })
        await inter.response.edit_message(content=f"✅ Access removed for UID: {uid}", view=None)

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
        if timezone not in pytz.all_timezones:
            return await inter.send(
                f"❌ `{timezone}` is not a valid timezone. Please select one from the autocomplete list!", 
                ephemeral=True
            )
        
        view = TierView(ign=in_game_name, timezone=timezone)
        await inter.send("Final Step: Select your **Troop Tier**:", view=view, ephemeral=True)

    @register.autocomplete("timezone")
    async def tz_autocomplete(self, inter: disnake.ApplicationCommandInteraction, string: str):
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
        user_ref = self.get_user_ref(inter)
        user_ref.set({
            "access_list": firestore.ArrayUnion([str(member.id)]),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        
        embed = disnake.Embed(
            description=f"🏰 **Keep Access Granted** to {member.mention}",
            color=disnake.Color.blue()
        )
        await inter.send(embed=embed, ephemeral=True)

    @commands.slash_command(description="View and remove Keep access permissions")
    async def update_access(self, inter: disnake.ApplicationCommandInteraction):
        user_ref = self.get_user_ref(inter)
        user_data = user_ref.get().to_dict() or {}
        access_list = user_data.get("access_list", [])
        
        if not access_list:
            return await inter.send("❌ Your access list is empty.", ephemeral=True)
        
        await inter.send("Who do you want to remove?", view=AccessRemoveView(access_list, inter.guild.id), ephemeral=True)

    @commands.slash_command(description="Update IGN for your Main or Alts")
    async def update_name(self, inter: disnake.ApplicationCommandInteraction, current_name: str, new_name: str):
        user_ref = self.get_user_ref(inter)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return await inter.send("❌ You are not registered yet. Use `/register`.", ephemeral=True)
            
        user_data = user_doc.to_dict()

        # Check Main Account
        if user_data.get("ign", "").lower() == current_name.lower():
            user_ref.update({"ign": new_name, "updated_at": firestore.SERVER_TIMESTAMP})
            return await inter.send(f"✅ Main IGN updated to **{new_name}**", ephemeral=True)

        # Check Alts
        alt_ref = user_ref.collection("alts").document(current_name)
        alt_doc = alt_ref.get()
        if alt_doc.exists:
            alt_data = alt_doc.to_dict()
            user_ref.collection("alts").document(new_name).set(alt_data)
            alt_ref.delete()
            return await inter.send(f"✅ Alt **{current_name}** renamed to **{new_name}**", ephemeral=True)

        await inter.send(f"❌ Record for **{current_name}** not found.", ephemeral=True)

def setup(bot):
    bot.add_cog(Registration(bot))
