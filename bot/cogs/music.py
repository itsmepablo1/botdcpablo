import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

# ─── yt-dlp options ──────────────────────────────────────────────────────────

# Untuk from_query: HANYA ambil metadata (title, webpage_url, thumbnail, duration)
# TIDAK ada format selector → tidak pernah gagal karena "format not available"
# Paksa android player client agar tidak butuh JavaScript runtime
YTDL_META = {
    "noplaylist":         True,
    "nocheckcertificate": True,
    "ignoreerrors":       True,
    "quiet":              True,
    "no_warnings":        True,
    "default_search":     "ytsearch",
    "source_address":     "0.0.0.0",
    "extractor_args":     {"youtube": {"player_client": ["android", "web"]}},
}

# Untuk playlist: flat metadata saja (cepat)
YTDL_PLAYLIST = {
    "noplaylist":         False,
    "nocheckcertificate": True,
    "ignoreerrors":       True,
    "quiet":              True,
    "no_warnings":        True,
    "source_address":     "0.0.0.0",
    "extract_flat":       "in_playlist",
    "extractor_args":     {"youtube": {"player_client": ["android", "web"]}},
}

# Format chains untuk dicoba saat resolve stream (urutan dari paling preferred)
STREAM_FORMAT_CHAIN = [
    "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "bestaudio/best",
    "ba/b",
    "best",
]

# Base opts untuk resolve stream URL
YTDL_STREAM_BASE = {
    "noplaylist":         True,
    "nocheckcertificate": True,
    "ignoreerrors":       False,  # raise jika benar-benar gagal
    "quiet":              True,
    "no_warnings":        True,
    "source_address":     "0.0.0.0",
    # Paksa Android player client → tidak butuh JS runtime
    "extractor_args":     {"youtube": {"player_client": ["android", "android_music", "web"]}},
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
    "executable":     FFMPEG_PATH,
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_stream_url(url: str) -> bool:
    if not url:
        return False
    NOT_STREAM = ("youtube.com/watch", "youtu.be/", "youtube.com/shorts", "youtube.com/playlist")
    return url.startswith("http") and not any(s in url for s in NOT_STREAM)

def _best_stream_from_data(data: dict) -> str | None:
    """Ambil stream URL terbaik dari hasil extract_info."""
    url = data.get("url", "")
    if _is_stream_url(url):
        return url
    formats = data.get("formats", [])
    # Audio-only dulu
    audio = [f for f in formats if f.get("url") and _is_stream_url(f["url"])
             and f.get("acodec", "none") != "none" and f.get("vcodec", "none") == "none"]
    if audio:
        audio.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
        return audio[0]["url"]
    # Apapun yang punya URL valid
    any_fmt = [f for f in formats if f.get("url") and _is_stream_url(f["url"])]
    if any_fmt:
        any_fmt.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
        return any_fmt[0]["url"]
    return None


# ─── Song ─────────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, data: dict):
        self.webpage   = data.get("webpage_url") or ""
        # Untuk playlist entry, url = watch URL; untuk resolved, url = stream URL
        raw_url        = data.get("url", "")
        if not self.webpage and not _is_stream_url(raw_url):
            self.webpage = raw_url  # simpan watch URL sebagai webpage
        self.title     = data.get("title", "Unknown")
        self.thumbnail = data.get("thumbnail")
        self.duration  = data.get("duration", 0)
        self.uploader  = data.get("uploader", "Unknown")
        self.requester = None
        # Jika data sudah punya stream URL (dari resolve sebelumnya), simpan
        self._stream_url = _best_stream_from_data(data)

    @staticmethod
    def _is_playlist_url(query: str) -> bool:
        return (
            "playlist?list=" in query
            or ("youtube.com" in query and "list=" in query and "watch" not in query)
        )

    @staticmethod
    async def from_query(query: str) -> list["Song"]:
        loop = asyncio.get_event_loop()

        if Song._is_playlist_url(query):
            # ── Playlist: metadata flat ───────────────────────────────────────
            print(f"[Music] from_query: PLAYLIST | {query[:80]}")
            data = await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(YTDL_PLAYLIST).extract_info(query, download=False)
            )
            if not data:
                return []
            entries = data.get("entries", [])
            songs = [Song(e) for e in entries if e]
            print(f"[Music] Playlist: {len(songs)} lagu")
            return songs[:100]

        else:
            # ── Single / search: metadata dulu, stream URL lazy ───────────────
            print(f"[Music] from_query: SINGLE/SEARCH | {query[:80]}")
            data = await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(YTDL_META).extract_info(query, download=False)
            )
            if not data:
                print("[Music] from_query: data None")
                return []

            if "entries" in data:
                # ytsearch → ambil entry pertama yang valid
                for entry in data["entries"]:
                    if entry and (entry.get("webpage_url") or entry.get("url")):
                        s = Song(entry)
                        print(f"[Music] Found: {s.title}")
                        return [s]
                return []

            s = Song(data)
            print(f"[Music] Found: {s.title}")
            return [s]

    # ── Stream resolve ────────────────────────────────────────────────────────

    async def get_stream_url(self) -> str:
        # Jika sudah ada stream URL valid, gunakan langsung
        if self._stream_url and _is_stream_url(self._stream_url):
            print(f"[Music] ✓ Cached stream: {self.title}")
            return self._stream_url

        resolve_target = self.webpage
        if not resolve_target:
            raise Exception(f"Tidak ada URL untuk resolve: {self.title}")

        print(f"[Music] Resolving: {resolve_target[:80]}")
        loop = asyncio.get_event_loop()

        last_error = None
        for fmt in STREAM_FORMAT_CHAIN:
            try:
                opts = {**YTDL_STREAM_BASE, "format": fmt}
                data = await loop.run_in_executor(
                    None, lambda o=opts: yt_dlp.YoutubeDL(o).extract_info(resolve_target, download=False)
                )
                if data:
                    url = _best_stream_from_data(data)
                    if url:
                        # Update metadata
                        self.title     = data.get("title")     or self.title
                        self.thumbnail = data.get("thumbnail") or self.thumbnail
                        self.duration  = data.get("duration")  or self.duration
                        self.uploader  = data.get("uploader")  or self.uploader
                        self._stream_url = url
                        print(f"[Music] ✓ Resolved [{fmt}]: {self.title}")
                        return url
            except Exception as e:
                last_error = e
                print(f"[Music] Format '{fmt}' gagal: {e}")
                continue

        raise Exception(f"Semua format gagal untuk '{self.title}'. Error terakhir: {last_error}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def duration_str(self) -> str:
        if not self.duration:
            return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    def embed(self, title="🎵 Sekarang Diputar") -> discord.Embed:
        link = f"[{self.title}]({self.webpage})" if self.webpage else self.title
        e = discord.Embed(title=title, description=link, color=0x9333ea)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱ Durasi",  value=self.duration_str(), inline=True)
        e.add_field(name="🎤 Artis",  value=self.uploader,       inline=True)
        if self.requester:
            e.add_field(name="👤 Request", value=self.requester.mention, inline=True)
        return e


# ─── GuildMusicState ──────────────────────────────────────────────────────────

class GuildMusicState:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot          = bot
        self.guild        = guild
        self.queue:       list[Song]                  = []
        self.current:     Song | None                 = None
        self.voice:       discord.VoiceClient | None  = None
        self.volume       = 0.5
        self.text_channel: discord.TextChannel | None = None
        self._next        = asyncio.Event()
        self._task        = bot.loop.create_task(self._player_loop())

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self._next.clear()

            if not self.queue:
                await self._next.wait()
                continue

            self.current = self.queue.pop(0)
            print(f"[Music] Proses: {self.current.title}")

            # ── Resolve stream URL ────────────────────────────────────────────
            try:
                stream_url = await self.current.get_stream_url()
            except Exception as e:
                print(f"[Music] ✗ Resolve gagal: {e}")
                await self._notify(f"⚠️ Gagal load `{self.current.title}`\n```{e}```")
                self._next.set()
                continue

            # ── Tunggu voice siap ─────────────────────────────────────────────
            for _ in range(20):
                if self.voice and self.voice.is_connected():
                    break
                await asyncio.sleep(0.5)

            if not (self.voice and self.voice.is_connected()):
                print("[Music] ✗ Voice tidak terkoneksi.")
                self._next.set()
                continue

            # ── Play ──────────────────────────────────────────────────────────
            try:
                print(f"[Music] ▶ Playing: {self.current.title}")
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
                    volume=self.volume
                )
                self.voice.play(source, after=lambda e: self._on_end(e))
                await self._notify(embed=self.current.embed())
                await self._next.wait()
            except Exception as e:
                print(f"[Music] ✗ Error play: {e}")
                await self._notify(f"⚠️ Error saat play `{self.current.title}`: {e}")
                self._next.set()

    def _on_end(self, error):
        if error:
            print(f"[Music] FFmpeg error: {error}")
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


# ─── Music Cog ───────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.states: dict[int, GuildMusicState] = {}

    def get_state(self, guild: discord.Guild) -> GuildMusicState:
        if guild.id not in self.states:
            self.states[guild.id] = GuildMusicState(self.bot, guild)
        return self.states[guild.id]

    def cog_unload(self):
        for state in self.states.values():
            state.cleanup()

    async def _ensure_voice(self, interaction: discord.Interaction) -> GuildMusicState | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Kamu harus masuk voice channel dulu!", ephemeral=True)
            return None
        state = self.get_state(interaction.guild)
        vc    = interaction.user.voice.channel
        if state.voice and state.voice.is_connected():
            if state.voice.channel.id != vc.id:
                await state.voice.move_to(vc)
        else:
            state.voice = await vc.connect()
        state.text_channel = interaction.channel
        return state

    # ── Slash Commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube (URL atau kata kunci)")
    @app_commands.describe(query="URL YouTube atau kata kunci pencarian")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        # Cari lagu DULU sebelum join voice
        await interaction.followup.send(f"🔍 Mencari: **{query}** ...")
        songs = await Song.from_query(query)
        if not songs:
            await interaction.followup.send("❌ Lagu tidak ditemukan!", ephemeral=True)
            return

        # Baru join voice setelah lagu ditemukan
        state = await self._ensure_voice(interaction)
        if not state:
            return

        for s in songs:
            s.requester = interaction.user
        state.queue.extend(songs)
        state._next.set()

        if len(songs) == 1:
            await interaction.followup.send(embed=songs[0].embed("✅ Ditambahkan ke Queue"))
        else:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Playlist Ditambahkan",
                    description=f"{len(songs)} lagu ditambahkan ke queue",
                    color=0x9333ea
                )
            )

    @app_commands.command(name="skip", description="Skip lagu yang sedang diputar")
    async def skip(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if not state.voice or not state.voice.is_playing():
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)
            return
        state.skip()
        await interaction.response.send_message("⏭ Lagu di-skip!")

    @app_commands.command(name="stop", description="Hentikan musik dan kosongkan queue")
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
            await interaction.response.send_message("⏸ Musik di-pause.")
        else:
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)

    @app_commands.command(name="resume", description="Lanjutkan musik yang di-pause")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if state.voice and state.voice.is_paused():
            state.voice.resume()
            await interaction.response.send_message("▶ Musik dilanjutkan.")
        else:
            await interaction.response.send_message("❌ Musik tidak dalam keadaan pause.", ephemeral=True)

    @app_commands.command(name="volume", description="Atur volume musik (0–100)")
    @app_commands.describe(level="Level volume 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Volume harus antara 0-100.", ephemeral=True)
            return
        state = self.get_state(interaction.guild)
        state.volume = level / 100
        if state.voice and state.voice.source:
            state.voice.source.volume = state.volume
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="queue", description="Lihat daftar lagu dalam queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        embed = discord.Embed(title="🎵 Music Queue", color=0x9333ea)
        if state.current:
            embed.add_field(
                name="▶ Sekarang Diputar",
                value=f"[{state.current.title}]({state.current.webpage}) `{state.current.duration_str()}`",
                inline=False
            )
        if state.queue:
            items = [
                f"`{i}.` [{s.title}]({s.webpage}) `{s.duration_str()}`"
                for i, s in enumerate(state.queue[:10], 1)
            ]
            embed.add_field(
                name=f"📋 Antrian ({len(state.queue)} lagu)",
                value="\n".join(items),
                inline=False
            )
        else:
            embed.add_field(name="📋 Antrian", value="Kosong", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Lihat lagu yang sedang diputar")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if not state.current:
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)
            return
        await interaction.response.send_message(embed=state.current.embed())

    @app_commands.command(name="deleteallqueue", description="Hapus semua lagu dari antrian")
    async def deleteallqueue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if not state.queue:
            await interaction.response.send_message("📋 Antrian sudah kosong.", ephemeral=True)
            return
        jumlah = len(state.queue)
        state.queue.clear()
        embed = discord.Embed(
            title="🗑️ Antrian Dihapus",
            description=(
                f"**{jumlah} lagu** berhasil dihapus.\n"
                + (f"▶ `{state.current.title}` tetap diputar." if state.current else "")
            ),
            color=0xef4444,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
