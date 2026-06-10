import disnake
from disnake.ext import commands


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)


COMMANDS = {
    "profile": {
        "title": "Profile",
        "commands": [
            ("/register", "Create or update your GoTC profile."),
            ("/add_alt", "Add an alt under your account."),
            ("/update_name", "Rename your main or an alt."),
            ("/add_access", "Grant someone keep access."),
            ("/update_access", "Remove keep access from your list."),
        ],
    },
    "stats": {
        "title": "Stats",
        "commands": [
            ("/update_attack", "Update marching and rally stats."),
            ("/update_defence", "Update stationary and reinforcement stats."),
            ("/get_stats", "Look up recorded combat stats."),
            ("/export_roster", "Export roster data to CSV or a message."),
        ],
    },
    "coordination": {
        "title": "Coordination",
        "commands": [
            ("/time12", "Post a 12-hour time as a Discord timestamp."),
            ("/time24", "Post a 24-hour time as a Discord timestamp."),
            ("/poll", "Create a Firestore-backed council poll."),
            ("/availability_check", "Post the weekend availability panel."),
            ("/availability_report", "Show availability by slot."),
            ("/create_battlegrounds_event", "Create a BG signup with reminders."),
        ],
    },
    "council": {
        "title": "Council",
        "commands": [
            ("/lookup_account", "View owner, alts, and keep access."),
            ("/bubble_up", "Ping an owner and their access list."),
            ("/announce", "Send a council announcement."),
            ("/setup_council", "Set the council role."),
            ("/setup_announcements", "Set the announcement channel."),
        ],
    },
    "setup": {
        "title": "Setup",
        "commands": [
            ("/setup_gotc_roles", "Create or verify all GoTC roles."),
            ("/post_role_panel", "Post troop, type, specialist, and dragon panels."),
            ("/post_battleground_ping_panel", "Post BG ping opt-in buttons."),
            ("/moderate", "Kick or ban a member."),
        ],
    },
}


DETAILS = {
    "register": (
        "Create your profile",
        "`/register in_game_name:<IGN> timezone:<Region/City>`",
        "Stores your profile inside this Discord server only. Timezone autocomplete keeps event times accurate.",
    ),
    "add_alt": (
        "Add an alt",
        "`/add_alt name:<AltIGN>`",
        "Adds an alt under your profile and asks for its purpose using a dropdown.",
    ),
    "add_access": (
        "Grant keep access",
        "`/add_access member:@User`",
        "Adds someone to your keep access list so council can bubble the right people.",
    ),
    "poll": (
        "Create a poll",
        "`/poll question:<text> options:<A, B, C>`",
        "Creates a live poll whose votes are stored in Firestore, so Render restarts do not wipe results.",
    ),
    "availability_check": (
        "Start availability check",
        "`/availability_check`",
        "Clears old weekend availability roles and posts a fresh panel. Open, Mid-Shift, and Close can stack; Throughout and Absent are exclusive.",
    ),
    "post_role_panel": (
        "Post role panels",
        "`/post_role_panel`",
        "Posts persistent role selection panels for troop tier, primary type, specialist roles, and dragon level.",
    ),
    "post_battleground_ping_panel": (
        "Post BG opt-in panel",
        "`/post_battleground_ping_panel`",
        "Posts buttons for all battleground pings, Titans of the North, and The Great Ranging.",
    ),
    "create_battlegrounds_event": (
        "Create battleground event",
        "`/create_battlegrounds_event type:<Titans/The Great Ranging> time:<8pm or 2030>`",
        "Uses your registered timezone, posts a signup list, and reminds signed-up players 60, 30, 15, and 0 minutes before start.",
    ),
    "export_roster": (
        "Export roster data",
        "`/export_roster format:CSV include_alts:True stat_columns:Full Combat Stats`",
        "Builds a roster export from Firestore. CSV is best when council wants to sort or share data.",
    ),
}


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="help", description="Open the Steward command guide")
    async def help(
        self,
        inter: disnake.ApplicationCommandInteraction,
        command: str = commands.Param(default=None, description="Optional command name for details"),
    ):
        await inter.response.defer(ephemeral=True)

        if command:
            command_name = command.lower().replace("/", "").strip()
            if command_name in DETAILS:
                title, usage, details = DETAILS[command_name]
                embed = disnake.Embed(title=f"/{command_name}: {title}", color=BRAND_COLOR)
                embed.add_field(name="Usage", value=usage, inline=False)
                embed.add_field(name="Details", value=details, inline=False)
                return await inter.edit_original_message(embed=embed)

            return await inter.edit_original_message(
                content=f"I do not have a detailed card for `/{command_name}` yet. Try `/help` for the full menu."
            )

        embed = disnake.Embed(
            title="Steward Command Guide",
            description="Server-isolated GoTC coordination, roles, profiles, stats, and council tools.",
            color=BRAND_COLOR,
        )

        for section in COMMANDS.values():
            lines = [f"`{name}` - {description}" for name, description in section["commands"]]
            embed.add_field(name=section["title"], value="\n".join(lines), inline=False)

        embed.set_footer(text="Tip: use /help command:poll for a focused command card.")
        await inter.edit_original_message(embed=embed)

    @help.autocomplete("command")
    async def help_autocomplete(self, inter, string: str):
        query = string.lower()
        names = sorted(DETAILS.keys())
        return [name for name in names if query in name][:25]


def setup(bot):
    bot.add_cog(HelpCommand(bot))
