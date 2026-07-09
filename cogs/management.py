import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore
from services.public_translation import add_translate_button, register_translatable_message


def guild_ref(guild_id: int):
    return db.collection("guilds").document(str(guild_id))


def poll_ref(guild_id: int, poll_id: str):
    return guild_ref(guild_id).collection("polls").document(str(poll_id))


def build_poll_embed(poll_data: dict, closed: bool = False):
    question = poll_data.get("question", "Council Poll")
    options = poll_data.get("options", [])
    votes = poll_data.get("votes", {}) or {}

    counts = {option: 0 for option in options}
    for choice in votes.values():
        if choice in counts:
            counts[choice] += 1

    lines = [f"**{option}**: {counts.get(option, 0)} votes" for option in options]
    embed = disnake.Embed(
        title=f"{'Poll Closed' if closed else 'Council Poll'}: {question}",
        description="\n".join(lines) or "No options configured.",
        color=disnake.Color.dark_gray() if closed else disnake.Color.blue(),
    )

    if closed:
        if counts:
            top_score = max(counts.values())
            winners = [option for option, count in counts.items() if count == top_score]
            embed.add_field(name="Winner", value=", ".join(winners), inline=False)
        embed.set_footer(text=f"Total votes: {len(votes)}")
    else:
        embed.set_footer(text="Use the Vote button to choose an option.")

    return embed


async def author_has_council_role(inter: disnake.MessageInteraction):
    guild_doc = guild_ref(inter.guild.id).get()
    guild_data = guild_doc.to_dict() if guild_doc.exists else {}
    council_role_id = guild_data.get("council_role")
    if not council_role_id:
        return False
    return any(role.id == council_role_id for role in inter.author.roles)


class PollView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        add_translate_button(self)

    @disnake.ui.button(
        label="Vote",
        style=disnake.ButtonStyle.blurple,
        custom_id="steward_poll_vote",
    )
    async def vote_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        poll_doc = poll_ref(inter.guild.id, str(inter.message.id)).get()
        if not poll_doc.exists:
            return await inter.response.send_message(
                "This poll is no longer available.",
                ephemeral=True,
            )

        poll_data = poll_doc.to_dict() or {}
        if poll_data.get("status") == "closed":
            return await inter.response.send_message("This poll is already closed.", ephemeral=True)

        options = poll_data.get("options", [])
        if len(options) < 2:
            return await inter.response.send_message(
                "This poll has no valid options configured.",
                ephemeral=True,
            )

        await inter.response.send_message(
            "Select your option:",
            view=VoteDropdownView(inter.guild.id, str(inter.message.id), options),
            ephemeral=True,
        )

    @disnake.ui.button(
        label="Close Poll",
        style=disnake.ButtonStyle.red,
        custom_id="steward_poll_close",
    )
    async def close_poll(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)

        if not await author_has_council_role(inter):
            return await inter.edit_original_message(
                content="Only Council members can close polls.",
            )

        ref = poll_ref(inter.guild.id, str(inter.message.id))
        poll_doc = ref.get()
        if not poll_doc.exists:
            return await inter.edit_original_message(content="This poll is no longer available.")

        poll_data = poll_doc.to_dict() or {}
        poll_data["status"] = "closed"
        ref.set(
            {
                "status": "closed",
                "closed_by": str(inter.author.id),
                "closed_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        await inter.message.edit(embed=build_poll_embed(poll_data, closed=True), view=None)
        await inter.edit_original_message(content="Poll closed.")


class VoteDropdownView(disnake.ui.View):
    def __init__(self, guild_id: int, poll_id: str, options: list[str]):
        super().__init__(timeout=60)
        self.add_item(VoteDropdown(guild_id, poll_id, options))


class VoteDropdown(disnake.ui.Select):
    def __init__(self, guild_id: int, poll_id: str, options: list[str]):
        self.guild_id = guild_id
        self.poll_id = poll_id
        select_options = [disnake.SelectOption(label=option, value=option) for option in options[:25]]
        super().__init__(
            placeholder="Choose wisely...",
            options=select_options,
            custom_id=f"steward_poll_select_{poll_id}",
        )

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)

        ref = poll_ref(self.guild_id, self.poll_id)
        poll_doc = ref.get()
        if not poll_doc.exists:
            return await inter.edit_original_message(content="This poll is no longer available.", view=None)

        poll_data = poll_doc.to_dict() or {}
        if poll_data.get("status") == "closed":
            return await inter.edit_original_message(content="This poll is already closed.", view=None)

        votes = poll_data.get("votes", {}) or {}
        user_id = str(inter.author.id)
        if user_id in votes:
            return await inter.edit_original_message(content="You have already voted.", view=None)

        choice = self.values[0]
        votes[user_id] = choice
        poll_data["votes"] = votes
        ref.set(
            {
                "votes": votes,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        await inter.edit_original_message(content=f"Voted for {choice}.", view=None)

        channel_id = poll_data.get("channel_id")
        message_id = poll_data.get("message_id")
        channel = inter.guild.get_channel(int(channel_id)) if channel_id else None
        if channel and message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=build_poll_embed(poll_data), view=PollView())
            except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
                pass


class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.views_registered = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.views_registered:
            return
        self.bot.add_view(PollView())
        self.views_registered = True

    @commands.slash_command(description="Set the @Council role")
    @commands.has_permissions(administrator=True)
    async def setup_council(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await inter.response.defer(ephemeral=True)
        guild_ref(inter.guild.id).set({"council_role": role.id}, merge=True)
        await inter.edit_original_message(content=f"Council role set to {role.mention}")

    @commands.slash_command(name="setup_logistics", description="Set the Logistics role")
    @commands.has_permissions(administrator=True)
    async def setup_logistics(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await inter.response.defer(ephemeral=True)
        guild_ref(inter.guild.id).set(
            {
                "logistics_role": role.id,
                "settings_updated_by": str(inter.author.id),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        await inter.edit_original_message(
            content=f"Logistics role set to {role.mention}. This role can use admin-proxy and roster management commands."
        )

    @commands.slash_command(name="setup_announcements", description="Set the channel for council announcements")
    @commands.has_permissions(administrator=True)
    async def setup_council_announcement(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
    ):
        await inter.response.defer(ephemeral=True)
        guild_ref(inter.guild.id).set({"announcement_channel": channel.id}, merge=True)
        await inter.edit_original_message(content=f"Announcement channel set to {channel.mention}")

    @commands.slash_command(name="announce", description="Send a council announcement")
    async def council_announcement(self, inter: disnake.ApplicationCommandInteraction, message: str):
        await inter.response.defer(ephemeral=True)

        guild_doc = guild_ref(inter.guild.id).get()
        guild_data = guild_doc.to_dict() if guild_doc.exists else {}
        council_role_id = guild_data.get("council_role")

        if not council_role_id or not any(role.id == council_role_id for role in inter.author.roles):
            return await inter.edit_original_message(content="Access denied: Council role required.")

        channel_id = guild_data.get("announcement_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return await inter.edit_original_message(content="Announcement channel is not configured.")

        embed = disnake.Embed(title="Council Announcement", description=message, color=disnake.Color.gold())
        embed.set_footer(text=f"Sent by {inter.author.display_name}")
        await channel.send(content="@everyone", embed=embed)
        await inter.edit_original_message(content="Announcement sent.")

    @commands.slash_command(name="poll", description="Create a Firestore-backed poll")
    async def create_poll(self, inter: disnake.ApplicationCommandInteraction, question: str, options: str):
        option_list = []
        seen = set()
        for raw_option in options.split(","):
            option = raw_option.strip()
            if option and option.lower() not in seen:
                seen.add(option.lower())
                option_list.append(option[:100])

        if len(option_list) < 2:
            return await inter.send("Need at least 2 unique options.", ephemeral=True)
        if len(option_list) > 25:
            return await inter.send("Discord supports up to 25 options in this poll.", ephemeral=True)

        poll_data = {
            "question": question[:256],
            "options": option_list,
            "votes": {},
            "status": "open",
            "guild_id": str(inter.guild.id),
            "channel_id": str(inter.channel.id),
            "created_by": str(inter.author.id),
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        message = await inter.channel.send(embed=build_poll_embed(poll_data), view=PollView())
        poll_data["message_id"] = str(message.id)
        poll_ref(inter.guild.id, str(message.id)).set(poll_data, merge=True)
        register_translatable_message(inter.guild.id, message, "poll")
        await inter.send("Poll started.", ephemeral=True)


def setup(bot):
    bot.add_cog(Management(bot))
