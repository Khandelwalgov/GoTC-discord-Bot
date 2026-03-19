import disnake
from disnake.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
intents = disnake.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Load Cogs
for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

bot.run(os.getenv('DISCORD_TOKEN'))