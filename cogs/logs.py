import discord
from discord import app_commands
from discord.ext import commands
import datetime

from utils.database import update_guild_config, get_guild_config
from utils.permissions import require_level


async def send_log(guild: discord.Guild, column: str, embed: discord.Embed):
    config = await get_guild_config(guild.id)
    channel_id = config[column]
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="logs", description="Configure les salons de logs")

    # ---------- Configuration ----------
    @group.command(name="setup", description="Configure un salon unique pour toutes les catégories de logs")
    @require_level("logs")
    async def setup_all(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await update_guild_config(
            interaction.guild.id,
            log_moderation_channel=salon.id,
            log_security_channel=salon.id,
            log_members_channel=salon.id,
            log_messages_channel=salon.id,
            log_server_channel=salon.id,
        )
        await interaction.response.send_message(f"✅ Toutes les catégories de logs pointent maintenant vers {salon.mention}")

    @group.command(name="moderation", description="Définit le salon des logs de modération")
    @require_level("logs")
    async def logs_moderation(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await update_guild_config(interaction.guild.id, log_moderation_channel=salon.id)
        await interaction.response.send_message(f"✅ Logs de modération → {salon.mention}")

    @group.command(name="security", description="Définit le salon des logs de sécurité")
    @require_level("logs")
    async def logs_security(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await update_guild_config(interaction.guild.id, log_security_channel=salon.id)
        await interaction.response.send_message(f"✅ Logs de sécurité → {salon.mention}")

    @group.command(name="members", description="Définit le salon des logs de membres (arrivées/départs)")
    @require_level("logs")
    async def logs_members(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await update_guild_config(interaction.guild.id, log_members_channel=salon.id)
        await interaction.response.send_message(f"✅ Logs de membres → {salon.mention}")

    @group.command(name="messages", description="Définit le salon des logs de messages (suppr/édition)")
    @require_level("logs")
    async def logs_messages(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await update_guild_config(interaction.guild.id, log_messages_channel=salon.id)
        await interaction.response.send_message(f"✅ Logs de messages → {salon.mention}")

    @group.command(name="server", description="Définit le salon des logs serveur (salons/rôles)")
    @require_level("logs")
    async def logs_server(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await update_guild_config(interaction.guild.id, log_server_channel=salon.id)
        await interaction.response.send_message(f"✅ Logs serveur → {salon.mention}")

    # ---------- Listeners : membres ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(title="📥 Arrivée", description=f"{member.mention} a rejoint le serveur", color=discord.Color.green())
        embed.set_footer(text=f"ID : {member.id}")
        await send_log(member.guild, "log_members_channel", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(title="📤 Départ", description=f"{member} a quitté le serveur", color=discord.Color.red())
        embed.set_footer(text=f"ID : {member.id}")
        await send_log(member.guild, "log_members_channel", embed)

    # ---------- Listeners : messages ----------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        embed = discord.Embed(title="🗑️ Message supprimé", color=discord.Color.orange(), timestamp=datetime.datetime.now())
        embed.add_field(name="Auteur", value=message.author.mention, inline=False)
        embed.add_field(name="Salon", value=message.channel.mention, inline=False)
        embed.add_field(name="Contenu", value=message.content[:1000] or "*Vide (probablement un fichier/embed)*", inline=False)
        await send_log(message.guild, "log_messages_channel", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        embed = discord.Embed(title="✏️ Message modifié", color=discord.Color.blue(), timestamp=datetime.datetime.now())
        embed.add_field(name="Auteur", value=before.author.mention, inline=False)
        embed.add_field(name="Salon", value=before.channel.mention, inline=False)
        embed.add_field(name="Avant", value=before.content[:500] or "*Vide*", inline=False)
        embed.add_field(name="Après", value=after.content[:500] or "*Vide*", inline=False)
        await send_log(before.guild, "log_messages_channel", embed)

    # ---------- Listeners : serveur ----------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(title="➕ Salon créé", description=f"{channel.mention if hasattr(channel, 'mention') else channel.name}", color=discord.Color.green())
        await send_log(channel.guild, "log_server_channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(title="➖ Salon supprimé", description=f"#{channel.name}", color=discord.Color.red())
        await send_log(channel.guild, "log_server_channel", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(title="➕ Rôle créé", description=role.mention, color=discord.Color.green())
        await send_log(role.guild, "log_server_channel", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(title="➖ Rôle supprimé", description=f"@{role.name}", color=discord.Color.red())
        await send_log(role.guild, "log_server_channel", embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logs(bot))
