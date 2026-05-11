"""
panel/routers/streamers.py — CRUD API untuk tracked YouTube & TikTok channels
"""
import re
import asyncio
import subprocess
import json
import sys, os
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from bot import database as db
from panel.routers.auth import verify_token

router = APIRouter()

YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

LIMITS = {"youtube": 30, "tiktok": 10}


# ── Pydantic ──────────────────────────────────────────────────────────────────

class AddStreamerRequest(BaseModel):
    platform:          str
    channel_url:       str
    discord_channel_id: Any
    ping_role_id:      Any = None
    content_type:      str = "all"
    video_message:     str = "{channel} just posted a new video!"
    live_message:      str = "{channel} is live!"
    status:            str = "running"

class UpdateStreamerRequest(BaseModel):
    discord_channel_id: Any = None
    ping_role_id:       Any = None
    content_type:       str | None = None
    video_message:      str | None = None
    live_message:       str | None = None
    status:             str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_platform(url: str) -> str | None:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "tiktok.com" in url:
        return "tiktok"
    return None


def _resolve_yt_channel_id(url: str) -> str | None:
    """Coba extract UC... dari URL langsung."""
    m = re.search(r"channel/(UC[\w-]+)", url)
    if m:
        return m.group(1)
    return None


def _run_ytdlp_sync(args: list, timeout: int = 30) -> dict | None:
    try:
        r = subprocess.run(
            [YTDLP, "--no-warnings", "--quiet"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout.strip().splitlines()[0])
    except Exception as e:
        print(f"[Streamers API] yt-dlp: {e}", flush=True)
        return None


async def _resolve_channel_info(platform: str, url: str) -> tuple[str, str]:
    """Return (platform_channel_id, channel_name)."""
    loop = asyncio.get_event_loop()

    if platform == "youtube":
        # Coba extract langsung dari URL
        cid = _resolve_yt_channel_id(url)
        if cid:
            return cid, "YouTube Channel"
        # Fallback: yt-dlp
        def _fetch():
            return _run_ytdlp_sync([
                "--dump-json", "--playlist-items", "1", "--flat-playlist", url
            ], timeout=30)
        data = await loop.run_in_executor(None, _fetch)
        if data:
            cid   = data.get("channel_id") or data.get("uploader_id", url)
            name  = data.get("uploader") or data.get("channel", "Unknown")
            return cid, name
        return url, "Unknown"

    elif platform == "tiktok":
        m = re.search(r"tiktok\.com/@([\w.]+)", url)
        username = m.group(1) if m else url
        return username, f"@{username}"

    return url, "Unknown"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{guild_id}")
async def list_streamers(guild_id: str, platform: str | None = None,
                         _=Depends(verify_token)):
    rows = await db.get_tracked_streamers(int(guild_id), platform or None)
    return {"streamers": rows}


@router.post("/{guild_id}")
async def add_streamer(guild_id: str, data: AddStreamerRequest,
                       _=Depends(verify_token)):
    gid = int(guild_id)

    # Auto-detect platform jika perlu
    platform = data.platform.lower()
    if platform not in ("youtube", "tiktok"):
        platform = _detect_platform(data.channel_url) or "youtube"

    # Cek limit
    existing = await db.get_tracked_streamers(gid, platform)
    limit = LIMITS.get(platform, 10)
    if len(existing) >= limit:
        raise HTTPException(400, f"Limit {limit} channel {platform} tercapai.")

    # Resolve channel info
    platform_id, channel_name = await _resolve_channel_info(platform, data.channel_url)

    try:
        discord_ch_id = int(str(data.discord_channel_id)) if data.discord_channel_id else None
        ping_role_id  = int(str(data.ping_role_id)) if data.ping_role_id else None
    except (ValueError, TypeError):
        raise HTTPException(422, "discord_channel_id atau ping_role_id tidak valid.")

    if not discord_ch_id:
        raise HTTPException(422, "discord_channel_id wajib diisi.")

    streamer_id = await db.add_tracked_streamer(
        guild_id=gid,
        platform=platform,
        channel_url=data.channel_url,
        platform_channel_id=platform_id,
        channel_name=channel_name,
        discord_channel_id=discord_ch_id,
        ping_role_id=ping_role_id,
        content_type=data.content_type,
        video_message=data.video_message,
        live_message=data.live_message,
    )

    # Set initial status
    if data.status and data.status != "running":
        await db.update_tracked_streamer(streamer_id, status=data.status)

    rows = await db.get_tracked_streamers(gid, platform)
    new_row = next((r for r in rows if r["id"] == streamer_id), None)
    return {"ok": True, "streamer": new_row}


@router.patch("/{guild_id}/{streamer_id}")
async def update_streamer(guild_id: str, streamer_id: int,
                          data: UpdateStreamerRequest,
                          _=Depends(verify_token)):
    gid = int(guild_id)
    updates = {}
    if data.status is not None:
        updates["status"] = data.status
    if data.content_type is not None:
        updates["content_type"] = data.content_type
    if data.video_message is not None:
        updates["video_message"] = data.video_message
    if data.live_message is not None:
        updates["live_message"] = data.live_message
    if data.discord_channel_id is not None:
        try:
            updates["discord_channel_id"] = int(str(data.discord_channel_id))
        except (ValueError, TypeError):
            pass
    if data.ping_role_id is not None:
        try:
            updates["ping_role_id"] = int(str(data.ping_role_id))
        except (ValueError, TypeError):
            updates["ping_role_id"] = None

    if updates:
        await db.update_tracked_streamer(streamer_id, **updates)
    return {"ok": True}


@router.delete("/{guild_id}/{streamer_id}")
async def delete_streamer(guild_id: str, streamer_id: int,
                           _=Depends(verify_token)):
    await db.delete_tracked_streamer(streamer_id, int(guild_id))
    return {"ok": True}
