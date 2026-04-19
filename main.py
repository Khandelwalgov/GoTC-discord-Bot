import disnake
from disnake.ext import commands
import os
from dotenv import load_dotenv
from threading import Thread
from flask import Flask

# --- WEB SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Steward is Online!"

@app.route('/health')
def health():
    return "OK", 200

def run_web():
    # Render provides a PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- BOT LOGIC ---
load_dotenv()
intents = disnake.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Load Cogs (Your existing logic)
for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Start web server before running the bot
keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))