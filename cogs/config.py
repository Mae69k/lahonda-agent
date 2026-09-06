import discord
from discord import app_commands
from discord.ext import commands

from utils.database import update_guild_config, get_guild_config, get_db
from utils.permissions import require_level, LEVEL_NAMES, NAME_TO_LEVEL, DEFAULT_LEVELS


class Config(commands.Cog):
    """Configuration des rôles de permission et des accès par commande"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    config_group = app_commands.Group(name="config", description="Configuration du serveur")
    role_group = app_commands.Group(name="role", description="Configure les rôles de permission", parent=config_group)
    permission_group = app_commands.Group(name="permission", description="Configure les permissions par commande")

    # ---------- /config role ... ----------
    @role_group.command(name="creator", description="Définit le rôle Creator (accès total)")
    @require_level("config")
    async def role_creator(self, interaction: discord.Interaction, role: discord.Role):
        await update_guild_config(interaction.guild.id, creator_role_id=role.id)
        await interaction.response.send_message(f"✅ Rôle **Creator** défini sur {role.mention}")

    @role_group.command(name="admin", description="Définit le rôle Admin")
    @require_level("config")
    async def role_admin(self, interaction: discord.Interaction, role: discord.Role):
        await update_guild_config(interaction.guild.id, admin_role_id=role.id)
        await interaction.response.send_message(f"✅ Rôle **Admin** défini sur {role.mention}")

    @role_group.command(name="moderator", description="Définit le rôle Moderator")
    @require_level("config")
    async def role_moderator(self, interaction: discord.Interaction, role: discord.Role):
        await update_guild_config(interaction.guild.id, moderator_role_id=role.id)
        await interaction.response.send_message(f"✅ Rôle **Moderator** défini sur {role.mention}")

    @role_group.command(name="member", description="Définit le rôle Member")
    @require_level("config")
    async def role_member(self, interaction: discord.Interaction, role: discord.Role):
        await update_guild_config(interaction.guild.id, member_role_id=role.id)
        await interaction.response.send_message(f"✅ Rôle **Member** défini sur {role.mention}")

    # ---------- /permissions ----------
    @app_commands.command(name="permissions", description="Affiche la configuration actuelle des rôles et permissions")
    @require_level("permissions")
    async def permissions(self, interaction: discord.Interaction):
        config = await get_guild_config(interaction.guild.id)
        guild = interaction.guild

        def role_mention(role_id):
            if not role_id:
                return "*Non configuré*"
            role = guild.get_role(role_id)
            return role.mention if role else "*Rôle introuvable*"

        embed = discord.Embed(title="🔐 Configuration des permissions", color=discord.Color.blurple())
        embed.add_field(name="Creator", value=role_mention(config["creator_role_id"]), inline=True)
        embed.add_field(name="Admin", value=role_mention(config["admin_role_id"]), inline=True)
        embed.add_field(name="Moderator", value=role_mention(config["moderator_role_id"]), inline=True)
        embed.add_field(name="Member", value=role_mention(config["member_role_id"]), inline=True)

        db = await get_db()
        cursor = await db.execute(
            "SELECT command_name, required_level FROM command_permissions WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        overrides = await cursor.fetchall()
        if overrides:
            text = "\n".join(f"`{row['command_name']}` → {LEVEL_NAMES[row['required_level']]}" for row in overrides)
            embed.add_field(name="Surcharges de commandes", value=text, inline=False)

        await interaction.response.send_message(embed=embed)

    # ---------- /permission command ----------
    @permission_group.command(name="command", description="Définit le niveau requis pour une commande")
    @app_commands.describe(commande="Nom de la commande (ex: ban)", niveau="Member, Moderator, Admin ou Creator")
    @app_commands.choices(niveau=[
        app_commands.Choice(name="Member", value="member"),
        app_commands.Choice(name="Moderator", value="moderator"),
        app_commands.Choice(name="Admin", value="admin"),
        app_commands.Choice(name="Creator", value="creator"),
    ])
    @require_level("permission")
    async def permission_command(self, interaction: discord.Interaction, commande: str, niveau: app_commands.Choice[str]):
        level = NAME_TO_LEVEL[niveau.value]
        db = await get_db()
        await db.execute(
            """INSERT INTO command_permissions (guild_id, command_name, required_level)
               VALUES (?, ?, ?)
               ON CONFLICT(guild_id, command_name) DO UPDATE SET required_level = excluded.required_level""",
            (interaction.guild.id, commande.lower(), level),
        )
        await db.commit()
        await interaction.response.send_message(
            f"✅ La commande `{commande}` nécessite maintenant le niveau **{niveau.name}**"
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(str(error), ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
            raise error


async def setup(bot: commands.Bot):
    cog = Config(bot)
    bot.tree.add_command(cog.permission_group)
    await bot.add_cog(cog)
