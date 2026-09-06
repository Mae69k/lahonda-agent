import discord
from discord import app_commands
from discord.ext import commands
from collections import defaultdict, deque
import datetime

from utils.database import get_db, get_guild_config
from utils.permissions import require_level


async def get_antinuke_config(guild_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM antinuke_config WHERE guild_id = ?", (guild_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO antinuke_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
        cursor = await db.execute("SELECT * FROM antinuke_config WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
    return row


class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # (guild_id, actor_id, action_type) -> deque de timestamps
        self.action_log: dict[tuple, deque] = defaultdict(deque)

    group = app_commands.Group(name="antinuke", description="Configuration de l'anti-nuke")

    async def _record_and_check(self, guild: discord.Guild, actor: discord.Member, action_type: str, threshold: int, interval: int):
        key = (guild.id, actor.id, action_type)
        now = datetime.datetime.now().timestamp()
        log = self.action_log[key]
        log.append(now)
        while log and now - log[0] > interval:
            log.popleft()

        if len(log) > threshold:
            log.clear()
            await self.punish(guild, actor, f"Anti-nuke : trop d'actions '{action_type}' en peu de temps")

    async def punish(self, guild: discord.Guild, actor: discord.Member, reason: str):
        from cogs.security import quarantine_member  # import différé pour éviter la dépendance circulaire

        try:
            await quarantine_member(guild, actor, reason)
        except Exception:
            pass

        config = await get_guild_config(guild.id)
        if config["log_security_channel"]:
            channel = guild.get_channel(config["log_security_channel"])
            if channel:
                embed = discord.Embed(title="🚨 ANTI-NUKE DÉCLENCHÉ", color=discord.Color.dark_red())
                embed.add_field(name="Utilisateur", value=f"{actor} ({actor.id})", inline=False)
                embed.add_field(name="Raison", value=reason, inline=False)
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        config = await get_antinuke_config(channel.guild.id)
        if not config["enabled"]:
            return
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            actor = entry.user
            if isinstance(actor, discord.Member) and not actor.guild_permissions.administrator:
                await self._record_and_check(
                    channel.guild, actor, "channel_delete", config["channel_delete_threshold"], config["interval_seconds"]
                )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        config = await get_antinuke_config(role.guild.id)
        if not config["enabled"]:
            return
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            actor = entry.user
            if isinstance(actor, discord.Member):
                await self._record_and_check(
                    role.guild, actor, "role_delete", config["role_delete_threshold"], config["interval_seconds"]
                )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        config = await get_antinuke_config(guild.id)
        if not config["enabled"]:
            return
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            actor = entry.user
            if isinstance(actor, discord.Member):
                await self._record_and_check(guild, actor, "ban", config["ban_threshold"], config["interval_seconds"])

    @group.command(name="enable", description="Active l'anti-nuke")
    @require_level("antinuke")
    async def enable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antinuke_config(interaction.guild.id)
        await db.execute("UPDATE antinuke_config SET enabled = 1 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-nuke activé.")

    @group.command(name="disable", description="Désactive l'anti-nuke")
    @require_level("antinuke")
    async def disable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antinuke_config(interaction.guild.id)
        await db.execute("UPDATE antinuke_config SET enabled = 0 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-nuke désactivé.")

    @group.command(name="status", description="Affiche l'état de l'anti-nuke")
    @require_level("antinuke")
    async def status(self, interaction: discord.Interaction):
        config = await get_antinuke_config(interaction.guild.id)
        embed = discord.Embed(title="🛡️ Statut Anti-Nuke", color=discord.Color.blurple())
        embed.add_field(name="Activé", value="✅ Oui" if config["enabled"] else "❌ Non")
        embed.add_field(name="Seuil bans", value=config["ban_threshold"])
        embed.add_field(name="Seuil suppr. salons", value=config["channel_delete_threshold"])
        embed.add_field(name="Seuil suppr. rôles", value=config["role_delete_threshold"])
        embed.add_field(name="Fenêtre", value=f"{config['interval_seconds']}s")
        await interaction.response.send_message(embed=embed)

    @group.command(name="config", description="Configure les seuils de l'anti-nuke")
    @require_level("antinuke")
    async def config_cmd(
        self,
        interaction: discord.Interaction,
        ban_threshold: int,
        channel_delete_threshold: int,
        role_delete_threshold: int,
        interval_seconds: int,
    ):
        db = await get_db()
        await get_antinuke_config(interaction.guild.id)
        await db.execute(
            """UPDATE antinuke_config SET ban_threshold = ?, channel_delete_threshold = ?,
               role_delete_threshold = ?, interval_seconds = ? WHERE guild_id = ?""",
            (ban_threshold, channel_delete_threshold, role_delete_threshold, interval_seconds, interaction.guild.id),
        )
        await db.commit()
        await interaction.response.send_message("✅ Seuils anti-nuke mis à jour.")


async def setup(bot: commands.Bot):
    cog = AntiNuke(bot)
    bot.tree.add_command(cog.group)
    await bot.add_cog(cog)
