import disnake
from disnake.ext import commands

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Detailed guide for all Steward commands")
    async def help(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        command: str = commands.Param(default=None, description="Specify a command for deep-dive info")
    ):
        await inter.response.defer(ephemeral=True)

        # --- DATA DICTIONARY FOR ALL COMMANDS ---
        help_data = {
            "register": {
                "desc": "Creates your server-specific profile.",
                "usage": "`/register in_game_name: <IGN> timezone: <City>`",
                "details": "Ties your GoTC identity to this server. Uses autocomplete for timezones to ensure accurate rally timings."
            },
            "add_alt": {
                "desc": "Registers an alternative account under your profile.",
                "usage": "`/add_alt name: <AltIGN>`",
                "details": "Select the purpose (Farming, Attack, etc.) from the dropdown. Alts are isolated to this server."
            },
            "update_attack": {
                "desc": "Updates combat stats for Main or Alts.",
                "usage": "`/update_attack target: <main or AltName>`",
                "details": "Opens a modal to input Marching Attack, HP, Def, and Rally capacities."
            },
            "update_defence": {
                "desc": "Updates stationary/reinforcement stats.",
                "usage": "`/update_defence target: <main or AltName>`",
                "details": "Opens a modal for Stationary Att/Def/HP and Reinforcement Cap."
            },
            "lookup_account": {
                "desc": "Council: Check owner and access lists.",
                "usage": "`/lookup_account member: [@User] or ign: [Name]`",
                "details": "Displays account security, registered alts, and who has keep access."
            },
            "get_stats": {
                "desc": "Retrieve full combat data for an account.",
                "usage": "`/get_stats member: [@User] or ign: [Name]`",
                "details": "Returns a detailed embed with every attack and defence stat recorded."
            },
            "export_roster": {
                "desc": "Council: Export full allegiance data.",
                "usage": "`/export_roster format: [CSV/Text] stat_columns: [Filter]`",
                "details": "Generates a spreadsheet or message. 'Attack Only' pulls all 5 marcher/rally stats."
            },
            "bubble_up": {
                "desc": "Emergency ping for a keep.",
                "usage": "`/bubble_up member: [@User] or ign: [Name]`",
                "details": "Tags the owner AND everyone on their access list for urgent action."
            },
            "time12": {
                "desc": "Share a 12h time converted for everyone.",
                "usage": "`/time12 time_input: [5:30pm] date_input: [Select] extra_text: [Message]`",
                "details": "Everyone sees this time in THEIR own local timezone. No more mental math."
            },
            "post_weekend_availability": {
                "desc": "Start the weekly availability check.",
                "usage": "`/post_weekend_availability`",
                "details": "Resets current weekend roles and posts the reaction buttons for the new week."
            },
            "create_poll": {
                "desc": "Launch a custom poll with a 'Close' button.",
                "usage": "`/create_poll question: [Text] options: [Opt1, Opt2...]`",
                "details": "Votes are tracked live. Only Council can click the button to finalize the results."
            }
        }

        # --- SINGLE COMMAND HELP ---
        if command:
            cmd_clean = command.lower().replace("/", "")
            if cmd_clean in help_data:
                data = help_data[cmd_clean]
                embed = disnake.Embed(title=f"📖 Command: /{cmd_clean}", color=disnake.Color.blue())
                embed.add_field(name="What it does", value=data["desc"], inline=False)
                embed.add_field(name="Usage", value=f"**{data['usage']}**", inline=False)
                embed.add_field(name="Details", value=data["details"], inline=False)
                return await inter.edit_original_message(embed=embed)
            else:
                return await inter.edit_original_message(content=f"❌ Command `/{cmd_clean}` not found.")

        # --- FULL CATEGORIZED HELP ---
        embed = disnake.Embed(
            title="🏰 Steward: Allegiance Management System",
            description="All data is **Server Isolated**. Your stats here stay here.\nUse `/help command:name` for specific usage.",
            color=disnake.Color.gold()
        )

        embed.add_field(
            name="📝 Registration & Profile",
            value="`register`, `add_alt`, `update_name`, `add_access`, `update_access`",
            inline=False
        )
        embed.add_field(
            name="⚔️ Combat Stats",
            value="`update_attack`, `update_defence`",
            inline=False
        )
        embed.add_field(
            name="🛡️ Council & Intelligence",
            value="`lookup_account`, `get_stats`, `export_roster`, `bubble_up`, `get_availability`",
            inline=False
        )
        embed.add_field(
            name="📅 Coordination & Management",
            value="`time12`, `time24`, `create_poll`, `post_weekend_availability`, `council_announcement`",
            inline=False
        )
        embed.add_field(
            name="⚙️ Server Admin",
            value=" `configure_weekend`, `setup_reaction_roles` (Run these first!)",
            inline=False
        )

        embed.set_footer(text="Developed for GoT:C Alliances")
        await inter.edit_original_message(embed=embed)

def setup(bot):
    bot.add_cog(HelpCommand(bot))