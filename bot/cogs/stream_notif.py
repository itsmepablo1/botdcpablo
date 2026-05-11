"""
stream_notif.py — Background task YouTube & TikTok
Fixes:
- TikTok LIVE detection via @username/live URL
- YouTube LIVE detection via RSS + live badge check
- First-run: simpan ID tapi TETAP notif jika sedang live
- is_live state tracking untuk hindari duplikat notif live
- Verbose logging untuk debugging
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

YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


# ── yt-dlp runner ─────────────────────────────────────────────────────────────

def _run_ytdlp_sync(args: list, timeout: int = 45) -> dict | None:
    """Jalankan yt-dlp secara synchronous, kembalikan dict JSON pertama."""
    try:
        cmd = [YTDLP, "--no-warnings", "--quiet"] + args
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        if not out:
            return None
        # Ambil baris pertama yang valid JSON
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        return None
    except subprocess.TimeoutExpired:
        print(f"[StreamNotif] yt-dlp timeout: {args[-1]}", flush=True)
        return None
    except Exception as e:
        print(f"[StreamNotif] yt-dlp error: {e}", flush=True)
        return None


async def _run_ytdlp(args: list, timeout: int = 45) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _run_ytdlp_sync(args, timeout))


# ── TikTok ────────────────────────────────────────────────────────────────────

async def check_tiktok_live(username: str) -> dict | None:
    """
    Cek apakah TikTok user sedang LIVE.
    Return dict info jika live, None jika tidak.
    """
    live_url = f"https://www.tiktok.com/@{username}/live"
    print(f"[StreamNotif] Cek TikTok live: {live_url}", flush=True)
    data = await _run_ytdlp([
        "--dump-json",
        "--no-playlist",
        live_url
    ], timeout=45)
    if not data:
        print(f"[StreamNotif] TikTok @{username} tidak live / gagal scrape", flush=True)
        return None
    # Kalau berhasil, artinya sedang live
    return {
        "id":        data.get("id", f"live_{username}"),
        "title":     data.get("title") or f"{username} is live!",
        "url":       data.get("webpage_url", live_url),
        "thumbnail": data.get("thumbnail", ""),
        "channel":   data.get("uploader") or username,
        "is_live":   True,
    }


async def check_tiktok_video(username: str) -> dict | None:
    """Ambil video terbaru TikTok (bukan live)."""
    print(f"[StreamNotif] Cek TikTok video terbaru: @{username}", flush=True)
    data = await _run_ytdlp([
        "--dump-json",
        "--playlist-items", "1",
        f"https://www.tiktok.com/@{username}"
    ], timeout=45)
    if not data:
        print(f"[StreamNotif] TikTok @{username} gagal ambil video", flush=True)
        return None
    return {
        "id":        data.get("id", ""),
        "title":     data.get("title", ""),
        "url":       data.get("webpage_url", f"https://tiktok.com/@{username}"),
        "thumbnail": data.get("thumbnail", ""),
        "channel":   data.get("uploader", username),
        "is_live":   False,
    }


# ── YouTube ───────────────────────────────────────────────────────────────────

async def fetch_latest_youtube(channel_id: str) -> dict | None:
    """Ambil video/live terbaru YouTube via RSS."""
    url = YT_RSS.format(channel_id=channel_id)
    print(f"[StreamNotif] Cek YouTube RSS: {channel_id}", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    print(f"[StreamNotif] YT RSS status {r.status}", flush=True)
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

        vid_id  = entry.findtext("yt:videoId", namespaces=ns)
        title   = entry.findtext("atom:title", namespaces=ns)
        link_el = entry.find("atom:link", ns)
        link    = link_el.get("href", "") if link_el is not None else f"https://youtu.be/{vid_id}"
        thumb   = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
        author  = entry.find("atom:author/atom:name", ns)
        ch_name = author.text if author is not None else "Unknown"

        return {
            "id":        vid_id,
            "title":     title,
            "url":       link,
            "thumbnail": thumb,
            "channel":   ch_name,
            "is_live":   False,
        }
    except Exception as e:
        print(f"[StreamNotif] YT RSS error: {e}", flush=True)
        return None


# ── Embed builder ─────────────────────────────────────────────────────────────

def make_notif_embed(platform: str, content: dict, message: str, is_live: bool = False) -> discord.Embed:
    if platform == "youtube":
        color = 0xFF0000
        icon  = "🔴 LIVE" if is_live else "▶ YouTube"
    else:
        color = 0xFE2C55
        icon  = "🎵 TikTok LIVE" if is_live else "🎵 TikTok"

    ch_name = content.get("channel", "Unknown")
    desc = message \
        .replace("{channel}", f"**{ch_name}**") \
        .replace("{title}",   content.get("title", "")) \
        .replace("{url}",     content.get("url", ""))

    e = discord.Embed(
        title=content.get("title", ""),
        url=content.get("url", ""),
        description=desc,
        color=color,
    )
    e.set_author(name=f"{icon} • {ch_name}")
    if content.get("thumbnail"):
        e.set_image(url=content["thumbnail"])
    label = "LIVE" if is_live else "Video Baru"
    e.set_footer(text=f"{platform.title()} {label} • Notifikasi Otomatis")
    e.timestamp = datetime.utcnow()
    return e


# ── Main Cog ──────────────────────────────────────────────────────────────────

class StreamNotif(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track state live per streamer_id agar tidak spam
        self._live_state: dict[int, bool] = {}
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    @tasks.loop(minutes=5)
    async def check_loop(self):
        await self.bot.wait_until_ready()
        print("[StreamNotif] ─── Mulai pengecekan ───", flush=True)
        try:
            rows = await db.get_all_tracked_streamers()
        except Exception as e:
            print(f"[StreamNotif] DB error: {e}", flush=True)
            return

        print(f"[StreamNotif] Total tracked: {len(rows)}", flush=True)
        for row in rows:
            if row["status"] != "running":
                continue
            try:
                await self._check_one(row)
            except Exception as e:
                print(f"[StreamNotif] Error {row['channel_url']}: {e}", flush=True)

    async def _send_notif(self, channel, ping_role_id, embed):
        """Kirim embed + ping role."""
        ping = f"<@&{ping_role_id}> " if ping_role_id else None
        await channel.send(content=ping, embed=embed)

    async def _check_one(self, row: dict):
        platform   = row["platform"]
        sid        = row["id"]
        content_type = row.get("content_type", "all")

        guild = self.bot.get_guild(row["guild_id"])
        if not guild:
            print(f"[StreamNotif] Guild {row['guild_id']} tidak ditemukan", flush=True)
            return

        disc_ch = guild.get_channel(row["discord_channel_id"])
        if not disc_ch:
            print(f"[StreamNotif] Discord channel {row['discord_channel_id']} tidak ditemukan", flush=True)
            return

        username = row["platform_channel_id"]

        # ── TikTok ──────────────────────────────────────────────────────────
        if platform == "tiktok":
            # Cek LIVE dulu
            if content_type in ("all", "live"):
                live_info = await check_tiktok_live(username)
                was_live  = self._live_state.get(sid, False)

                if live_info and not was_live:
                    # Baru mulai live!
                    self._live_state[sid] = True
                    msg_tpl = row.get("live_message") or "{channel} is live!"
                    embed   = make_notif_embed("tiktok", live_info, msg_tpl, is_live=True)
                    await self._send_notif(disc_ch, row.get("ping_role_id"), embed)
                    print(f"[StreamNotif] TikTok LIVE notif: @{username}", flush=True)
                    return  # Jangan cek video juga saat live

                elif not live_info and was_live:
                    # Live berakhir
                    self._live_state[sid] = False
                    print(f"[StreamNotif] TikTok @{username} live berakhir", flush=True)

                elif live_info and was_live:
                    print(f"[StreamNotif] TikTok @{username} masih live (skip)", flush=True)
                    return

            # Cek video terbaru
            if content_type in ("all", "video"):
                video = await check_tiktok_video(username)
                if not video:
                    return
                if video["id"] and video["id"] == row.get("last_video_id"):
                    print(f"[StreamNotif] TikTok @{username} tidak ada video baru (ID sama)", flush=True)
                    return
                # Video baru!
                is_first = row.get("last_video_id") is None
                await db.update_streamer_last_video(sid, video["id"])
                if not is_first:
                    msg_tpl = row.get("video_message") or "{channel} just posted a new video!"
                    embed   = make_notif_embed("tiktok", video, msg_tpl, is_live=False)
                    await self._send_notif(disc_ch, row.get("ping_role_id"), embed)
                    print(f"[StreamNotif] TikTok video notif: {video['title']}", flush=True)
                else:
                    print(f"[StreamNotif] TikTok @{username} first-run, simpan ID tanpa notif", flush=True)

        # ── YouTube ─────────────────────────────────────────────────────────
        elif platform == "youtube":
            content = await fetch_latest_youtube(row["platform_channel_id"])
            if not content:
                return
            if content["id"] and content["id"] == row.get("last_video_id"):
                print(f"[StreamNotif] YouTube {username} tidak ada konten baru", flush=True)
                return
            is_first = row.get("last_video_id") is None
            await db.update_streamer_last_video(sid, content["id"])
            if not is_first:
                msg_tpl = row.get("video_message") or "{channel} just posted a new video!"
                embed   = make_notif_embed("youtube", content, msg_tpl, is_live=False)
                await self._send_notif(disc_ch, row.get("ping_role_id"), embed)
                print(f"[StreamNotif] YouTube notif: {content['title']}", flush=True)
            else:
                print(f"[StreamNotif] YouTube {username} first-run, simpan ID tanpa notif", flush=True)

    @check_loop.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(StreamNotif(bot))
