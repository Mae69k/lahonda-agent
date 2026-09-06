import discord
from discord import app_commands
from discord.ext import commands
import datetime

from utils.database import get_db, get_guild_config, next_case_number
from utils.permissions import require_level


async def log_to_channel(guild: discord.Guild, channel_column: str, embed: discord.Embed):
    config = await get_guild_config(guild.id)
    channel_id = config[channel_column]
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)


async def create_case(guild_id: int, user_id: int, moderator_id: int, action: str, reason: str) -> int:
    case_number = await next_case_number(guild_id)
    db = await get_db()
    await db.execute(
        """INSERT INTO cases (guild_id, case_number, user_id, moderator_id, action, reason, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (guild_id, case_number, user_id, moderator_id, action, reason, datetime.datetime.now().isoformat()),
    )
    await db.commit()
    return case_number


def hierarchy_ok(actor: discord.Member, target: discord.Member) -> bool:
    return actor.id == actor.guild.owner_id or actor.top_role > target.top_role


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    case_group = app_commands.Group(name="case", description="Consulter et modifier les dossiers de modération")

    # ---------- WARN ----------
    @app_commands.command(name="warn", description="Avertit un membre")
    @require_level("warn")
    async def warn(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        db = await get_db()
        await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild.id, membre.id, interaction.user.id, raison, datetime.datetime.now().isoformat()),
        )
        await db.commit()
        case_number = await create_case(interaction.guild.id, membre.id, interaction.user.id, "warn", raison)

        embed = discord.Embed(title=f"⚠️ Avertissement — Dossier #{case_number}", color=discord.Color.yellow())
        embed.add_field(name="Membre", value=f"{membre} ({membre.id})", inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=False)
        embed.add_field(name="Raison", value=raison, inline=False)

        await interaction.response.send_message(embed=embed)
        await log_to_channel(interaction.guild, "log_moderation_channel", embed)
        try:
            await membre.send(f"Tu as reçu un avertissement sur **{interaction.guild.name}**.\nRaison : {raison}")
        except discord.Forbidden:
            pass

    # ---------- WARNINGS ----------
    @app_commands.command(name="warnings", description="Affiche les avertissements d'un membre")
    @require_level("warnings")
    async def warnings(self, interaction: discord.Interaction, membre: discord.Member):
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, moderator_id, reason, timestamp FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
            (interaction.guild.id, membre.id),
        )
        rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message(f"{membre.mention} n'a aucun avertissement.")
            return

        embed = discord.Embed(title=f"⚠️ Avertissements de {membre}", color=discord.Color.yellow())
        for row in rows[:15]:
            mod = interaction.guild.get_member(row["moderator_id"])
            embed.add_field(
                name=f"#{row['id']} — {row['timestamp'][:10]}",
                value=f"Par : {mod.mention if mod else row['moderator_id']}\nRaison : {row['reason']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    # ---------- UNWARN ----------
    @app_commands.command(name="unwarn", description="Supprime un avertissement précis par son ID")
    @require_level("unwarn")
    async def unwarn(self, interaction: discord.Interaction, warning_id: int):
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM warnings WHERE id = ? AND guild_id = ?", (warning_id, interaction.guild.id)
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("❌ Avertissement introuvable.", ephemeral=True)
            return
        await db.execute("DELETE FROM warnings WHERE id = ?", (warning_id,))
        await db.commit()
        await interaction.response.send_message(f"✅ Avertissement #{warning_id} supprimé.")

    # ---------- CLEARWARNINGS ----------
    @app_commands.command(name="clearwarnings", description="Supprime tous les avertissements d'un membre")
    @require_level("clearwarnings")
    async def clearwarnings(self, interaction: discord.Interaction, membre: discord.Member):
        db = await get_db()
        await db.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, membre.id))
        await db.commit()
        await interaction.response.send_message(f"✅ Tous les avertissements de {membre.mention} ont été supprimés.")

    # ---------- TIMEOUT / UNTIMEOUT ----------
    @app_commands.command(name="timeout", description="Mute temporairement un membre")
    @require_level("timeout")
    async def timeout(self, interaction: discord.Interaction, membre: discord.Member, minutes: int, raison: str = "Aucune raison fournie"):
        if not hierarchy_ok(interaction.user, membre):
            await interaction.response.send_message("⚠️ Hiérarchie de rôles insuffisante.", ephemeral=True)
            return
        await membre.timeout(datetime.timedelta(minutes=minutes), reason=raison)
        case_number = await create_case(interaction.guild.id, membre.id, interaction.user.id, "timeout", raison)

        embed = discord.Embed(title=f"🔇 Timeout — Dossier #{case_number}", color=discord.Color.gold())
        embed.add_field(name="Membre", value=f"{membre} ({membre.id})", inline=False)
        embed.add_field(name="Durée", value=f"{minutes} min", inline=False)
        embed.add_field(name="Raison", value=raison, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_to_channel(interaction.guild, "log_moderation_channel", embed)

    @app_commands.command(name="untimeout", description="Retire le timeout d'un membre")
    @require_level("untimeout")
    async def untimeout(self, interaction: discord.Interaction, membre: discord.Member):
        await membre.timeout(None)
        await interaction.response.send_message(f"🔊 {membre.mention} n'est plus en timeout.")

    # ---------- KICK ----------
    @app_commands.command(name="kick", description="Expulse un membre")
    @require_level("kick")
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        if not hierarchy_ok(interaction.user, membre):
            await interaction.response.send_message("⚠️ Hiérarchie de rôles insuffisante.", ephemeral=True)
            return
        await membre.kick(reason=raison)
        case_number = await create_case(interaction.guild.id, membre.id, interaction.user.id, "kick", raison)

        embed = discord.Embed(title=f"👢 Expulsion — Dossier #{case_number}", color=discord.Color.orange())
        embed.add_field(name="Membre", value=f"{membre} ({membre.id})", inline=False)
        embed.add_field(name="Raison", value=raison, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_to_channel(interaction.guild, "log_moderation_channel", embed)

    # ---------- BAN / UNBAN ----------
    @app_commands.command(name="ban", description="Bannit un membre")
    @require_level("ban")
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        if not hierarchy_ok(interaction.user, membre):
            await interaction.response.send_message("⚠️ Hiérarchie de rôles insuffisante.", ephemeral=True)
            return
        await membre.ban(reason=raison)
        case_number = await create_case(interaction.guild.id, membre.id, interaction.user.id, "ban", raison)

        embed = discord.Embed(title=f"🔨 Bannissement — Dossier #{case_number}", color=discord.Color.red())
        embed.add_field(name="Membre", value=f"{membre} ({membre.id})", inline=False)
        embed.add_field(name="Raison", value=raison, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_to_channel(interaction.guild, "log_moderation_channel", embed)

    @app_commands.command(name="unban", description="Débannit un membre via son ID")
    @require_level("unban")
    async def unban(self, interaction: discord.Interaction, user_id: str, raison: str = "Aucune raison fournie"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=raison)
            await create_case(interaction.guild.id, user.id, interaction.user.id, "unban", raison)
            await interaction.response.send_message(f"✅ {user} a été débanni.")
        except (discord.NotFound, ValueError):
            await interaction.response.send_message("❌ Utilisateur introuvable ou non banni.", ephemeral=True)

    # ---------- PURGE ----------
    @app_commands.command(name="purge", description="Supprime un nombre de messages dans le salon")
    @require_level("purge")
    async def purge(self, interaction: discord.Interaction, nombre: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=nombre)
        await interaction.followup.send(f"🧹 {len(deleted)} message(s) supprimé(s).", ephemeral=True)

    # ---------- SLOWMODE ----------
    @app_commands.command(name="slowmode", description="Définit le mode lent du salon (en secondes)")
    @require_level("slowmode")
    async def slowmode(self, interaction: discord.Interaction, secondes: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=secondes)
        await interaction.response.send_message(f"🐌 Mode lent réglé sur {secondes}s dans ce salon.")

    # ---------- LOCK / UNLOCK ----------
    @app_commands.command(name="lock", description="Verrouille le salon actuel")
    @require_level("lock")
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 Salon verrouillé.")

    @app_commands.command(name="unlock", description="Déverrouille le salon actuel")
    @require_level("unlock")
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 Salon déverrouillé.")

    # ---------- NICK ----------
    @app_commands.command(name="nick", description="Change le pseudo d'un membre")
    @require_level("nick")
    async def nick(self, interaction: discord.Interaction, membre: discord.Member, pseudo: str = None):
        await membre.edit(nick=pseudo)
        await interaction.response.send_message(f"✅ Pseudo de {membre.mention} mis à jour.")

    # ---------- NOTE ----------
    @app_commands.command(name="note", description="Ajoute une note privée sur un membre")
    @require_level("note")
    async def note(self, interaction: discord.Interaction, membre: discord.Member, contenu: str):
        db = await get_db()
        await db.execute(
            "INSERT INTO notes (guild_id, user_id, moderator_id, note, timestamp) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild.id, membre.id, interaction.user.id, contenu, datetime.datetime.now().isoformat()),
        )
        await db.commit()
        await interaction.response.send_message(f"📝 Note ajoutée pour {membre.mention}.", ephemeral=True)

    # ---------- HISTORY ----------
    @app_commands.command(name="history", description="Affiche l'historique complet de modération d'un membre")
    @require_level("history")
    async def history(self, interaction: discord.Interaction, membre: discord.Member):
        db = await get_db()
        cursor = await db.execute(
            "SELECT case_number, action, reason, timestamp FROM cases WHERE guild_id = ? AND user_id = ? ORDER BY case_number DESC",
            (interaction.guild.id, membre.id),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message(f"{membre.mention} n'a aucun historique.")
            return

        embed = discord.Embed(title=f"📜 Historique de {membre}", color=discord.Color.blurple())
        for row in rows[:15]:
            embed.add_field(
                name=f"#{row['case_number']} — {row['action'].upper()} ({row['timestamp'][:10]})",
                value=row["reason"],
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    # ---------- CASE (group: view / edit / reason) ----------
    @case_group.command(name="view", description="Affiche le détail d'un dossier de modération")
    @require_level("case")
    async def case_view(self, interaction: discord.Interaction, numero: int):
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM cases WHERE guild_id = ? AND case_number = ?", (interaction.guild.id, numero)
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("❌ Dossier introuvable.", ephemeral=True)
            return

        user = self.bot.get_user(row["user_id"])
        mod = self.bot.get_user(row["moderator_id"])
        embed = discord.Embed(title=f"📁 Dossier #{numero}", color=discord.Color.blurple())
        embed.add_field(name="Membre", value=f"{user or row['user_id']}", inline=True)
        embed.add_field(name="Modérateur", value=f"{mod or row['moderator_id']}", inline=True)
        embed.add_field(name="Action", value=row["action"], inline=True)
        embed.add_field(name="Raison", value=row["reason"], inline=False)
        embed.add_field(name="Date", value=row["timestamp"][:19], inline=False)
        await interaction.response.send_message(embed=embed)

    @case_group.command(name="edit", description="Modifie l'action associée à un dossier")
    @require_level("case")
    async def case_edit(self, interaction: discord.Interaction, numero: int, nouvelle_action: str):
        db = await get_db()
        await db.execute(
            "UPDATE cases SET action = ? WHERE guild_id = ? AND case_number = ?",
            (nouvelle_action, interaction.guild.id, numero),
        )
        await db.commit()
        await interaction.response.send_message(f"✅ Dossier #{numero} mis à jour.")

    @case_group.command(name="reason", description="Modifie la raison d'un dossier")
    @require_level("case")
    async def case_reason(self, interaction: discord.Interaction, numero: int, nouvelle_raison: str):
        db = await get_db()
        await db.execute(
            "UPDATE cases SET reason = ? WHERE guild_id = ? AND case_number = ?",
            (nouvelle_raison, interaction.guild.id, numero),
        )
        await db.commit()
        await interaction.response.send_message(f"✅ Raison du dossier #{numero} mise à jour.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message(str(error), ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
            raise error


async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    bot.tree.add_command(cog.case_group)
    await bot.add_cog(cog)
