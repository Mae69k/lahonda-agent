import discord
from discord import app_commands
from discord.ext import commands
from collections import deque
import datetime

from utils.database import get_db, update_guild_config, get_guild_config
from utils.permissions import require_level


async def get_antiraid_config(guild_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM antiraid_config WHERE guild_id = ?", (guild_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO antiraid_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
        cursor = await db.execute("SELECT * FROM antiraid_config WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
    return row


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.join_log: dict[int, deque] = {}

    group = app_commands.Group(name="antiraid", description="Configuration de l'anti-raid")
    lockdown_group = app_commands.Group(name="lockdown", description="Verrouille tout le serveur en urgence")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await get_antiraid_config(member.guild.id)
        if not config["enabled"]:
            return

        now = datetime.datetime.now().timestamp()
        log = self.join_log.setdefault(member.guild.id, deque())
        log.append(now)
        while log and now - log[0] > config["interval_seconds"]:
            log.popleft()

        if len(log) > config["join_threshold"]:
            await self.trigger_lockdown(member.guild, "Anti-raid : vague de connexions suspecte détectée")

    async def trigger_lockdown(self, guild: discord.Guild, reason: str):
        await update_guild_config(guild.id, panic_mode=1)
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
            except discord.Forbidden:
                continue

        config = await get_guild_config(guild.id)
        if config["log_security_channel"]:
            log_channel = guild.get_channel(config["log_security_channel"])
            if log_channel:
                embed = discord.Embed(title="🚨 LOCKDOWN AUTOMATIQUE", description=reason, color=discord.Color.red())
                await log_channel.send(embed=embed)

    @group.command(name="enable", description="Active l'anti-raid")
    @require_level("antiraid")
    async def enable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antiraid_config(interaction.guild.id)
        await db.execute("UPDATE antiraid_config SET enabled = 1 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-raid activé.")

    @group.command(name="disable", description="Désactive l'anti-raid")
    @require_level("antiraid")
    async def disable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antiraid_config(interaction.guild.id)
        await db.execute("UPDATE antiraid_config SET enabled = 0 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-raid désactivé.")

    @group.command(name="status", description="Affiche l'état de l'anti-raid")
    @require_level("antiraid")
    async def status(self, interaction: discord.Interaction):
        config = await get_antiraid_config(interaction.guild.id)
        embed = discord.Embed(title="🛡️ Statut Anti-Raid", color=discord.Color.blurple())
        embed.add_field(name="Activé", value="✅ Oui" if config["enabled"] else "❌ Non")
        embed.add_field(name="Seuil", value=f"{config['join_threshold']} arrivées / {config['interval_seconds']}s")
        embed.add_field(name="Action", value=config["action"])
        await interaction.response.send_message(embed=embed)

    @group.command(name="config", description="Configure les seuils de l'anti-raid")
    @require_level("antiraid")
    async def config_cmd(self, interaction: discord.Interaction, join_threshold: int, interval_seconds: int):
        db = await get_db()
        await get_antiraid_config(interaction.guild.id)
        await db.execute(
            "UPDATE antiraid_config SET join_threshold = ?, interval_seconds = ? WHERE guild_id = ?",
            (join_threshold, interval_seconds, interaction.guild.id),
        )
        await db.commit()
        await interaction.response.send_message(f"✅ Anti-raid configuré : {join_threshold} arrivées / {interval_seconds}s")

    # ---------- LOCKDOWN manuel ----------
    @lockdown_group.command(name="enable", description="Verrouille tous les salons du serveur")
    @require_level("lockdown")
    async def lockdown_enable(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.trigger_lockdown(interaction.guild, f"Lockdown manuel déclenché par {interaction.user}")
        await interaction.followup.send("🔒 Serveur entièrement verrouillé.")

    @lockdown_group.command(name="disable", description="Déverrouille tous les salons du serveur")
    @require_level("lockdown")
    async def lockdown_disable(self, interaction: discord.Interaction):
        await interaction.response.defer()
        for channel in interaction.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(interaction.guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            except discord.Forbidden:
                continue
        await update_guild_config(interaction.guild.id, panic_mode=0)
        await interaction.followup.send("🔓 Serveur déverrouillé.")

    @lockdown_group.command(name="status", description="Affiche si le serveur est en lockdown")
    @require_level("lockdown")
    async def lockdown_status(self, interaction: discord.Interaction):
        config = await get_guild_config(interaction.guild.id)
        state = "🔒 Actif" if config["panic_mode"] else "🔓 Inactif"
        await interaction.response.send_message(f"Lockdown : {state}")


async def setup(bot: commands.Bot):
    cog = AntiRaid(bot)
    bot.tree.add_command(cog.group)
    bot.tree.add_command(cog.lockdown_group)
    await bot.add_cog(cog)
