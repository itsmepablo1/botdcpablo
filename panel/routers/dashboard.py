import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from panel.routers.auth import verify_token
from bot import database as db
import aiosqlite
from bot.config import DATABASE_PATH

router = APIRouter()

@router.get("/stats")
async def get_stats(payload: dict = Depends(verify_token)):
    stats = {"total_guilds": 0, "total_members": 0, "configs": 0}
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("SELECT COUNT(*) FROM guild_config") as cur:
                row = await cur.fetchone()
                stats["configs"] = row[0] if row else 0
            async with conn.execute("SELECT COUNT(*) FROM role_panels") as cur:
                row = await cur.fetchone()
                stats["role_panels"] = row[0] if row else 0
            async with conn.execute("SELECT COUNT(*) FROM auto_voice_channels") as cur:
                row = await cur.fetchone()
                stats["active_vcs"] = row[0] if row else 0
            async with conn.execute(
                "SELECT COUNT(*) FROM streamer_alerts WHERE ended_at IS NULL"
            ) as cur:
                row = await cur.fetchone()
                stats["live_streamers"] = row[0] if row else 0
    except Exception as e:
        stats["error"] = str(e)
    return stats

@router.get("/guilds")
async def get_guilds(payload: dict = Depends(verify_token)):
    configs = []
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT * FROM guild_config ORDER BY created_at DESC") as cur:
                rows = await cur.fetchall()
                configs = [dict(r) for r in rows]
    except Exception:
        pass
    return configs
