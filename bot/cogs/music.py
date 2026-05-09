import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

# ── Proven YDL Options (battle-tested pattern) ────────────────────────────────
YDL_OPTS = {
    "format":         "bestaudio/best",
    "noplaylist":     True,
    "quiet":          True,
    "no_warnings":    True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extractor_args": {"youtube": {"player_client": ["android", "android_music", "web"]}},
}

YDL_PLAYLIST_OPTS = {
    "format":         "bestaudio/best",
    "noplaylist":     False,
    "quiet":          True,
    "no_warnings":    True,
    "source_address": "0.0.0.0",
    "extract_flat":   "in_playlist",
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
    "executable":     FFMPEG_PATH,
}

# ── Get stream URL (simple, direct) ──────────────────────────────────────────

async def get_stream_url(query: str) -> dict | None:
    """
    Cari lagu dan return dict {title, url, webpage, thumbnail, duration, uploader}.
    URL adalah direct stream URL, langsung bisa dipakai FFmpegPCMAudio.
    """
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(YDL_OPTS).extract_info(query, download=False)
        )
    except Exception as e:
        print(f"[Music] yt-dlp error: {e}")
        return None

    if not data:
        return None

    # Kalau ada entries (playlist atau ytsearch result), ambil yang pertama
    if "entries" in data:
        for entry in data["entries"]:
            if entry:
                data = entry
                break
        else:
            return None

    # Ambil stream URL dari data
    stream_url = data.get("url", "")

    # Kalau url kosong atau masih YouTube halaman, cari di formats[]
    if not stream_url or "youtube.com/watch" in stream_url:
        formats = data.get("formats", [])
        # Prioritas: audio-only (no video)
        audio = [f for f in formats if f.get("url") and f.get("acodec", "none") != "none"
                 and f.get("vcodec", "none") == "none" and "googlevideo" in f.get("url", "")]
        if not audio:
            # Fallback: apapun dengan googlevideo URL
            audio = [f for f in formats if "googlevideo" in f.get("url", "")]
        if audio:
            audio.sort(key=lambda f: f.get("abr") or 0, reverse=True)
            stream_url = audio[0]["url"]

    if not stream_url or "youtube.com" in stream_url:
        print(f"[Music] Tidak dapat stream URL untuk: {data.get('title')}")
        return None

    print(f"[Music] ✓ Got stream: {data.get('title')} | {stream_url[:60]}...")
    return {
        "title":     data.get("title", "Unknown"),
        "url":       stream_url,
        "webpage":   data.get("webpage_url", ""),
        "thumbnail": data.get("thumbnail"),
        "duration":  data.get("duration", 0),
        "uploader":  data.get("uploader", "Unknown"),
    }


async def get_playlist_entries(url: str) -> list[dict]:
    """Ambil daftar entry dari playlist (metadata saja, URL di-resolve saat play)."""
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(YDL_PLAYLIST_OPTS).extract_info(url, download=False)
        )
    except Exception as e:
        print(f"[Music] playlist error: {e}")
        return []
    if not data:
        return []
    entries = data.get("entries", [])
    result = []
    for e in entries:
        if not e:
            continue
        result.append({
            "title":     e.get("title", "Unknown"),
            "url":       None,  # belum di-resolve
            "webpage":   e.get("url") or e.get("webpage_url", ""),
            "thumbnail": e.get("thumbnail"),
            "duration":  e.get("duration", 0),
            "uploader":  e.get("uploader", "Unknown"),
        })
    return result[:100]


# ── Queue Item ────────────────────────────────────────────────────────────────

class QueueItem:
    def __init__(self, info: dict, requester: discord.Member = None):
        self.title     = info["title"]
        self.stream_url = info.get("url")        # None = belum di-resolve (playlist)
        self.webpage   = info.get("webpage", "")
        self.thumbnail = info.get("thumbnail")
        self.duration  = info.get("duration", 0)
        self.uploader  = info.get("uploader", "Unknown")
        self.requester = requester

    async def resolve(self) -> bool:
        """Resolve stream URL jika belum ada (untuk playlist entries)."""
        if self.stream_url:
            return True
        if not self.webpage:
            return False
        result = await get_stream_url(self.webpage)
        if result:
            self.stream_url = result["url"]
            self.title      = result["title"] or self.title
            return True
        return False

    def duration_str(self) -> str:
        if not self.duration:
            return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    def embed(self, title="🎵 Sekarang Diputar") -> discord.Embed:
        desc = f"[{self.title}]({self.webpage})" if self.webpage else self.title
        e = discord.Embed(title=title, description=desc, color=0x9333ea)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱ Durasi",  value=self.duration_str(), inline=True)
        e.add_field(name="🎤 Artis",  value=self.uploader,       inline=True)
        if self.requester:
            e.add_field(name="👤 Request", value=self.requester.mention, inline=True)
        return e


# ── Guild Music State ─────────────────────────────────────────────────────────

class GuildMusicState:
    IDLE_TIMEOUT = 300  # disconnect setelah 5 menit idle

    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot          = bot
        self.guild        = guild
        self.queue:       list[QueueItem]            = []
        self.current:     QueueItem | None           = None
        self.voice:       discord.VoiceClient | None = None
        self.volume       = 0.5
        self.text_channel: discord.TextChannel | None = None
        self._next        = asyncio.Event()
        self._task        = bot.loop.create_task(self._player_loop())

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self._next.clear()
            self.current = None

            if not self.queue:
                # Tunggu lagu baru, max IDLE_TIMEOUT detik
                try:
                    await asyncio.wait_for(self._next.wait(), timeout=self.IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    # Idle terlalu lama → disconnect
                    if self.voice and self.voice.is_connected():
                        await self.voice.disconnect()
                        self.voice = None
                        await self._notify("⏹ Bot keluar dari voice karena idle terlalu lama.")
                    continue
                self._next.clear()

            if not self.queue:
                continue

            item = self.queue.pop(0)
            self.current = item

            # Resolve stream URL jika belum ada
            print(f"[Music] Processing: {item.title}")
            ok = await item.resolve()
            if not ok or not item.stream_url:
                print(f"[Music] ✗ Gagal resolve: {item.title}")
                await self._notify(f"⚠️ Tidak bisa load **{item.title}** — di-skip.")
                self._next.set()
                continue

            # Pastikan voice terkoneksi
            if not (self.voice and self.voice.is_connected()):
                print(f"[Music] ✗ Voice tidak terkoneksi.")
                self._next.set()
                continue

            # Play
            try:
                print(f"[Music] ▶ Playing: {item.title}")
                src = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(item.stream_url, **FFMPEG_OPTS),
                    volume=self.volume
                )
                self.voice.play(src, after=lambda e: self._after(e))
                await self._notify(embed=item.embed())
                await self._next.wait()
            except Exception as e:
                print(f"[Music] ✗ Play error: {e}")
                await self._notify(f"⚠️ Error play **{item.title}**: `{e}`")
                self._next.set()

    def _after(self, error):
        if error:
            print(f"[Music] FFmpeg after error: {error}")
        self.bot.loop.call_soon_threadsafe(self._next.set)

    async def _notify(self, content: str = None, embed: discord.Embed = None):
        if not self.text_channel:
            return
        try:
            if embed:
                await self.text_channel.send(embed=embed)
            elif content:
                await self.text_channel.send(content)
        except Exception:
            pass

    def skip(self):
        if self.voice and self.voice.is_playing():
            self.voice.stop()

    def stop(self):
        self.queue.clear()
        self.current = None
        if self.voice and self.voice.is_playing():
            self.voice.stop()

    def cleanup(self):
        if self._task:
            self._task.cancel()


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.states: dict[int, GuildMusicState] = {}

    def get_state(self, guild: discord.Guild) -> GuildMusicState:
        if guild.id not in self.states:
            self.states[guild.id] = GuildMusicState(self.bot, guild)
        return self.states[guild.id]

    def cog_unload(self):
        for s in self.states.values():
            s.cleanup()

    async def _join_voice(self, interaction: discord.Interaction) -> GuildMusicState | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Masuk voice channel dulu!", ephemeral=True)
            return None
        state = self.get_state(interaction.guild)
        vc = interaction.user.voice.channel
        if state.voice and state.voice.is_connected():
            if state.voice.channel.id != vc.id:
                await state.voice.move_to(vc)
        else:
            state.voice = await vc.connect()
        state.text_channel = interaction.channel
        return state

    @app_commands.command(name="play", description="Putar lagu dari YouTube (URL atau kata kunci)")
    @app_commands.describe(query="URL YouTube atau kata kunci")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await interaction.followup.send(f"🔍 Mencari: **{query}**...")

        is_playlist = "playlist?list=" in query or ("list=" in query and "watch" not in query and "youtube.com" in query)

        if is_playlist:
            entries = await get_playlist_entries(query)
            if not entries:
                await interaction.followup.send("❌ Playlist tidak ditemukan!", ephemeral=True)
                return
            state = await self._join_voice(interaction)
            if not state:
                return
            for e in entries:
                state.queue.append(QueueItem(e, interaction.user))
            state._next.set()
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Playlist Ditambahkan",
                    description=f"{len(entries)} lagu ditambahkan ke queue",
                    color=0x9333ea
                )
            )
        else:
            # Single video / search — resolve stream URL dulu
            info = await get_stream_url(query)
            if not info:
                await interaction.followup.send("❌ Lagu tidak ditemukan atau tidak bisa di-stream!", ephemeral=True)
                return
            state = await self._join_voice(interaction)
            if not state:
                return
            item = QueueItem(info, interaction.user)
            state.queue.append(item)
            state._next.set()
            await interaction.followup.send(embed=item.embed("✅ Ditambahkan ke Queue"))

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if not state.voice or not state.voice.is_playing():
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)
            return
        state.skip()
        await interaction.response.send_message("⏭ Di-skip!")

    @app_commands.command(name="stop", description="Hentikan musik & keluar voice")
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        state.stop()
        if state.voice:
            await state.voice.disconnect()
            state.voice = None
        await interaction.response.send_message("⏹ Musik dihentikan.")

    @app_commands.command(name="pause", description="Pause musik")
    async def pause(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if state.voice and state.voice.is_playing():
            state.voice.pause()
            await interaction.response.send_message("⏸ Di-pause.")
        else:
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)

    @app_commands.command(name="resume", description="Lanjutkan musik")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if state.voice and state.voice.is_paused():
            state.voice.resume()
            await interaction.response.send_message("▶ Dilanjutkan.")
        else:
            await interaction.response.send_message("❌ Tidak dalam keadaan pause.", ephemeral=True)

    @app_commands.command(name="volume", description="Atur volume (0-100)")
    @app_commands.describe(level="Volume 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Volume 0-100.", ephemeral=True)
            return
        state = self.get_state(interaction.guild)
        state.volume = level / 100
        if state.voice and state.voice.source:
            state.voice.source.volume = state.volume
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="queue", description="Lihat antrian lagu")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        embed = discord.Embed(title="🎵 Music Queue", color=0x9333ea)
        if state.current:
            embed.add_field(
                name="▶ Sekarang",
                value=f"[{state.current.title}]({state.current.webpage}) `{state.current.duration_str()}`",
                inline=False
            )
        if state.queue:
            lines = [f"`{i}.` [{s.title}]({s.webpage}) `{s.duration_str()}`"
                     for i, s in enumerate(state.queue[:10], 1)]
            embed.add_field(name=f"📋 Antrian ({len(state.queue)} lagu)", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📋 Antrian", value="Kosong", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Lagu yang sedang diputar")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if not state.current:
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        await interaction.response.send_message(embed=state.current.embed())

    @app_commands.command(name="deleteallqueue", description="Hapus semua antrian")
    async def deleteallqueue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        n = len(state.queue)
        if not n:
            await interaction.response.send_message("📋 Antrian kosong.", ephemeral=True)
            return
        state.queue.clear()
        embed = discord.Embed(
            title="🗑️ Antrian Dihapus",
            description=f"**{n} lagu** dihapus." + (f"\n▶ `{state.current.title}` tetap diputar." if state.current else ""),
            color=0xef4444
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="musictest", description="Test apakah bot bisa extract YouTube URL")
    @app_commands.describe(url="URL YouTube untuk ditest")
    async def musictest(self, interaction: discord.Interaction, url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
        await interaction.response.defer()
        info = await get_stream_url(url)
        if info:
            embed = discord.Embed(title="✅ Berhasil!", color=0x22c55e)
            embed.add_field(name="Judul", value=info["title"], inline=False)
            embed.add_field(name="Stream URL", value=f"`{info['url'][:80]}...`", inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Gagal extract URL. Cek log VPS untuk detail.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
