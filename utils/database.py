import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lahonda.db")

_connection: aiosqlite.Connection = None


async def get_db() -> aiosqlite.Connection:
    global _connection
    if _connection is None:
        _connection = await aiosqlite.connect(DB_PATH)
        _connection.row_factory = aiosqlite.Row
    return _connection


async def init_db():
    db = await get_db()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            creator_role_id INTEGER,
            admin_role_id INTEGER,
            moderator_role_id INTEGER,
            member_role_id INTEGER,
            log_moderation_channel INTEGER,
            log_security_channel INTEGER,
            log_members_channel INTEGER,
            log_messages_channel INTEGER,
            log_server_channel INTEGER,
            panic_mode INTEGER DEFAULT 0,
            next_case_number INTEGER DEFAULT 1
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS command_permissions (
            guild_id INTEGER,
            command_name TEXT,
            required_level INTEGER,
            PRIMARY KEY (guild_id, command_name)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            timestamp TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            case_number INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            action TEXT,
            reason TEXT,
            timestamp TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            note TEXT,
            timestamp TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS antispam_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            max_messages INTEGER DEFAULT 5,
            interval_seconds INTEGER DEFAULT 5,
            action TEXT DEFAULT 'timeout'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS antilink_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            action TEXT DEFAULT 'delete'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS antilink_whitelist (
            guild_id INTEGER,
            domain TEXT,
            PRIMARY KEY (guild_id, domain)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS antilink_blacklist (
            guild_id INTEGER,
            domain TEXT,
            PRIMARY KEY (guild_id, domain)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS antiraid_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            join_threshold INTEGER DEFAULT 10,
            interval_seconds INTEGER DEFAULT 10,
            action TEXT DEFAULT 'kick'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS antinuke_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            ban_threshold INTEGER DEFAULT 3,
            channel_delete_threshold INTEGER DEFAULT 3,
            role_delete_threshold INTEGER DEFAULT 3,
            interval_seconds INTEGER DEFAULT 10,
            action TEXT DEFAULT 'quarantine'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS quarantine (
            guild_id INTEGER,
            user_id INTEGER,
            original_roles TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    await db.commit()


async def get_guild_config(guild_id: int) -> aiosqlite.Row:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO guild_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
        cursor = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
    return row


async def update_guild_config(guild_id: int, **kwargs):
    db = await get_db()
    await get_guild_config(guild_id)  # s'assure que la ligne existe
    columns = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [guild_id]
    await db.execute(f"UPDATE guild_config SET {columns} WHERE guild_id = ?", values)
    await db.commit()


async def next_case_number(guild_id: int) -> int:
    config = await get_guild_config(guild_id)
    number = config["next_case_number"]
    await update_guild_config(guild_id, next_case_number=number + 1)
    return number
