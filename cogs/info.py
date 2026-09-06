import discord
from discord import app_commands
from discord.ext import commands


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="userinfo", description="Affiche les informations d'un membre")
    async def userinfo(self, interaction: discord.Interaction, membre: discord.Member = None):
        membre = membre or interaction.user
        embed = discord.Embed(title=f"👤 {membre}", color=membre.color)
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="ID", value=membre.id, inline=True)
        embed.add_field(name="Surnom", value=membre.nick or "Aucun", inline=True)
        embed.add_field(name="Compte créé le", value=discord.utils.format_dt(membre.created_at, "D"), inline=False)
        embed.add_field(name="A rejoint le", value=discord.utils.format_dt(membre.joined_at, "D"), inline=False)
        roles = [r.mention for r in membre.roles if r != interaction.guild.default_role]
        embed.add_field(name=f"Rôles ({len(roles)})", value=" ".join(roles) if roles else "Aucun", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Affiche les informations du serveur")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"🏰 {guild.name}", color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Propriétaire", value=guild.owner.mention if guild.owner else "Inconnu", inline=True)
        embed.add_field(name="Créé le", value=discord.utils.format_dt(guild.created_at, "D"), inline=False)
        embed.add_field(name="Membres", value=guild.member_count, inline=True)
        embed.add_field(name="Salons textuels", value=len(guild.text_channels), inline=True)
        embed.add_field(name="Salons vocaux", value=len(guild.voice_channels), inline=True)
        embed.add_field(name="Rôles", value=len(guild.roles), inline=True)
        embed.add_field(name="Niveau de boost", value=guild.premium_tier, inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
