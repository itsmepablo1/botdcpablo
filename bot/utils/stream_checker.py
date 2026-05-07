import aiohttp
import asyncio
from bot.config import YOUTUBE_API_KEY

# ── YouTube Live Checker ──────────────────────────────────────────────────────

async def check_youtube_live(channel_id_or_handle: str) -> dict | None:
    """
    Check if a YouTube channel is live.
    Returns dict with stream info or None if not live.
    Requires YOUTUBE_API_KEY in .env.
    """
    if not YOUTUBE_API_KEY:
        return None

    # Resolve handle/channel to channel ID if needed
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key":        YOUTUBE_API_KEY,
        "channelId":  channel_id_or_handle,
        "eventType":  "live",
        "type":       "video",
        "part":       "snippet",
        "maxResults": 1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                items = data.get("items", [])
                if not items:
                    return None
                item = items[0]
                video_id = item["id"]["videoId"]
                title    = item["snippet"]["title"]
                thumb    = item["snippet"]["thumbnails"]["high"]["url"]
                return {
                    "platform":   "YouTube",
                    "title":      title,
                    "url":        f"https://youtube.com/watch?v={video_id}",
                    "thumbnail":  thumb,
                    "channel":    item["snippet"]["channelTitle"],
                }
    except Exception:
        return None

# ── TikTok Live Checker ───────────────────────────────────────────────────────

async def check_tiktok_live(username: str) -> dict | None:
    """
    Check if a TikTok user is currently live via scraping.
    Returns stream info dict or None.
    """
    url = f"https://www.tiktok.com/@{username}/live"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                text = await resp.text()
                # TikTok redirects away from /live when not streaming
                if "/live" not in str(resp.url) or resp.status != 200:
                    return None
                if '"status":4' in text or '"liveRoomInfo"' in text:
                    return {
                        "platform": "TikTok",
                        "title":    f"{username} sedang LIVE di TikTok!",
                        "url":      f"https://www.tiktok.com/@{username}/live",
                        "thumbnail": None,
                        "channel":  username,
                    }
    except Exception:
        return None
    return None

# ── Discord Activity Helper ───────────────────────────────────────────────────

def get_streaming_activity(member) -> dict | None:
    """
    Returns streaming info from Discord's built-in Streaming activity.
    Works for Twitch and any stream captured by Discord overlay.
    """
    import discord
    for activity in member.activities:
        if isinstance(activity, discord.Streaming):
            platform = activity.platform or "Unknown"
            if activity.twitch_name:
                platform = "Twitch"
            elif activity.url and "youtube" in activity.url.lower():
                platform = "YouTube"
            elif activity.url and "tiktok" in activity.url.lower():
                platform = "TikTok"
            return {
                "platform":  platform,
                "title":     activity.name or f"{member.display_name} is streaming",
                "url":       activity.url or "",
                "thumbnail": activity.assets.get("large_image") if activity.assets else None,
                "channel":   member.display_name,
            }
    return None
