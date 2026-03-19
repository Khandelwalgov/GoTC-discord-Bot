import disnake
from disnake.ext import commands
from database import db

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Moderation commands")
    @commands.has_permissions(kick_members=True)
    # FIX: Ensure parameters without defaults come BEFORE those with defaults, 
    # OR give them all a default using commands.Param
    async def mod(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        action: str = commands.Param(choices=["kick", "ban"]), 
        member: disnake.Member = commands.Param(description="The user to mod"), 
        reason: str = commands.Param(default="No reason provided")
    ):
        if action == "kick":
            await member.kick(reason=reason)
        else:
            await member.ban(reason=reason)
        await inter.send(f"✅ {action.capitalize()}ed {member.display_name} | Reason: {reason}", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_data = db.collection("guilds").document(str(member.guild.id)).get().to_dict()
        if guild_data and "logs_channel" in guild_data:
            channel = self.bot.get_channel(guild_data["logs_channel"])
            if channel:
                embed = disnake.Embed(
                    title="New Member", 
                    description=f"{member.mention} joined the battlefield.", 
                    color=disnake.Color.gold()
                )
                await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Admin(bot))