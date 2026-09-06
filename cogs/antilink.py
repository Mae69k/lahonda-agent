import discord
from discord import app_commands
from discord.ext import commands
import re

from utils.database import get_db
from utils.permissions import require_level

URL_REGEX = re.compile(r"https?://([\w.-]+)")


async def get_antilink_config(guild_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM antilink_config WHERE guild_id = ?", (guild_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO antilink_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
        cursor = await db.execute("SELECT * FROM antilink_config WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
    return row


class AntiLink(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="antilink", description="Configuration de l'anti-lien")
    whitelist_group = app_commands.Group(name="whitelist", description="Gère la liste blanche de domaines", parent=group)
    blacklist_group = app_commands.Group(name="blacklist", description="Gère la liste noire de domaines", parent=group)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = await get_antilink_config(message.guild.id)
        if not config["enabled"]:
            return

        domains = URL_REGEX.findall(message.content)
        if not domains:
            return

        db = await get_db()
        cursor = await db.execute("SELECT domain FROM antilink_whitelist WHERE guild_id = ?", (message.guild.id,))
        whitelist = {row["domain"] for row in await cursor.fetchall()}
        cursor = await db.execute("SELECT domain FROM antilink_blacklist WHERE guild_id = ?", (message.guild.id,))
        blacklist = {row["domain"] for row in await cursor.fetchall()}

        for domain in domains:
            is_blacklisted = any(domain.endswith(bad) for bad in blacklist)
            is_whitelisted = any(domain.endswith(good) for good in whitelist)

            # Si une blacklist existe, seul son contenu est bloqué. Sinon, tout est bloqué sauf la whitelist.
            should_block = is_blacklisted if blacklist else not is_whitelisted

            if should_block:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                if config["action"] == "timeout":
                    try:
                        import datetime
                        await message.author.timeout(datetime.timedelta(minutes=5), reason="Anti-lien : domaine non autorisé")
                    except discord.Forbidden:
                        pass
                await message.channel.send(
                    f"🚫 {message.author.mention}, ce lien n'est pas autorisé ici.", delete_after=8
                )
                break

    @group.command(name="enable", description="Active l'anti-lien")
    @require_level("antilink")
    async def enable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antilink_config(interaction.guild.id)
        await db.execute("UPDATE antilink_config SET enabled = 1 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-lien activé.")

    @group.command(name="disable", description="Désactive l'anti-lien")
    @require_level("antilink")
    async def disable(self, interaction: discord.Interaction):
        db = await get_db()
        await get_antilink_config(interaction.guild.id)
        await db.execute("UPDATE antilink_config SET enabled = 0 WHERE guild_id = ?", (interaction.guild.id,))
        await db.commit()
        await interaction.response.send_message("✅ Anti-lien désactivé.")

    @group.command(name="status", description="Affiche l'état de l'anti-lien")
    @require_level("antilink")
    async def status(self, interaction: discord.Interaction):
        config = await get_antilink_config(interaction.guild.id)
        embed = discord.Embed(title="🔗 Statut Anti-Lien", color=discord.Color.blurple())
        embed.add_field(name="Activé", value="✅ Oui" if config["enabled"] else "❌ Non")
        embed.add_field(name="Action", value=config["action"])
        await interaction.response.send_message(embed=embed)

    # ---------- Whitelist ----------
    @whitelist_group.command(name="add", description="Ajoute un domaine à la liste blanche")
    @require_level("antilink")
    async def whitelist_add(self, interaction: discord.Interaction, domaine: str):
        db = await get_db()
        await db.execute(
            "INSERT OR IGNORE INTO antilink_whitelist (guild_id, domain) VALUES (?, ?)",
            (interaction.guild.id, domaine.lower()),
        )
        await db.commit()
        await interaction.response.send_message(f"✅ `{domaine}` ajouté à la liste blanche.")

    @whitelist_group.command(name="remove", description="Retire un domaine de la liste blanche")
    @require_level("antilink")
    async def whitelist_remove(self, interaction: discord.Interaction, domaine: str):
        db = await get_db()
        await db.execute(
            "DELETE FROM antilink_whitelist WHERE guild_id = ? AND domain = ?", (interaction.guild.id, domaine.lower())
        )
        await db.commit()
        await interaction.response.send_message(f"✅ `{domaine}` retiré de la liste blanche.")

    @whitelist_group.command(name="list", description="Liste les domaines autorisés")
    @require_level("antilink")
    async def whitelist_list(self, interaction: discord.Interaction):
        db = await get_db()
        cursor = await db.execute("SELECT domain FROM antilink_whitelist WHERE guild_id = ?", (interaction.guild.id,))
        rows = await cursor.fetchall()
        text = "\n".join(f"• {row['domain']}" for row in rows) or "*Aucun domaine*"
        await interaction.response.send_message(f"**Liste blanche :**\n{text}")

    # ---------- Blacklist ----------
    @blacklist_group.command(name="add", description="Ajoute un domaine à la liste noire")
    @require_level("antilink")
    async def blacklist_add(self, interaction: discord.Interaction, domaine: str):
        db = await get_db()
        await db.execute(
            "INSERT OR IGNORE INTO antilink_blacklist (guild_id, domain) VALUES (?, ?)",
            (interaction.guild.id, domaine.lower()),
        )
        await db.commit()
        await interaction.response.send_message(f"✅ `{domaine}` ajouté à la liste noire.")

    @blacklist_group.command(name="remove", description="Retire un domaine de la liste noire")
    @require_level("antilink")
    async def blacklist_remove(self, interaction: discord.Interaction, domaine: str):
        db = await get_db()
        await db.execute(
            "DELETE FROM antilink_blacklist WHERE guild_id = ? AND domain = ?", (interaction.guild.id, domaine.lower())
        )
        await db.commit()
        await interaction.response.send_message(f"✅ `{domaine}` retiré de la liste noire.")

    @blacklist_group.command(name="list", description="Liste les domaines interdits")
    @require_level("antilink")
    async def blacklist_list(self, interaction: discord.Interaction):
        db = await get_db()
        cursor = await db.execute("SELECT domain FROM antilink_blacklist WHERE guild_id = ?", (interaction.guild.id,))
        rows = await cursor.fetchall()
        text = "\n".join(f"• {row['domain']}" for row in rows) or "*Aucun domaine*"
        await interaction.response.send_message(f"**Liste noire :**\n{text}")


async def setup(bot: commands.Bot):
    cog = AntiLink(bot)
    bot.tree.add_command(cog.group)
    await bot.add_cog(cog)
