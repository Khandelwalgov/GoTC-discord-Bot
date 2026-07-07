import disnake
from disnake.ext import commands
from database import db
from firebase_admin import firestore
import pandas as pd
import io

class Council(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- HELPER: RESOLVE USER BY TAG OR IGN (ISOLATED TO GUILD) ---
    async def get_user_context(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member = None, ign: str = None):
        """Helper to find Firestore data using either a Discord member or an IGN string, isolated by Guild."""
        # Reference to this specific server's user collection
        guild_users_ref = db.collection("guilds").document(str(inter.guild.id)).collection("users")
        
        if member:
            doc = guild_users_ref.document(str(member.id)).get()
            if doc.exists:
                return str(member.id), doc.to_dict()
        
        if ign:
            users_stream = guild_users_ref.stream()
            for doc in users_stream:
                data = doc.to_dict()
                if data.get("ign", "").lower() == ign.lower():
                    return doc.id, data
        return None, None

    @commands.slash_command(description="Lookup account security/details by @User or IGN")
    async def lookup_account(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        member: disnake.Member = commands.Param(default=None), 
        ign: str = commands.Param(default=None)
    ):
        await inter.response.defer()
        uid, data = await self.get_user_context(inter, member, ign)

        if not data:
            return await inter.edit_original_message(content="❌ No records found for that input in this server.")

        # Access List
        access_uids = data.get("access_list", [])
        access_str = ", ".join([f"<@{u}>" for u in access_uids]) if access_uids else "None"
        
        # Alts (Server Isolated)
        alts_ref = db.collection("guilds").document(str(inter.guild.id)).collection("users").document(uid).collection("alts").stream()
        alts_list = [f"{alt.id} ({alt.to_dict().get('purpose', 'N/A')})" for alt in alts_ref]
        alts_str = ", ".join(alts_list) if alts_list else "None"

        embed = disnake.Embed(title=f"🏰 Security Profile: {data.get('ign')}", color=disnake.Color.dark_blue())
        embed.add_field(name="Owner", value=f"<@{uid}>", inline=True)
        embed.add_field(name="Tier", value=data.get("tier", "Unknown"), inline=True)
        embed.add_field(name="Access List", value=access_str, inline=False)
        embed.add_field(name="Registered Alts", value=alts_str, inline=False)
        await inter.edit_original_message(embed=embed)

    @commands.slash_command(description="Retrieve all combat stats for a specific account")
    async def get_stats(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        member: disnake.Member = commands.Param(default=None), 
        ign: str = commands.Param(default=None)
    ):
        await inter.response.defer()
        uid, data = await self.get_user_context(inter, member, ign)

        if not data:
            return await inter.edit_original_message(content="❌ Account not found in this server.")

        att = data.get("attack_stats", {})
        dfn = data.get("defence_stats", {})
        dragon_att = data.get("dragon_attack_stats", {})
        dragon_def = data.get("dragon_defense_stats", {})

        embed = disnake.Embed(title=f"Combat Stats: {data.get('ign')}", color=disnake.Color.red())
        
        atk_fmt = (f"**Marcher attack vs player at seat of power:** {att.get('m_att', '-')}\n"
                   f"**Marcher defense vs player at seat of power:** {att.get('m_def', '-')}\n"
                   f"**Marcher health vs player at seat of power:** {att.get('m_health', '-')}\n"
                   f"**Rally Cap:** {att.get('r_cap', '-')}\n"
                   f"**Rally vs SoP:** {att.get('r_sop', '-')}")
        
        def_fmt = (f"**Defense vs player at seat of power:** {dfn.get('s_def', '-')}\n"
                   f"**Attack vs player at seat of power:** {dfn.get('s_att', '-')}\n"
                   f"**Health vs player at seat of power:** {dfn.get('s_health', '-')}\n"
                   f"**Reinforcement cap at owned SoP:** {dfn.get('rein_sop', '-')}")

        embed.add_field(name="Offense", value=atk_fmt, inline=True)
        embed.add_field(name="Defense", value=def_fmt, inline=True)

        if dragon_att:
            dragon_atk_fmt = (f"**Dragon marcher attack vs player at SoP:** {dragon_att.get('dragon_m_att', '-')}\n"
                              f"**Dragon marcher defense vs player at SoP:** {dragon_att.get('dragon_m_def', '-')}\n"
                              f"**Dragon marcher health vs player at SoP:** {dragon_att.get('dragon_m_health', '-')}\n"
                              f"**Dragon attack vs dragon:** {dragon_att.get('dragon_att_vs_dragon', '-')}")
            embed.add_field(name="Dragon Offense", value=dragon_atk_fmt, inline=False)

        if dragon_def:
            dragon_def_fmt = (f"**Dragon defense vs player at SoP:** {dragon_def.get('dragon_def_player_sop', '-')}\n"
                              f"**Dragon attack vs player at SoP:** {dragon_def.get('dragon_att_player_sop', '-')}\n"
                              f"**Dragon health vs player at SoP:** {dragon_def.get('dragon_health_player_sop', '-')}\n"
                              f"**Dragon defense vs dragon:** {dragon_def.get('dragon_def_vs_dragon', '-')}")
            embed.add_field(name="Dragon Defense", value=dragon_def_fmt, inline=False)

        await inter.edit_original_message(embed=embed)

    @commands.slash_command(description="Tag owner and everyone with access to the account")
    async def bubble_up(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        member: disnake.Member = commands.Param(default=None), 
        ign: str = commands.Param(default=None)
    ):
        await inter.response.defer()
        uid, data = await self.get_user_context(inter, member, ign)

        if not data:
            return await inter.edit_original_message(content="❌ Account not found in this server.")

        access_list = data.get("access_list", [])
        mentions = [f"<@{uid}>"] + [f"<@{a_uid}>" for a_uid in access_list]
        
        content = f"📣 **BUBBLE UP ALERT: {data.get('ign')}**\n{' '.join(mentions)}\nYou are requested to check this Keep status immediately!"
        await inter.edit_original_message(content=content)

    @commands.slash_command(name="account_export", description="Export registered account/profile stat data")
    async def export_roster(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        format: str = commands.Param(choices=["CSV", "Discord Message"]),
        include_alts: bool = True,
        min_tier: str = commands.Param(default="T1", choices=[f"T{i}" for i in range(1, 13)]),
        stat_columns: str = commands.Param(default="Basic Info", choices=["Basic Info", "Offense Only", "Defense Only", "Full Combat Stats"])
    ):
        await inter.response.defer()
        # Server Isolated stream
        guild_id_str = str(inter.guild.id)
        all_users = db.collection("guilds").document(guild_id_str).collection("users").stream()
        rows = []
        min_tier_val = int(min_tier.replace("T", ""))

        for doc in all_users:
            u = doc.to_dict()
            try:
                u_tier_val = int(u.get("tier", "T1").replace("T", ""))
            except: u_tier_val = 1
            
            if u_tier_val < min_tier_val: continue

            def process_entry(name, type_str, tier, src):
                entry = {"Owner_IGN": u.get("ign"), "Acc_Name": name, "Type": type_str, "Tier": tier}
                a_stats = src.get("attack_stats", {})
                d_stats = src.get("defence_stats", {})
                
                # UPDATED: Now includes ALL stats from modals
                if stat_columns in ["Offense Only", "Full Combat Stats"]:
                    entry.update({
                        "M_Att": a_stats.get("m_att", "-"),
                        "M_HP": a_stats.get("m_health", "-"),
                        "M_Def": a_stats.get("m_def", "-"),
                        "R_Cap": a_stats.get("r_cap", "-"),
                        "R_SoP": a_stats.get("r_sop", "-")
                    })
                if stat_columns in ["Defense Only", "Full Combat Stats"]:
                    entry.update({
                        "S_Att": d_stats.get("s_att", "-"),
                        "S_Def": d_stats.get("s_def", "-"),
                        "S_HP": d_stats.get("s_health", "-"),
                        "Rein_Cap": d_stats.get("rein_sop", "-")
                    })
                if stat_columns in ["Offense Only", "Full Combat Stats"]:
                    dragon_attack = src.get("dragon_attack_stats", {})
                    entry.update({
                        "Dragon_M_Att": dragon_attack.get("dragon_m_att", "-"),
                        "Dragon_M_Def": dragon_attack.get("dragon_m_def", "-"),
                        "Dragon_M_HP": dragon_attack.get("dragon_m_health", "-"),
                        "Dragon_Att_vs_Dragon": dragon_attack.get("dragon_att_vs_dragon", "-")
                    })
                if stat_columns in ["Defense Only", "Full Combat Stats"]:
                    dragon_defense = src.get("dragon_defense_stats", {})
                    entry.update({
                        "Dragon_Def_Player_SoP": dragon_defense.get("dragon_def_player_sop", "-"),
                        "Dragon_Att_Player_SoP": dragon_defense.get("dragon_att_player_sop", "-"),
                        "Dragon_HP_Player_SoP": dragon_defense.get("dragon_health_player_sop", "-"),
                        "Dragon_Def_vs_Dragon": dragon_defense.get("dragon_def_vs_dragon", "-")
                    })
                return entry

            rows.append(process_entry("PRIMARY", "Main", u.get("tier"), u))

            if include_alts:
                # Alts also pulled from server-isolated path
                alts = db.collection("guilds").document(guild_id_str).collection("users").document(doc.id).collection("alts").stream()
                for alt in alts:
                    alt_data = alt.to_dict()
                    rows.append(process_entry(alt.id, f"Alt ({alt_data.get('purpose')})", "N/A", alt_data))

        if not rows:
            return await inter.edit_original_message(content="⚠️ No data matches these filters in this server.")

        df = pd.DataFrame(rows)

        if format == "CSV":
            buf = io.BytesIO()
            df.to_csv(buf, index=False)
            buf.seek(0)
            await inter.edit_original_message(file=disnake.File(buf, filename="GoTC_Account_Export.csv"))
        else:
            summary = df.to_string(index=False)
            if len(summary) > 1900:
                summary = summary[:1900] + "\n...[Truncated]"
            await inter.edit_original_message(content=f"**Account Export ({stat_columns}):**\n```\n{summary}\n```")

def setup(bot):
    bot.add_cog(Council(bot))
