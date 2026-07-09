import disnake
from disnake.ext import commands

from services.translation import get_user_language, t


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)


COMMANDS = {
    "profile": {
        "title": "Profile",
        "commands": [
            ("/language", "Choose your Steward language."),
            ("/tutorial", "Open the guided member tutorial."),
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
            ("/update_attack", "Update primary troop attack and rally stats."),
            ("/update_defense", "Update primary troop defense and owned-SoP rein cap."),
            ("/update_dragon_attack_stats", "Update dragon attack stats."),
            ("/update_dragon_defense_stats", "Update dragon defense stats."),
            ("/get_stats", "Look up recorded combat stats."),
            ("/account_export", "Export registered account/stat data."),
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
            ("/setup_logistics", "Set the Logistics role."),
            ("/setup_announcements", "Set the announcement channel."),
        ],
    },
    "setup": {
        "title": "Setup",
        "commands": [
            ("/setup_gotc_roles", "Create or verify all GoTC roles."),
            ("/tutorial_admin", "Open the guided admin setup tutorial."),
            ("/post_role_panel", "Post troop, type, specialist, and dragon panels."),
            ("/post_battleground_ping_panel", "Post BG ping opt-in buttons."),
            ("/set_logs_channel", "Set join/leave log channel."),
            ("/disable_logs_channel", "Disable join/leave logs."),
            ("/set_autorole", "Set an existing role for new members."),
            ("/disable_autorole", "Disable automatic role assignment."),
            ("/server_settings", "Show current server settings."),
            ("/moderate", "Kick or ban a member."),
        ],
    },
    "admin_proxy": {
        "title": "Admin Proxy",
        "commands": [
            ("/add_register", "Register a member on their behalf."),
            ("/add_update", "Update a member's main or alt stats."),
        ],
    },
    "legion_roster": {
        "title": "Legion Roster",
        "commands": [
            ("/roster_template", "Download the full roster CSV template."),
            ("/roster_import", "Preview and import a full seat roster."),
            ("/roster_validate", "Check hierarchy, capacity, and TA expiry."),
            ("/roster_export", "Export roster as CSV, JSON, or text."),
            ("/roster_update_positions", "Create a weekly placement draft."),
            ("/roster_alts", "List roster PA/TA entries."),
            ("/roster_update_expiry", "Batch update TA expiry dates."),
            ("/roster_config", "Configure TA expiry defaults and alerts."),
        ],
    },
}


DETAILS = {
    "language": (
        "Choose your language",
        "`/language language:Deutsch`",
        "Sets the language used for supported private replies, help, tutorials, and translated public message copies.",
    ),
    "tutorial": (
        "Guided walkthrough",
        "`/tutorial` or `/tutorial topic:stats`",
        "Opens a private, button-driven walkthrough for registration, stats, alts, access, lookup, bubble alerts, and time commands.",
    ),
    "tutorial_admin": (
        "Admin setup walkthrough",
        "`/tutorial_admin` or `/tutorial_admin topic:roster_import`",
        "Opens a private admin guide for role setup, Logistics/Council setup, BG tools, polls, and roster management.",
    ),
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
    "update_access": (
        "Remove keep access",
        "`/update_access`",
        "Shows your access list privately and lets you remove someone from it.",
    ),
    "update_name": (
        "Rename main or alt",
        "`/update_name current_name:<old> new_name:<new>`",
        "Updates your main IGN or renames one of your registered alts.",
    ),
    "update_attack": (
        "Update attack stats",
        "`/update_attack target:main`",
        "Opens a modal for primary troop stats only: marcher attack/defense/health vs player at seat of power, plus rally cap fields.",
    ),
    "update_defense": (
        "Update defense stats",
        "`/update_defense target:main`",
        "Opens a modal for primary troop stats only: defense/attack/health vs player at seat of power, plus reinforcement cap at owned SoP.",
    ),
    "update_dragon_attack_stats": (
        "Update dragon attack stats",
        "`/update_dragon_attack_stats target:main`",
        "Opens a 4-field modal for dragon marcher attack, defense, health vs player at SoP, plus dragon attack vs dragon.",
    ),
    "update_dragon_defense_stats": (
        "Update dragon defense stats",
        "`/update_dragon_defense_stats target:main`",
        "Opens a 3-field modal for dragon defense, attack, and health vs player at SoP.",
    ),
    "get_stats": (
        "View combat stats",
        "`/get_stats member:@User` or `/get_stats ign:<IGN>`",
        "Shows saved offense, defense, dragon offense, and dragon defense stats for a registered account.",
    ),
    "lookup_account": (
        "Look up an account",
        "`/lookup_account member:@User` or `/lookup_account ign:<IGN>`",
        "Shows the account owner, tier, alts, and access list for the selected profile.",
    ),
    "bubble_up": (
        "Send a bubble alert",
        "`/bubble_up member:@User` or `/bubble_up ign:<IGN>`",
        "Tags the account owner and everyone on their access list when a keep needs attention.",
    ),
    "time12": (
        "Post a 12-hour timestamp",
        "`/time12 time_input:8:30pm date_input:<date> extra_text:Rally at`",
        "Converts your registered timezone into a Discord timestamp everyone sees in their own local time.",
    ),
    "time24": (
        "Post a 24-hour timestamp",
        "`/time24 hhmm:2030 date_input:<date> extra_text:Rally at`",
        "Converts your registered timezone into a Discord timestamp everyone sees in their own local time.",
    ),
    "add_register": (
        "Admin register",
        "`/add_register member:@User in_game_name:<IGN> timezone:Asia/Kolkata tier:T11`",
        "Admin or Logistics shortcut that writes the selected member's profile to the same Firestore path as self-registration.",
    ),
    "add_update": (
        "Admin stat update",
        "`/add_update member:@User stat_type:attack target:main` or `stat_type:defense`",
        "Admin or Logistics stat modal for updating a selected member's main account or an already registered alt. Use `attack` or `defense`.",
    ),
    "setup_logistics": (
        "Set Logistics role",
        "`/setup_logistics role:@Logistics`",
        "Admin-only setup. The Logistics role can use admin-proxy registration/stat commands and Legion roster management commands, but not moderation or server settings.",
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
    "availability_report": (
        "Show availability report",
        "`/availability_report`",
        "Shows members grouped by the current weekend availability roles.",
    ),
    "setup_gotc_roles": (
        "Create GoTC roles",
        "`/setup_gotc_roles`",
        "Creates or verifies Steward's GoTC roles, saves their role IDs, and keeps renamed roles working later.",
    ),
    "post_role_panel": (
        "Post role panels",
        "`/post_role_panel`",
        "Posts persistent role selection panels for troop tier, primary type, specialist roles, and dragon level, including L55+ Rally Keep.",
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
    "set_logs_channel": (
        "Set logs channel",
        "`/set_logs_channel channel:#server-logs`",
        "Sends join and leave logs only to the configured channel.",
    ),
    "disable_logs_channel": (
        "Disable logs",
        "`/disable_logs_channel`",
        "Turns off Steward join and leave logs.",
    ),
    "set_autorole": (
        "Set autorole",
        "`/set_autorole role:@Member enabled:True`",
        "Uses an existing assignable role for new members. Steward will not create roles.",
    ),
    "disable_autorole": (
        "Disable autorole",
        "`/disable_autorole`",
        "Stops automatic role assignment for new members.",
    ),
    "server_settings": (
        "Server settings",
        "`/server_settings`",
        "Shows the configured log channel and autorole state.",
    ),
    "moderate": (
        "Moderate a member",
        "`/moderate action:kick member:@User reason:<reason>` or `action:ban`",
        "Kick or ban a member. This uses Discord moderation permissions and is separate from Steward logistics access.",
    ),
    "setup_council": (
        "Set Council role",
        "`/setup_council role:@Council`",
        "Admin-only setup. The Council role can close polls and use council-only announcement tools.",
    ),
    "setup_announcements": (
        "Set announcement channel",
        "`/setup_announcements channel:#announcements`",
        "Admin-only setup. Council announcements are sent to this configured channel.",
    ),
    "announce": (
        "Send council announcement",
        "`/announce message:<text>`",
        "Council-only command that posts an @everyone announcement embed in the configured announcement channel.",
    ),
    "account_export": (
        "Export account data",
        "`/account_export format:CSV include_alts:True stat_columns:Full Combat Stats`",
        "Exports registered member profiles, alts, and saved combat stats. Legion seat rosters use `/roster_export` instead.",
    ),
    "roster_template": (
        "Download roster template",
        "`/roster_template`",
        "Returns the exact CSV structure for the lightweight Legion seat roster.",
    ),
    "roster_import": (
        "Import roster",
        "`/roster_import file:<csv> roster_name:Main Legion replace_existing:False`",
        "Admin or Logistics. Validates a full roster CSV, fixes missing TA expiry defaults, then shows an Apply/Cancel preview.",
    ),
    "roster_validate": (
        "Validate roster",
        "`/roster_validate`",
        "Checks the active Legion roster for hierarchy, capacity, and temporary-alt expiry warnings.",
    ),
    "roster_export": (
        "Export roster",
        "`/roster_export format:csv`",
        "Exports the lightweight Legion seat roster as CSV, JSON, or text. Registered account data uses `/account_export`.",
    ),
    "roster_update_positions": (
        "Weekly roster draft",
        "`/roster_update_positions file:<csv> mode:auto`\n"
        "`/roster_update_positions text:T1: vix | T2: t2alt, IamT31, Gov | PROTECT: vix, Gov mode:ask`",
        "Admin or Logistics. Text supports multiline sections or one-line pipe sections. Sections: T1, T2, T3, T4, PROTECT, REMOVE, MODE. Names can be comma-separated. Empty sections are allowed.",
    ),
    "roster_alts": (
        "Roster alts",
        "`/roster_alts filter:expired`",
        "Lists only roster PA/TA entries. This is separate from the registered /add_alt system.",
    ),
    "roster_config": (
        "Roster config",
        "`/roster_config default_ta_expiry_days:30 ta_warning_days:1 expiry_channel:#channel`",
        "Admin or Logistics. Configures default TA expiry, warning window, and daily expiry alert channel.",
    ),
    "roster_update_expiry": (
        "Update TA expiry",
        "`/roster_update_expiry mode:specific names:AltOne, AltTwo days:14`",
        "Admin or Logistics. Batch updates expiry dates for temporary alts by all TAs, newly added TAs, or specific names.",
    ),
}


def translated(language_code, key, fallback):
    value = t(key, language_code)
    return fallback if value == key else value


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
        language_code = get_user_language(inter.guild.id, inter.author.id)

        if command:
            command_name = command.lower().replace("/", "").strip()
            if command_name in DETAILS:
                title, usage, details = DETAILS[command_name]
                title = translated(language_code, f"help.detail.{command_name}.title", title)
                usage = translated(language_code, f"help.detail.{command_name}.usage", usage)
                details = translated(language_code, f"help.detail.{command_name}.details", details)
                embed = disnake.Embed(title=f"/{command_name}: {title}", color=BRAND_COLOR)
                embed.add_field(name=t("help.usage", language_code), value=usage, inline=False)
                embed.add_field(name=t("help.details", language_code), value=details, inline=False)
                return await inter.edit_original_message(embed=embed)

            return await inter.edit_original_message(
                content=t("help.no_detail", language_code, command=command_name)
            )

        embed = disnake.Embed(
            title=t("help.title", language_code),
            description=t("help.description", language_code),
            color=BRAND_COLOR,
        )

        for section_key, section in COMMANDS.items():
            lines = []
            for name, description in section["commands"]:
                command_key = name.replace("/", "")
                short = translated(language_code, f"help.command.{command_key}.short", description)
                lines.append(f"`{name}` - {short}")
            embed.add_field(
                name=translated(language_code, f"help.section.{section_key}", section["title"]),
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=t("help.footer", language_code))
        await inter.edit_original_message(embed=embed)

    @help.autocomplete("command")
    async def help_autocomplete(self, inter, string: str):
        query = string.lower()
        names = sorted(DETAILS.keys())
        return [name for name in names if query in name][:25]


def setup(bot):
    bot.add_cog(HelpCommand(bot))
