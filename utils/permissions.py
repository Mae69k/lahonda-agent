"""
Système de permissions à 4 niveaux :
0 = Member (aucune permission spéciale)
1 = Moderator
2 = Admin
3 = Creator (accès total, généralement le/la propriétaire du serveur)

Chaque commande a un niveau minimum requis (par défaut défini dans DEFAULT_LEVELS,
mais surchargeable par serveur via /permission command).
"""

import discord
from discord import app_commands
from utils.database import get_db, get_guild_config

LEVEL_NAMES = {0: "Member", 1: "Moderator", 2: "Admin", 3: "Creator"}
NAME_TO_LEVEL = {v.lower(): k for k, v in LEVEL_NAMES.items()}

# Niveau par défaut requis pour chaque commande si aucune surcharge n'est configurée
DEFAULT_LEVELS = {
    "warn": 1, "warnings": 1, "unwarn": 1, "clearwarnings": 2,
    "timeout": 1, "untimeout": 1, "kick": 1, "ban": 2, "unban": 2,
    "purge": 1, "slowmode": 1, "lock": 1, "unlock": 1, "nick": 1,
    "note": 1, "history": 1, "case": 1, "quarantine": 2, "unquarantine": 2,
    "antispam": 2, "antilink": 2, "antiraid": 2, "antinuke": 3,
    "lockdown": 2, "security": 2, "logs": 2, "panic": 3,
    "config": 3, "permissions": 3, "permission": 3,
}


async def get_user_level(member: discord.Member) -> int:
    """Retourne le niveau de permission le plus élevé d'un membre."""
    if member.guild.owner_id == member.id or member.guild_permissions.administrator:
        return 3

    config = await get_guild_config(member.guild.id)
    role_ids = {r.id for r in member.roles}

    if config["creator_role_id"] and config["creator_role_id"] in role_ids:
        return 3
    if config["admin_role_id"] and config["admin_role_id"] in role_ids:
        return 2
    if config["moderator_role_id"] and config["moderator_role_id"] in role_ids:
        return 1
    return 0


async def get_required_level(guild_id: int, command_name: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT required_level FROM command_permissions WHERE guild_id = ? AND command_name = ?",
        (guild_id, command_name),
    )
    row = await cursor.fetchone()
    if row is not None:
        return row["required_level"]
    return DEFAULT_LEVELS.get(command_name, 1)


def require_level(command_name: str):
    """Decorator/check à utiliser sur les commandes slash pour vérifier la permission."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False

        required = await get_required_level(interaction.guild.id, command_name)
        user_level = await get_user_level(interaction.user)

        if user_level < required:
            raise app_commands.CheckFailure(
                f"🚫 Tu dois être au moins **{LEVEL_NAMES[required]}** pour utiliser cette commande."
            )
        return True

    return app_commands.check(predicate)
