import disnake
from disnake.ext import commands
from database import db

# --- POLL VIEW ---
class PollView(disnake.ui.View):
    def __init__(self, question, options):
        super().__init__(timeout=None)
        self.question = question
        self.options = options
        self.votes = {option: 0 for option in options}
        self.voters = set()

    def create_embed(self):
        desc = "\n".join([f"**{opt}**: {count} votes" for opt, count in self.votes.items()])
        embed = disnake.Embed(title=f"📊 {self.question}", description=desc, color=disnake.Color.blue())
        return embed

    @disnake.ui.button(label="Vote", style=disnake.ButtonStyle.blurple)
    async def vote_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        view = VoteDropdownView(self)
        await inter.response.send_message("Select your option:", view=view, ephemeral=True)

    @disnake.ui.button(label="Close Poll", style=disnake.ButtonStyle.red)
    async def close_poll(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        
        # Pulling from server-specific configuration
        guild_data_doc = db.collection("guilds").document(str(inter.guild.id)).get()
        guild_data = guild_data_doc.to_dict() if guild_data_doc.exists else {}
        council_role_id = guild_data.get("council_role")
        
        if not council_role_id or not any(role.id == council_role_id for role in inter.author.roles):
            return await inter.edit_original_message(content="❌ Only Council members can close polls.")

        winner = max(self.votes, key=self.votes.get)
        final_embed = self.create_embed()
        final_embed.title = f"✅ Poll Closed: {self.question}"
        final_embed.add_field(name="Winner", value=f"🏆 **{winner}**", inline=False)
        final_embed.color = disnake.Color.dark_gray()

        await inter.message.edit(embed=final_embed, view=None)
        await inter.edit_original_message(content="Poll closed.")

class VoteDropdownView(disnake.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.add_item(VoteDropdown(parent_view))

class VoteDropdown(disnake.ui.Select):
    def __init__(self, parent_view):
        options = [disnake.SelectOption(label=opt) for opt in parent_view.options]
        super().__init__(placeholder="Choose wisely...", options=options)
        self.parent_view = parent_view

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id in self.parent_view.voters:
            return await inter.response.send_message("❌ You've already voted!", ephemeral=True)
        
        self.parent_view.votes[self.values[0]] += 1
        self.parent_view.voters.add(inter.author.id)
        
        await inter.response.send_message(f"✅ Voted for {self.values[0]}", ephemeral=True)
        await inter.message.edit(embed=self.parent_view.create_embed())

# --- MANAGEMENT COG ---
class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Set the @Council role")
    @commands.has_permissions(administrator=True)
    async def setup_council(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await inter.response.defer(ephemeral=True)
        # Server-Isolated setup
        db.collection("guilds").document(str(inter.guild.id)).set({"council_role": role.id}, merge=True)
        await inter.edit_original_message(content=f"✅ Council role set to {role.mention}")

    @commands.slash_command(description="Set the channel for Council Announcements")
    @commands.has_permissions(administrator=True)
    async def setup_council_announcement(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer(ephemeral=True)
        # Server-Isolated setup
        db.collection("guilds").document(str(inter.guild.id)).set({"announcement_channel": channel.id}, merge=True)
        await inter.edit_original_message(content=f"✅ Announcement channel set to {channel.mention}")

    @commands.slash_command(description="Post a Council Announcement")
    async def council_announcement(self, inter: disnake.ApplicationCommandInteraction, message: str):
        await inter.response.defer(ephemeral=True)
        
        guild_doc = db.collection("guilds").document(str(inter.guild.id)).get()
        guild_data = guild_doc.to_dict() if guild_doc.exists else {}
        council_role_id = guild_data.get("council_role")
        
        if not council_role_id or not any(role.id == council_role_id for role in inter.author.roles):
            return await inter.edit_original_message(content="❌ Access Denied: Council Role required.")

        channel_id = guild_data.get("announcement_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return await inter.edit_original_message(content="❌ Announcement channel not configured.")

        embed = disnake.Embed(title="📢 Council Announcement", description=message, color=disnake.Color.gold())
        embed.set_footer(text=f"Sent by {inter.author.display_name}")
        await channel.send(content="@everyone", embed=embed)
        await inter.edit_original_message(content="✅ Announcement sent.")

    @commands.slash_command(description="Create a poll with multiple options (comma separated)")
    async def create_poll(self, inter: disnake.ApplicationCommandInteraction, question: str, options: str):
        option_list = [opt.strip() for opt in options.split(",")]
        if len(option_list) < 2:
            return await inter.send("❌ Need at least 2 options.", ephemeral=True)
        
        view = PollView(question, option_list)
        # No defer needed here for local ephemeral send, but final channel post is public
        await inter.send("Poll started!", ephemeral=True)
        await inter.channel.send(embed=view.create_embed(), view=view)

def setup(bot):
    bot.add_cog(Management(bot))