import discord
from discord import app_commands
from discord.ext import commands
from collections import defaultdict, deque
import datetime

from utils.database import get_db
from utils.permissions import require_level


async def get_antispam_config(guild_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM antispam_config WHERE guild_id = ?", (guild_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO antispam_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
        cursor = await db.execute("SELECT * FROM antispam_config WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
    return row


class AntiSpam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # historique des messages récents par (guild_id, user_id)
        self.message_log: dict[tuple[int, int], deque] = defaultdict(deque)

    group = app_commands.Group(name="antispam", description="Configuration de l'anti-spam")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = await get_antispam_config(message.guild.id)
        if not config["enabled"]:
            return

        key = (message.guild.id, message.author.id)
        now = datetime.datetime.now().timestamp()
        log = self.message_log[key]
        log.append(now)

        # ne garde que les messages dans la fenêtre de temps configurée
        while log and now - log[0] > config["interval_seconds"]:
            log.popleft()

        if len(log) > config["max_messages"]:
            log.clear()
            member = message.author
            try:
                if config["action"] == "timeout":
                    await member.timeout(datetime.timedelta(minutes=5), reason="Anti-spam : flood de messages")
                elif config["action"] == "kick":
                    await member.kick(reason="Anti-spam : flood de messages")
                elif config["action"] == "ban":
                    await member.ban(reason="Anti-spam : flood de messages")
            except discord.Forbidden:
                pass
            await message.channel.send(f"🚫 {member.mention} a été sanctionné pour spam.", delete_after=10)

    @group.command(name="enable", description="Active l'anti-spam")
    @require_level("antispam")
    async def enable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antispam_config(interaction.guild.id)
        await db.execute("UPDATE antispam_config SET enabled = 1 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-spam activé.")

    @group.command(name="disable", description="Désactive l'anti-spam")
    @require_level("antispam")
    async def disable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antispam_config(interaction.guild.id)
        await db.execute("UPDATE antispam_config SET enabled = 0 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-spam désactivé.")

    @group.command(name="status", description="Affiche l'état actuel de l'anti-spam")
    @require_level("antispam")
    async def status(self, interaction: discord.Interaction):
        config = await get_antispam_config(interaction.guild.id)
        embed = discord.Embed(title="🛡️ Statut Anti-Spam", color=discord.Color.blurple())
        embed.add_field(name="Activé", value="✅ Oui" if config["enabled"] else "❌ Non")
        embed.add_field(name="Seuil", value=f"{config['max_messages']} messages / {config['interval_seconds']}s")
        embed.add_field(name="Action", value=config["action"])
        await interaction.response.send_message(embed=embed)

    @group.command(name="config", description="Configure les seuils de l'anti-spam")
    @app_commands.describe(
        max_messages="Nombre de messages max autorisés",
        interval_seconds="Fenêtre de temps en secondes",
        action="Action à appliquer : timeout, kick ou ban",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Timeout", value="timeout"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Ban", value="ban"),
    ])
    @require_level("antispam")
    async def config_cmd(self, interaction: discord.Interaction, max_messages: int, interval_seconds: int, action: app_commands.Choice[str]):
        db = await get_db()
        await get_antispam_config(interaction.guild.id)
        await db.execute(
            "UPDATE antispam_config SET max_messages = ?, interval_seconds = ?, action = ? WHERE guild_id = ?",
            (max_messages, interval_seconds, action.value, interaction.guild.id),
        )
        await db.commit()
        await interaction.response.send_message(
            f"✅ Anti-spam configuré : {max_messages} messages / {interval_seconds}s → **{action.name}**"
        )


async def setup(bot: commands.Bot):
    cog = AntiSpam(bot)
    bot.tree.add_command(cog.group)
    await bot.add_cog(cog)
