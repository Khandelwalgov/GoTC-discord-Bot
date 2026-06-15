import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore


def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))


def load_guild_config(guild_id):
    doc = guild_ref(guild_id).get()
    return doc.to_dict() if doc.exists else {}


def can_assign_role(guild, role):
    bot_member = guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles:
        return False, "I need the Manage Roles permission before I can assign autoroles."
    if role == guild.default_role:
        return False, "I cannot configure @everyone as an autorole."
    if role.managed:
        return False, "That role is managed by an integration or bot and cannot be assigned manually."
    if role >= bot_member.top_role:
        return False, "That role must be moved below Steward's highest role before I can assign it."
    return True, None


async def get_log_channel(bot, guild, config):
    channel_id = config.get("logs_channel")
    if not channel_id:
        return None
    return bot.get_channel(int(channel_id)) or guild.get_channel(int(channel_id))


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="moderate", description="Kick or ban a member")
    @commands.has_permissions(kick_members=True)
    async def mod(
        self,
        inter: disnake.ApplicationCommandInteraction,
        action: str = commands.Param(choices=["kick", "ban"]),
        member: disnake.Member = commands.Param(description="The user to mod"),
        reason: str = commands.Param(default="No reason provided"),
    ):
        if action == "kick":
            await member.kick(reason=reason)
        else:
            await member.ban(reason=reason)
        embed = disnake.Embed(
            title="Moderation Action",
            description=f"**{action.capitalize()}ed:** {member.mention}\n**Reason:** {reason}",
            color=disnake.Color.dark_red(),
        )
        await inter.send(embed=embed, ephemeral=True)

    @commands.slash_command(name="set_logs_channel", description="Set the server join/leave log channel")
    @commands.has_permissions(manage_guild=True)
    async def set_logs_channel(self, inter, channel: disnake.TextChannel):
        guild_ref(inter.guild.id).set(
            {
                "logs_channel": channel.id,
                "settings_updated_by": str(inter.author.id),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.send(f"Server logs will now be sent to {channel.mention}.", ephemeral=True)

    @commands.slash_command(name="disable_logs_channel", description="Disable server join/leave logs")
    @commands.has_permissions(manage_guild=True)
    async def disable_logs_channel(self, inter):
        guild_ref(inter.guild.id).set(
            {
                "logs_channel": None,
                "settings_updated_by": str(inter.author.id),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.send("Server join/leave logs disabled.", ephemeral=True)

    @commands.slash_command(name="set_autorole", description="Set an existing role for new members")
    @commands.has_permissions(manage_guild=True)
    async def set_autorole(
        self,
        inter,
        role: disnake.Role,
        enabled: bool = commands.Param(default=True),
    ):
        ok, error = can_assign_role(inter.guild, role)
        if not ok:
            return await inter.send(error, ephemeral=True)

        guild_ref(inter.guild.id).set(
            {
                "autorole_id": role.id,
                "autorole_enabled": enabled,
                "settings_updated_by": str(inter.author.id),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        state = "will receive" if enabled else "will not receive until re-enabled"
        await inter.send(
            f"Autorole set to {role.mention}. New members {state} this role automatically.",
            ephemeral=True,
        )

    @commands.slash_command(name="disable_autorole", description="Disable automatic role assignment")
    @commands.has_permissions(manage_guild=True)
    async def disable_autorole(self, inter):
        guild_ref(inter.guild.id).set(
            {
                "autorole_enabled": False,
                "settings_updated_by": str(inter.author.id),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.send("Autorole disabled.", ephemeral=True)

    @commands.slash_command(name="server_settings", description="Show Steward server settings")
    @commands.has_permissions(manage_guild=True)
    async def server_settings(self, inter):
        config = load_guild_config(inter.guild.id)
        logs_channel = inter.guild.get_channel(int(config["logs_channel"])) if config.get("logs_channel") else None
        autorole = inter.guild.get_role(int(config["autorole_id"])) if config.get("autorole_id") else None
        embed = disnake.Embed(title="Server Settings", color=disnake.Color.gold())
        embed.add_field(name="Logs Channel", value=logs_channel.mention if logs_channel else "Disabled", inline=False)
        embed.add_field(name="Autorole", value=autorole.mention if autorole else "Not set", inline=False)
        embed.add_field(
            name="Autorole Enabled",
            value="Yes" if config.get("autorole_enabled") else "No",
            inline=False,
        )
        await inter.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = load_guild_config(member.guild.id)
        if not config:
            return

        channel = await get_log_channel(self.bot, member.guild, config)
        autorole_status = "skipped"

        if config.get("autorole_enabled") and config.get("autorole_id"):
            role = member.guild.get_role(int(config["autorole_id"]))
            if role:
                ok, error = can_assign_role(member.guild, role)
                if ok:
                    try:
                        await member.add_roles(role, reason="Steward autorole")
                        autorole_status = f"assigned {role.name}"
                    except (disnake.Forbidden, disnake.HTTPException):
                        autorole_status = "failed"
                        if channel:
                            await channel.send(f"Autorole failed for {member.mention}: could not assign `{role.name}`.")
                else:
                    autorole_status = "failed"
                    if channel:
                        await channel.send(f"Autorole failed for {member.mention}: {error}")
            else:
                autorole_status = "failed"
                if channel:
                    await channel.send(f"Autorole failed for {member.mention}: configured role no longer exists.")

        if not channel:
            return

        embed = disnake.Embed(
            title="Member Joined",
            description=f"{member.mention}\n{member}",
            color=disnake.Color.green(),
        )
        embed.add_field(name="User ID", value=str(member.id), inline=False)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:F>", inline=False)
        embed.add_field(name="Autorole", value=autorole_status, inline=False)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = load_guild_config(member.guild.id)
        if not config:
            return
        channel = await get_log_channel(self.bot, member.guild, config)
        if not channel:
            return

        embed = disnake.Embed(
            title="Member Left",
            description=str(member),
            color=disnake.Color.dark_red(),
        )
        embed.add_field(name="User ID", value=str(member.id), inline=False)
        if member.joined_at:
            embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=False)
        await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Admin(bot))
