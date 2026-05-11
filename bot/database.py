import aiosqlite
import asyncio
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import DATABASE_PATH

async def init_db():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id        INTEGER PRIMARY KEY,
                welcome_channel_id  INTEGER,
                welcome_message     TEXT DEFAULT 'Selamat datang {member} di {server}! Kamu member ke-{count}.',
                welcome_background  TEXT,
                leave_channel_id    INTEGER,
                leave_message       TEXT DEFAULT '{member} telah meninggalkan {server}.',
                leave_background    TEXT,
                status_member_channel_id  INTEGER,
                status_online_channel_id  INTEGER,
                status_category_id        INTEGER,
                streaming_channel_id      INTEGER,
                streaming_role_id         INTEGER,
                streaming_on_stream_role_id INTEGER,
                autovoice_channel_id      INTEGER,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS role_panels (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER,
                title       TEXT DEFAULT 'Pilih Role Kamu',
                description TEXT DEFAULT 'Pilih satu atau lebih role di bawah ini.',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS role_groups (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                panel_id INTEGER NOT NULL,
                name     TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                FOREIGN KEY (panel_id) REFERENCES role_panels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS role_options (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                role_id     INTEGER NOT NULL,
                emoji       TEXT,
                description TEXT,
                position    INTEGER DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES role_groups(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS auto_voice_channels (
                channel_id  INTEGER PRIMARY KEY,
                guild_id    INTEGER NOT NULL,
                owner_id    INTEGER NOT NULL,
                name        TEXT,
                user_limit  INTEGER DEFAULT 0,
                is_locked   INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS streamer_alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                message_id  INTEGER,
                platform    TEXT,
                stream_url  TEXT,
                started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at    TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tracked_streamers (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id            INTEGER NOT NULL,
                platform            TEXT NOT NULL,
                channel_url         TEXT NOT NULL,
                platform_channel_id TEXT,
                channel_name        TEXT,
                channel_thumb       TEXT,
                discord_channel_id  INTEGER NOT NULL,
                ping_role_id        INTEGER,
                status              TEXT DEFAULT 'running',
                content_type        TEXT DEFAULT 'all',
                video_message       TEXT DEFAULT '{channel} just posted a new video!',
                live_message        TEXT DEFAULT '{channel} is live!',
                last_video_id       TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()

async def get_guild_config(guild_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}

async def set_guild_config(guild_id: int, **kwargs):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT guild_id FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            exists = await cur.fetchone()
        if exists:
            set_clause = ', '.join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [guild_id]
            await db.execute(
                f"UPDATE guild_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?",
                vals
            )
        else:
            cols = ['guild_id'] + list(kwargs.keys())
            ph   = ', '.join('?' for _ in cols)
            vals = [guild_id] + list(kwargs.values())
            await db.execute(
                f"INSERT INTO guild_config ({', '.join(cols)}) VALUES ({ph})", vals
            )
        await db.commit()

# ── Role Panels ──────────────────────────────────────────────────────────────

async def create_role_panel(guild_id: int, channel_id: int, title: str, description: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "INSERT INTO role_panels (guild_id, channel_id, title, description) VALUES (?,?,?,?)",
            (guild_id, channel_id, title, description)
        )
        await db.commit()
        return cur.lastrowid

async def get_role_panels(guild_id: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM role_panels WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def update_panel_message_id(panel_id: int, message_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE role_panels SET message_id = ? WHERE id = ?", (message_id, panel_id)
        )
        await db.commit()

async def create_role_group(panel_id: int, name: str, position: int = 0) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "INSERT INTO role_groups (panel_id, name, position) VALUES (?,?,?)",
            (panel_id, name, position)
        )
        await db.commit()
        return cur.lastrowid

async def get_role_groups(panel_id: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM role_groups WHERE panel_id = ? ORDER BY position", (panel_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def add_role_option(group_id: int, role_id: int, emoji: str, description: str, position: int = 0):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO role_options (group_id, role_id, emoji, description, position) VALUES (?,?,?,?,?)",
            (group_id, role_id, emoji, description, position)
        )
        await db.commit()

async def get_role_options(group_id: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM role_options WHERE group_id = ? ORDER BY position", (group_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def delete_role_panel(panel_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM role_panels WHERE id = ?", (panel_id,))
        await db.commit()

# ── Auto Voice ───────────────────────────────────────────────────────────────

async def add_auto_voice(channel_id: int, guild_id: int, owner_id: int, name: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO auto_voice_channels (channel_id, guild_id, owner_id, name) VALUES (?,?,?,?)",
            (channel_id, guild_id, owner_id, name)
        )
        await db.commit()

async def get_auto_voice(channel_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM auto_voice_channels WHERE channel_id = ?", (channel_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}

async def update_auto_voice(channel_id: int, **kwargs):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        set_clause = ', '.join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [channel_id]
        await db.execute(
            f"UPDATE auto_voice_channels SET {set_clause} WHERE channel_id = ?", vals
        )
        await db.commit()

async def remove_auto_voice(channel_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM auto_voice_channels WHERE channel_id = ?", (channel_id,)
        )
        await db.commit()

async def get_all_auto_voice_ids(guild_id: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT channel_id FROM auto_voice_channels WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]

async def get_all_auto_voice_details(guild_id: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM auto_voice_channels WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

# ── Streamer Alerts ───────────────────────────────────────────────────────────

async def add_streamer_alert(guild_id: int, user_id: int, platform: str, stream_url: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "INSERT INTO streamer_alerts (guild_id, user_id, platform, stream_url) VALUES (?,?,?,?)",
            (guild_id, user_id, platform, stream_url)
        )
        await db.commit()
        return cur.lastrowid

async def update_streamer_alert_message(alert_id: int, message_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE streamer_alerts SET message_id = ? WHERE id = ?", (message_id, alert_id)
        )
        await db.commit()

async def end_streamer_alert(guild_id: int, user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE streamer_alerts SET ended_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND user_id = ? AND ended_at IS NULL",
            (guild_id, user_id)
        )
        await db.commit()

async def get_active_streamer_alert(guild_id: int, user_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM streamer_alerts WHERE guild_id = ? AND user_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (guild_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}

# ── Tracked Streamers (YouTube & TikTok) ─────────────────────────────────────

async def add_tracked_streamer(
    guild_id: int, platform: str, channel_url: str,
    platform_channel_id: str, channel_name: str,
    discord_channel_id: int, ping_role_id: int | None,
    content_type: str = "all",
    video_message: str = "{channel} just posted a new video!",
    live_message: str  = "{channel} is live!",
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """INSERT INTO tracked_streamers
               (guild_id, platform, channel_url, platform_channel_id, channel_name,
                discord_channel_id, ping_role_id, content_type, video_message, live_message)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (guild_id, platform, channel_url, platform_channel_id, channel_name,
             discord_channel_id, ping_role_id, content_type, video_message, live_message)
        )
        await db.commit()
        return cur.lastrowid

async def get_tracked_streamers(guild_id: int, platform: str | None = None) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if platform:
            async with db.execute(
                "SELECT * FROM tracked_streamers WHERE guild_id=? AND platform=? ORDER BY id",
                (guild_id, platform)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute(
                "SELECT * FROM tracked_streamers WHERE guild_id=? ORDER BY platform, id",
                (guild_id,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

async def get_all_tracked_streamers() -> list:
    """Untuk background task — ambil semua row."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tracked_streamers ORDER BY id") as cur:
            return [dict(r) for r in await cur.fetchall()]

async def update_tracked_streamer(streamer_id: int, **kwargs) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [streamer_id]
        await db.execute(
            f"UPDATE tracked_streamers SET {set_clause} WHERE id = ?", vals
        )
        await db.commit()

async def update_streamer_last_video(streamer_id: int, video_id: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE tracked_streamers SET last_video_id = ? WHERE id = ?",
            (video_id, streamer_id)
        )
        await db.commit()

async def delete_tracked_streamer(streamer_id: int, guild_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM tracked_streamers WHERE id = ? AND guild_id = ?",
            (streamer_id, guild_id)
        )
        await db.commit()
