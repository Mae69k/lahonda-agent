import discord
from discord import app_commands
from discord.ext import commands
import json

from utils.database import get_db, get_guild_config, update_guild_config
from utils.permissions import require_level


async def quarantine_member(guild: discord.Guild, member: discord.Member, reason: str):
    """Retire tous les rôles d'un membre et les sauvegarde pour restauration future."""
    db = await get_db()
    role_ids = [r.id for r in member.roles if r != guild.default_role]
    await db.execute(
        "INSERT OR REPLACE INTO quarantine (guild_id, user_id, original_roles) VALUES (?, ?, ?)",
        (guild.id, member.id, json.dumps(role_ids)),
    )
    await db.commit()
    try:
        await member.edit(roles=[], reason=reason)
    except discord.Forbidden:
        pass


class Security(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    security_group = app_commands.Group(name="security", description="Outils de sécurité du serveur")
    panic_group = app_commands.Group(name="panic", description="Mode panique : verrouille tout instantanément")

    # ---------- QUARANTINE ----------
    @app_commands.command(name="quarantine", description="Met un membre en quarantaine (retire tous ses rôles)")
    @require_level("quarantine")
    async def quarantine(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        await quarantine_member(interaction.guild, membre, raison)
        await interaction.response.send_message(f"🔒 {membre.mention} a été placé en quarantaine.")

    @app_commands.command(name="unquarantine", description="Restaure les rôles d'un membre mis en quarantaine")
    @require_level("unquarantine")
    async def unquarantine(self, interaction: discord.Interaction, membre: discord.Member):
        db = await get_db()
        cursor = await db.execute(
            "SELECT original_roles FROM quarantine WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, membre.id),
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("❌ Ce membre n'est pas en quarantaine.", ephemeral=True)
            return

        role_ids = json.loads(row["original_roles"])
        roles = [interaction.guild.get_role(rid) for rid in role_ids if interaction.guild.get_role(rid)]
        try:
            await membre.edit(roles=roles)
        except discord.Forbidden:
            pass

        await db.execute("DELETE FROM quarantine WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, membre.id))
        await db.commit()
        await interaction.response.send_message(f"✅ {membre.mention} a été retiré de la quarantaine.")

    # ---------- SECURITY ----------
    @security_group.command(name="scan", description="Scanne le serveur à la recherche de risques évidents")
    @require_level("security")
    async def scan(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        risks = []

        for member in guild.members:
            if member.bot and member.guild_permissions.administrator:
                risks.append(f"🤖 Le bot {member.mention} a la permission Administrateur")

        for role in guild.roles:
            if role.permissions.administrator and role != guild.default_role and len(role.members) > 3:
                risks.append(f"⚠️ Le rôle {role.mention} (Administrateur) est attribué à {len(role.members)} membres")

        if not risks:
            await interaction.followup.send("✅ Aucun risque évident détecté.")
            return

        embed = discord.Embed(title="🔍 Résultat du scan de sécurité", color=discord.Color.orange())
        embed.description = "\n".join(risks[:15])
        await interaction.followup.send(embed=embed)

    @security_group.command(name="permissions", description="Liste les membres ayant des permissions dangereuses")
    @require_level("security")
    async def permissions_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        dangerous = []
        for member in guild.members:
            if member.bot:
                continue
            perms = member.guild_permissions
            if perms.administrator or perms.ban_members or perms.kick_members or perms.manage_guild:
                dangerous.append(f"{member.mention} — Admin: {perms.administrator}, Ban: {perms.ban_members}, Kick: {perms.kick_members}")

        text = "\n".join(dangerous[:20]) or "*Aucun membre à risque*"
        embed = discord.Embed(title="🔐 Membres avec permissions sensibles", description=text, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    @security_group.command(name="status", description="Affiche un résumé de l'état de sécurité du serveur")
    @require_level("security")
    async def security_status(self, interaction: discord.Interaction):
        config = await get_guild_config(interaction.guild.id)

        db = await get_db()
        antispam = await db.execute("SELECT enabled FROM antispam_config WHERE guild_id = ?", (interaction.guild.id,))
        antispam_row = await antispam.fetchone()
        antilink = await db.execute("SELECT enabled FROM antilink_config WHERE guild_id = ?", (interaction.guild.id,))
        antilink_row = await antilink.fetchone()
        antiraid = await db.execute("SELECT enabled FROM antiraid_config WHERE guild_id = ?", (interaction.guild.id,))
        antiraid_row = await antiraid.fetchone()
        antinuke = await db.execute("SELECT enabled FROM antinuke_config WHERE guild_id = ?", (interaction.guild.id,))
        antinuke_row = await antinuke.fetchone()

        def status_icon(row):
            return "✅" if row and row["enabled"] else "❌"

        embed = discord.Embed(title="🛡️ État de sécurité global", color=discord.Color.blurple())
        embed.add_field(name="Anti-spam", value=status_icon(antispam_row))
        embed.add_field(name="Anti-lien", value=status_icon(antilink_row))
        embed.add_field(name="Anti-raid", value=status_icon(antiraid_row))
        embed.add_field(name="Anti-nuke", value=status_icon(antinuke_row))
        embed.add_field(name="Mode panique", value="🚨 Actif" if config["panic_mode"] else "✅ Inactif", inline=False)
        await interaction.response.send_message(embed=embed)

    @security_group.command(name="report", description="Génère un rapport de sécurité détaillé")
    @require_level("security")
    async def report(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        db = await get_db()

        warnings_count = await (await db.execute("SELECT COUNT(*) as c FROM warnings WHERE guild_id = ?", (guild.id,))).fetchone()
        cases_count = await (await db.execute("SELECT COUNT(*) as c FROM cases WHERE guild_id = ?", (guild.id,))).fetchone()
        quarantine_count = await (await db.execute("SELECT COUNT(*) as c FROM quarantine WHERE guild_id = ?", (guild.id,))).fetchone()

        embed = discord.Embed(title=f"📊 Rapport de sécurité — {guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Membres", value=guild.member_count)
        embed.add_field(name="Avertissements totaux", value=warnings_count["c"])
        embed.add_field(name="Dossiers de modération", value=cases_count["c"])
        embed.add_field(name="Membres en quarantaine", value=quarantine_count["c"])
        await interaction.followup.send(embed=embed)

    # ---------- PANIC ----------
    @panic_group.command(name="enable", description="Active le mode panique (verrouille tout, bloque les nouvelles arrivées)")
    @require_level("panic")
    async def panic_enable(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await update_guild_config(interaction.guild.id, panic_mode=1)
        for channel in interaction.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(interaction.guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            except discord.Forbidden:
                continue
        await interaction.followup.send("🚨 Mode panique activé. Le serveur est verrouillé.")

    @panic_group.command(name="disable", description="Désactive le mode panique")
    @require_level("panic")
    async def panic_disable(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await update_guild_config(interaction.guild.id, panic_mode=0)
        for channel in interaction.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(interaction.guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            except discord.Forbidden:
                continue
        await interaction.followup.send("✅ Mode panique désactivé.")


async def setup(bot: commands.Bot):
    cog = Security(bot)
    bot.tree.add_command(cog.security_group)
    bot.tree.add_command(cog.panic_group)
    await bot.add_cog(cog)
