"""
stream_notif.py — Background task untuk cek YouTube & TikTok
- YouTube: RSS feed (no API key)
- TikTok: yt-dlp scrape
- Jalan setiap 5 menit
"""
import asyncio
import aiohttp
import subprocess
import json
import re
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import discord
from discord.ext import commands, tasks

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db
from bot.config import DATABASE_PATH

YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_ytdlp(args: list, timeout: int = 30) -> dict | None:
    try:
        r = subprocess.run(
            [YTDLP, "--no-warnings", "--quiet"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout.strip().splitlines()[0])
    except Exception as e:
        print(f"[StreamNotif] yt-dlp error: {e}", flush=True)
        return None


async def resolve_youtube_channel(url: str) -> tuple[str, str, str] | None:
    """
    Kembalikan (channel_id, channel_name, thumbnail_url) dari URL YouTube.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
        return _run_ytdlp([
            "--dump-json", "--playlist-items", "1",
            "--no-playlist", "--flat-playlist",
            url
        ], timeout=30)

    data = await loop.run_in_executor(None, _fetch)

    # Coba extract channel_id dari URL langsung
    m = re.search(r"channel/(UC[\w-]+)", url)
    if m:
        cid = m.group(1)
        name = data.get("uploader", "Unknown") if data else "Unknown"
        thumb = data.get("uploader_url", "") if data else ""
        return cid, name, ""

    if data:
        ch_id  = data.get("channel_id") or data.get("uploader_id", "")
        ch_name = data.get("uploader") or data.get("channel", "Unknown")
        return ch_id, ch_name, ""

    return None


async def resolve_tiktok_channel(url: str) -> tuple[str, str] | None:
    """Kembalikan (channel_username, channel_name)."""
    m = re.search(r"tiktok\.com/@([\w.]+)", url)
    if not m:
        return None
    username = m.group(1)
    return username, username


async def fetch_latest_youtube(channel_id: str) -> dict | None:
    """Ambil video terbaru via RSS. Kembalikan dict atau None."""
    url = YT_RSS.format(channel_id=channel_id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                text = await r.text()
        root = ET.fromstring(text)
        ns = {
            "atom":  "http://www.w3.org/2005/Atom",
            "yt":    "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None
        vid_id  = entry.findtext("yt:videoId",   namespaces=ns)
        title   = entry.findtext("atom:title",   namespaces=ns)
        link_el = entry.find("atom:link",        ns)
        link    = link_el.get("href", "") if link_el is not None else f"https://youtu.be/{vid_id}"
        thumb   = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
        author  = entry.find("atom:author/atom:name", ns)
        ch_name = author.text if author is not None else "Unknown"
        return {"id": vid_id, "title": title, "url": link, "thumbnail": thumb, "channel": ch_name}
    except Exception as e:
        print(f"[StreamNotif] YT RSS error: {e}", flush=True)
        return None


async def fetch_latest_tiktok(username: str) -> dict | None:
    """Scrape video terbaru TikTok via yt-dlp."""
    loop = asyncio.get_event_loop()

    def _fetch():
        return _run_ytdlp([
            "--dump-json", "--playlist-items", "1",
            f"https://www.tiktok.com/@{username}"
        ], timeout=40)

    data = await loop.run_in_executor(None, _fetch)
    if not data:
        return None
    return {
        "id":        data.get("id", ""),
        "title":     data.get("title", ""),
        "url":       data.get("webpage_url", f"https://tiktok.com/@{username}"),
        "thumbnail": data.get("thumbnail", ""),
        "channel":   data.get("uploader", username),
    }


# ── Notification Embed ────────────────────────────────────────────────────────

def make_notif_embed(platform: str, video: dict, message: str) -> discord.Embed:
    color = 0xFF0000 if platform == "youtube" else 0x010101
    icon  = "🔴" if platform == "youtube" else "🎵"
    ch_name = video.get("channel", "Unknown")
    desc = message.replace("{channel}", f"**{ch_name}**") \
                  .replace("{title}", video.get("title", "")) \
                  .replace("{url}", video.get("url", ""))
    e = discord.Embed(
        title=video.get("title", ""),
        url=video.get("url", ""),
        description=desc,
        color=color,
    )
    e.set_author(name=f"{icon} {ch_name}")
    if video.get("thumbnail"):
        e.set_image(url=video["thumbnail"])
    e.set_footer(text=f"Notifikasi via {platform.title()}")
    e.timestamp = datetime.utcnow()
    return e


# ── Cog ───────────────────────────────────────────────────────────────────────

class StreamNotif(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    @tasks.loop(minutes=5)
    async def check_loop(self):
        await self.bot.wait_until_ready()
        try:
            rows = await db.get_all_tracked_streamers()
        except Exception as e:
            print(f"[StreamNotif] DB error: {e}", flush=True)
            return

        for row in rows:
            if row["status"] != "running":
                continue
            try:
                await self._check_one(row)
            except Exception as e:
                print(f"[StreamNotif] check error for {row['channel_url']}: {e}", flush=True)

    async def _check_one(self, row: dict):
        platform = row["platform"]
        guild    = self.bot.get_guild(row["guild_id"])
        if not guild:
            return
        channel = guild.get_channel(row["discord_channel_id"])
        if not channel:
            return

        if platform == "youtube":
            video = await fetch_latest_youtube(row["platform_channel_id"])
            if not video:
                return
            if video["id"] == row.get("last_video_id"):
                return
            # Video baru!
            await db.update_streamer_last_video(row["id"], video["id"])
            msg_tpl = row.get("video_message") or "{channel} just posted a new video!"
            embed   = make_notif_embed("youtube", video, msg_tpl)
            ping    = f"<@&{row['ping_role_id']}> " if row.get("ping_role_id") else ""
            await channel.send(content=ping or None, embed=embed)
            print(f"[StreamNotif] YT notif sent: {video['title']}", flush=True)

        elif platform == "tiktok":
            video = await fetch_latest_tiktok(row["platform_channel_id"])
            if not video:
                return
            if video["id"] == row.get("last_video_id"):
                return
            await db.update_streamer_last_video(row["id"], video["id"])
            msg_tpl = row.get("video_message") or "{channel} just posted a new video!"
            embed   = make_notif_embed("tiktok", video, msg_tpl)
            ping    = f"<@&{row['ping_role_id']}> " if row.get("ping_role_id") else ""
            await channel.send(content=ping or None, embed=embed)
            print(f"[StreamNotif] TikTok notif sent: {video['title']}", flush=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StreamNotif(bot))
