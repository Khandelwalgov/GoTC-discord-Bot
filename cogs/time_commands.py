import disnake
from disnake.ext import commands
from database import db
import pytz
from datetime import datetime, time, timedelta
from services.translation import get_user_language, t

class TimeStuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_tz(self, guild_id, user_id):
        doc = (
            db.collection("guilds")
            .document(str(guild_id))
            .collection("users")
            .document(str(user_id))
            .get()
        )
        if doc.exists:
            return doc.to_dict().get("timezone", "UTC")
        return "UTC"

    # --- AUTOCOMPLETE FOR DATES ---
    @disnake.ext.commands.Cog.listener()
    async def on_ready(self):
        print("Time Cog Loaded: Date Autocomplete Ready")

    async def date_autocomplete(self, inter, string: str):
        tz_str = await self.get_user_tz(inter.guild.id, inter.author.id)
        user_tz = pytz.timezone(tz_str)
        now = datetime.now(user_tz)
        
        # Generate next 7 days
        options = []
        for i in range(8):
            day = now + timedelta(days=i)
            label = day.strftime("%A, %b %d") # e.g. "Saturday, Mar 21"
            value = day.strftime("%Y-%m-%d")  # e.g. "2026-03-21"
            if string.lower() in label.lower():
                options.append(disnake.OptionChoice(name=label, value=value))
        return options

    # --- 24 HOUR COMMAND ---
    @commands.slash_command(description="Share a time in 24h format with a date and message")
    async def time24(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        hhmm: str = commands.Param(description="Format: 1730"),
        date_input: str = commands.Param(description="Select the date", autocomplete=True),
        extra_text: str = commands.Param(default="", description="Message to include (e.g. 'Rally at')")
    ):
        await inter.response.defer()
        language_code = get_user_language(inter.guild.id, inter.author.id)
        tz_str = await self.get_user_tz(inter.guild.id, inter.author.id)
        user_tz = pytz.timezone(tz_str)

        try:
            h, m = int(hhmm[:2]), int(hhmm[2:])
            target_date = datetime.strptime(date_input, "%Y-%m-%d").date()
            dt = user_tz.localize(datetime.combine(target_date, time(h, m)))
            unix = int(dt.timestamp())
            
            await inter.edit_original_message(
                content=f"{extra_text} <t:{unix}:F> (<t:{unix}:R>)"
            )
        except Exception:
            await inter.edit_original_message(content=t("time.error_24", language_code))

    # --- 12 HOUR COMMAND ---
    @commands.slash_command(description="Share a time in 12h format with a date and message")
    async def time12(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        time_input: str = commands.Param(description="Format: 5:30pm"),
        date_input: str = commands.Param(description="Select the date", autocomplete=True),
        extra_text: str = commands.Param(default="", description="Message to include (e.g. 'Rally at')")
    ):
        await inter.response.defer()
        language_code = get_user_language(inter.guild.id, inter.author.id)
        tz_str = await self.get_user_tz(inter.guild.id, inter.author.id)
        user_tz = pytz.timezone(tz_str)

        try:
            parsed_time = datetime.strptime(time_input.lower().replace(" ", ""), "%I:%M%p").time()
        except:
            try:
                parsed_time = datetime.strptime(time_input.lower().replace(" ", ""), "%I%p").time()
            except:
                return await inter.edit_original_message(content=t("time.error_12_format", language_code))

        try:
            target_date = datetime.strptime(date_input, "%Y-%m-%d").date()
            dt = user_tz.localize(datetime.combine(target_date, parsed_time))
            unix = int(dt.timestamp())
            
            await inter.edit_original_message(
                content=f"{extra_text} <t:{unix}:F> (<t:{unix}:R>)"
            )
        except Exception:
            await inter.edit_original_message(content=t("time.error_date", language_code))

    # Linking autocompletes
    @time24.autocomplete("date_input")
    async def t24_date_auto(self, inter, string): return await self.date_autocomplete(inter, string)
    
    @time12.autocomplete("date_input")
    async def t12_date_auto(self, inter, string): return await self.date_autocomplete(inter, string)

def setup(bot):
    bot.add_cog(TimeStuff(bot))
