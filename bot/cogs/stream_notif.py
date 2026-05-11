"""
stream_notif.py — YouTube & TikTok live/video notifications
Template: embed mirip NotifyMe — author, judul stream, viewers, thumbnail, Watch button
"""
import asyncio
import aiohttp
import subprocess
import json
import re
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db

WIB = timezone(timedelta(hours=7))

YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


# ── yt-dlp runner ─────────────────────────────────────────────────────────────

def _run_ytdlp_sync(args: list, timeout: int = 45) -> dict | None:
    try:
        r = subprocess.run(
            [YTDLP, "--no-warnings", "--quiet"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        out = r.stdout.strip()
        if not out:
            return None
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
    """Cek apakah TikTok user sedang LIVE. Return dict info jika live."""
    live_url = f"https://www.tiktok.com/@{username}/live"
    print(f"[StreamNotif] Cek TikTok live: {live_url}", flush=True)
    data = await _run_ytdlp(["--dump-json", "--no-playlist", live_url], timeout=45)
    if not data:
        print(f"[StreamNotif] TikTok @{username} tidak live", flush=True)
        return None

    viewers = (
        data.get("concurrent_view_count")
        or data.get("view_count")
        or 0
    )
    avatar = data.get("uploader_url") or data.get("channel_url") or ""

    return {
        "id":        data.get("id", f"live_{username}"),
        "title":     data.get("title") or f"{username} is live!",
        "url":       data.get("webpage_url", live_url),
        "thumbnail": data.get("thumbnail", ""),
        "channel":   data.get("uploader") or username,
        "avatar":    avatar,
        "viewers":   viewers,
        "is_live":   True,
    }


async def check_tiktok_video(username: str) -> dict | None:
    """Ambil video terbaru TikTok."""
    print(f"[StreamNotif] Cek TikTok video terbaru: @{username}", flush=True)
    data = await _run_ytdlp([
        "--dump-json", "--playlist-items", "1",
        f"https://www.tiktok.com/@{username}"
    ], timeout=45)
    if not data:
        return None
    return {
        "id":        data.get("id", ""),
        "title":     data.get("title", ""),
        "url":       data.get("webpage_url", f"https://tiktok.com/@{username}"),
        "thumbnail": data.get("thumbnail", ""),
        "channel":   data.get("uploader", username),
        "avatar":    "",
        "viewers":   0,
        "is_live":   False,
    }


# ── YouTube ───────────────────────────────────────────────────────────────────

async def fetch_latest_youtube(channel_id: str) -> dict | None:
    """Ambil video/live terbaru via RSS."""
    url = YT_RSS.format(channel_id=channel_id)
    print(f"[StreamNotif] Cek YouTube RSS: {channel_id}", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
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
            "avatar":    "",
            "viewers":   0,
            "is_live":   False,
        }
    except Exception as e:
        print(f"[StreamNotif] YT RSS error: {e}", flush=True)
        return None


# ── Embed + Button (template mirip NotifyMe) ──────────────────────────────────

class WatchView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="Watch Stream",
            style=discord.ButtonStyle.link,
            url=url,
            emoji="🔴",
        ))


def make_live_embed(platform: str, info: dict) -> discord.Embed:
    """Buat embed bergaya NotifyMe: author, judul, viewers, thumbnail."""
    ch_name = info.get("channel", "Unknown")
    now_wib = datetime.now(WIB)

    # Warna per platform
    color = 0xFF0000 if platform == "youtube" else 0xFE2C55

    e = discord.Embed(
        title=info.get("title", ""),
        url=info.get("url", ""),
        color=color,
    )

    # Author: nama channel + avatar (jika ada)
    avatar = info.get("avatar") or None
    e.set_author(name=ch_name, icon_url=avatar)

    # Viewers field (tampil hanya kalau ada data)
    viewers = info.get("viewers", 0)
    if viewers:
        e.add_field(name="Viewers", value=f"{viewers:,}", inline=True)

    # Thumbnail besar
    if info.get("thumbnail"):
        e.set_image(url=info["thumbnail"])

    plat_label = "YouTube" if platform == "youtube" else "TikTok"
    e.set_footer(text=f"{plat_label} LIVE • {now_wib.strftime('%d/%m/%Y %H:%M')} WIB")
    e.timestamp = now_wib
    return e


def make_video_embed(platform: str, info: dict) -> discord.Embed:
    """Buat embed untuk video baru (non-live)."""
    ch_name = info.get("channel", "Unknown")
    now_wib = datetime.now(WIB)
    color   = 0xFF0000 if platform == "youtube" else 0xFE2C55
    plat_label = "YouTube" if platform == "youtube" else "TikTok"

    e = discord.Embed(
        title=info.get("title", ""),
        url=info.get("url", ""),
        color=color,
    )
    avatar = info.get("avatar") or None
    e.set_author(name=ch_name, icon_url=avatar)
    if info.get("thumbnail"):
        e.set_image(url=info["thumbnail"])
    e.set_footer(text=f"{plat_label} Video Baru • {now_wib.strftime('%d/%m/%Y %H:%M')} WIB")
    e.timestamp = now_wib
    return e


# ── Cog ───────────────────────────────────────────────────────────────────────

class StreamNotif(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
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

    async def _send_live(self, disc_ch, ping_role_id, platform, info, row):
        """Kirim notif LIVE dengan format NotifyMe-style."""
        ch_name = info.get("channel", "Unknown")
        plat_label = "YouTube" if platform == "youtube" else "TikTok"
        stream_url = info.get("url", "")

        # Content: ping + "ChannelName 🔴 Stream Alert"
        ping_text = f"<@&{ping_role_id}> " if ping_role_id else ""
        live_msg  = row.get("live_message") or "{channel} 🔴 Stream Alert"
        content   = ping_text + live_msg.replace("{channel}", ch_name).replace("{url}", stream_url)

        embed = make_live_embed(platform, info)
        view  = WatchView(stream_url)
        await disc_ch.send(content=content, embed=embed, view=view)
        print(f"[StreamNotif] {plat_label} LIVE notif sent: {ch_name}", flush=True)

    async def _send_video(self, disc_ch, ping_role_id, platform, info, row):
        """Kirim notif video baru."""
        ch_name   = info.get("channel", "Unknown")
        video_url = info.get("url", "")
        ping_text = f"<@&{ping_role_id}> " if ping_role_id else ""
        video_msg = row.get("video_message") or "{channel} just posted a new video!"
        content   = ping_text + video_msg.replace("{channel}", ch_name).replace("{url}", video_url)

        embed = make_video_embed(platform, info)
        view  = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(
            label="Tonton Video",
            style=discord.ButtonStyle.link,
            url=video_url,
            emoji="▶",
        ))
        await disc_ch.send(content=content, embed=embed, view=view)

    async def _check_one(self, row: dict):
        platform     = row["platform"]
        sid          = row["id"]
        content_type = row.get("content_type", "all")

        guild = self.bot.get_guild(row["guild_id"])
        if not guild:
            return
        disc_ch = guild.get_channel(row["discord_channel_id"])
        if not disc_ch:
            return

        username = row["platform_channel_id"]

        # ── TikTok ──────────────────────────────────────────────────────────
        if platform == "tiktok":
            # Cek LIVE
            if content_type in ("all", "live"):
                live_info = await check_tiktok_live(username)
                was_live  = self._live_state.get(sid, False)

                if live_info and not was_live:
                    self._live_state[sid] = True
                    await self._send_live(disc_ch, row.get("ping_role_id"), "tiktok", live_info, row)
                    return

                elif not live_info and was_live:
                    self._live_state[sid] = False
                    print(f"[StreamNotif] TikTok @{username} live berakhir", flush=True)

                elif live_info and was_live:
                    print(f"[StreamNotif] TikTok @{username} masih live (skip)", flush=True)
                    return

            # Cek video terbaru
            if content_type in ("all", "video"):
                video = await check_tiktok_video(username)
                if not video or not video["id"]:
                    return
                if video["id"] == row.get("last_video_id"):
                    print(f"[StreamNotif] TikTok @{username} tidak ada video baru", flush=True)
                    return
                is_first = row.get("last_video_id") is None
                await db.update_streamer_last_video(sid, video["id"])
                if not is_first:
                    await self._send_video(disc_ch, row.get("ping_role_id"), "tiktok", video, row)
                else:
                    print(f"[StreamNotif] TikTok @{username} first-run, simpan ID tanpa notif", flush=True)

        # ── YouTube ─────────────────────────────────────────────────────────
        elif platform == "youtube":
            if content_type not in ("all", "video", "live"):
                return
            content = await fetch_latest_youtube(row["platform_channel_id"])
            if not content:
                return
            if content["id"] == row.get("last_video_id"):
                print(f"[StreamNotif] YouTube {username} tidak ada konten baru", flush=True)
                return
            is_first = row.get("last_video_id") is None
            await db.update_streamer_last_video(sid, content["id"])
            if not is_first:
                await self._send_video(disc_ch, row.get("ping_role_id"), "youtube", content, row)
            else:
                print(f"[StreamNotif] YouTube {username} first-run, simpan ID tanpa notif", flush=True)

    @check_loop.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(StreamNotif(bot))
