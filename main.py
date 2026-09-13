import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import init_db

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Intents nécessaires pour la modération
intents = discord.Intents.default()
intents.members = True          # pour détecter join/leave, gérer les rôles
intents.message_content = True  # pour lire le contenu des messages (anti-spam, commandes textuelles)

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Gestionnaire d'erreur global pour toutes les commandes slash, quel que soit le cog."""
    if isinstance(error, discord.app_commands.CheckFailure):
        message = str(error) or "🚫 Tu n'as pas la permission d'utiliser cette commande."
    else:
        print(f"⚠️ Erreur dans une commande : {error!r}")
        message = f"❌ Une erreur est survenue : {error}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        # L'interaction a expiré (plus de 3s sans réponse) : impossible de répondre, on abandonne proprement
        print("⚠️ Interaction expirée avant que l'erreur ait pu être affichée à l'utilisateur.")
    except discord.HTTPException as e:
        print(f"⚠️ Impossible d'envoyer le message d'erreur : {e}")


bot.tree.on_error = on_tree_error


@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    print(f"📡 Présent sur {len(bot.guilds)} serveur(s)")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} commande(s) slash synchronisée(s)")
    except Exception as e:
        print(f"⚠️ Erreur de synchronisation des commandes slash : {e}")


async def load_cogs():
    """Charge tous les cogs (modules de commandes) du dossier cogs/"""
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("__"):
            extension = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                print(f"📦 Cog chargé : {extension}")
            except Exception as e:
                print(f"❌ Erreur en chargeant {extension} : {e}")


async def main():
    if not TOKEN:
        raise ValueError("❌ DISCORD_TOKEN introuvable. Vérifie ton fichier .env")

    await init_db()

    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
