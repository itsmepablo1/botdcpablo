import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

# ─── yt-dlp options ──────────────────────────────────────────────────────────

# Untuk resolve stream URL satu lagu (fresh setiap kali play)
YTDL_STREAM_OPTIONS = {
    "format":             "bestaudio/best",
    "noplaylist":         True,
    "nocheckcertificate": True,
    "ignoreerrors":       False,
    "quiet":              True,
    "no_warnings":        True,
    "source_address":     "0.0.0.0",
}

# Untuk pencarian / single video URL — TANPA extract_flat agar tidak return None
YTDL_SINGLE_OPTIONS = {
    "format":             "bestaudio/best",
    "noplaylist":         True,   # jangan proses playlist jika URL video punya list=
    "nocheckcertificate": True,
    "ignoreerrors":       True,
    "quiet":              True,
    "no_warnings":        True,
    "default_search":     "ytsearch",
    "source_address":     "0.0.0.0",
    # TIDAK pakai extract_flat agar single video selalu berhasil di-extract
}

# Untuk playlist URL — cepat, hanya ambil metadata
YTDL_PLAYLIST_OPTIONS = {
    "format":             "bestaudio/best",
    "noplaylist":         False,
    "nocheckcertificate": True,
    "ignoreerrors":       True,
    "quiet":              True,
    "no_warnings":        True,
    "source_address":     "0.0.0.0",
    "extract_flat":       "in_playlist",  # cepat untuk playlist panjang
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
    "executable":     FFMPEG_PATH,
}

# ─── Song ─────────────────────────────────────────────────────────────────────

class Song:
    """Menyimpan metadata lagu. URL stream di-resolve fresh saat giliran play."""

    def __init__(self, data: dict):
        # webpage_url = URL halaman YouTube (https://www.youtube.com/watch?v=...)
        # ini yang akan kita berikan ke yt-dlp untuk resolve stream
        self.webpage   = data.get("webpage_url") or data.get("url", "")
        self.title     = data.get("title", "Unknown")
        self.thumbnail = data.get("thumbnail")
        self.duration  = data.get("duration", 0)
        self.uploader  = data.get("uploader", "Unknown")
        self.requester = None  # diisi oleh caller

    # ── Factory ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_playlist_url(query: str) -> bool:
        """Deteksi apakah query adalah URL playlist YouTube."""
        return (
            "playlist?list=" in query
            or ("youtube.com" in query and "list=" in query and "watch" not in query)
        )

    @staticmethod
    async def from_query(query: str) -> list["Song"]:
        """
        Cari lagu/playlist dan kembalikan list Song.
        - Playlist URL  → extract_flat (cepat, stream di-resolve saat play)
        - Single / search → extract penuh (tidak pakai extract_flat)
        """
        loop = asyncio.get_event_loop()

        if Song._is_playlist_url(query):
            # Playlist: ambil metadata saja dulu
            ydl  = yt_dlp.YoutubeDL(YTDL_PLAYLIST_OPTIONS)
            data = await loop.run_in_executor(
                None, lambda: ydl.extract_info(query, download=False)
            )
        else:
            # Single video URL atau kata kunci pencarian
            ydl  = yt_dlp.YoutubeDL(YTDL_SINGLE_OPTIONS)
            data = await loop.run_in_executor(
                None, lambda: ydl.extract_info(query, download=False)
            )

        if not data:
            print(f"[Music] from_query: yt-dlp return None untuk query: {query}")
            return []

        if "entries" in data:
            songs = []
            for entry in data["entries"]:
                if not entry:
                    continue
                songs.append(Song(entry))
            return songs[:100]  # maksimal 100 lagu

        return [Song(data)]

    # ── Stream resolve ────────────────────────────────────────────────────────

    async def get_stream_url(self) -> str:
        """
        Minta yt-dlp untuk resolve URL stream audio yang benar.
        Selalu fresh → tidak pernah expired.
        Raise Exception jika gagal.
        """
        if not self.webpage:
            raise Exception(f"Song '{self.title}' tidak punya webpage URL")

        loop = asyncio.get_event_loop()
        ydl  = yt_dlp.YoutubeDL(YTDL_STREAM_OPTIONS)

        print(f"[Music] Resolving stream: {self.webpage}")
        data = await loop.run_in_executor(
            None, lambda: ydl.extract_info(self.webpage, download=False)
        )

        if not data:
            raise Exception(f"yt-dlp gagal extract: {self.webpage}")

        # Ambil URL langsung
        stream_url = data.get("url")

        # Fallback: cari di formats[]
        if not stream_url:
            formats = data.get("formats", [])
            # Pilih audio-only format dengan bitrate tertinggi
            audio_fmts = [
                f for f in formats
                if f.get("url") and f.get("acodec", "none") != "none"
                and f.get("vcodec", "none") == "none"
            ]
            if not audio_fmts:
                # Fallback ke format apapun yang ada URL
                audio_fmts = [f for f in formats if f.get("url")]
            if audio_fmts:
                audio_fmts.sort(key=lambda f: f.get("abr") or 0, reverse=True)
                stream_url = audio_fmts[0]["url"]

        if not stream_url:
            raise Exception(f"Tidak dapat menemukan stream URL untuk: {self.title}")

        # Update metadata dari hasil resolve
        self.title     = data.get("title")     or self.title
        self.thumbnail = data.get("thumbnail") or self.thumbnail
        self.duration  = data.get("duration")  or self.duration
        self.uploader  = data.get("uploader")  or self.uploader
        self.webpage   = data.get("webpage_url") or self.webpage

        print(f"[Music] ✓ Stream OK: {self.title} | {stream_url[:60]}...")
        return stream_url

    # ── Helpers ───────────────────────────────────────────────────────────────

    def duration_str(self) -> str:
        if not self.duration:
            return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02}:{s:02}"
        return f"{m}:{s:02}"

    def embed(self, title="🎵 Sekarang Diputar") -> discord.Embed:
        e = discord.Embed(
            title=title,
            description=f"[{self.title}]({self.webpage})",
            color=0x9333ea
        )
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱ Durasi",    value=self.duration_str(), inline=True)
        e.add_field(name="🎤 Artis",    value=self.uploader,       inline=True)
        if self.requester:
            e.add_field(name="👤 Request oleh", value=self.requester.mention, inline=True)
        return e


# ─── GuildMusicState ──────────────────────────────────────────────────────────

class GuildMusicState:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot     = bot
        self.guild   = guild
        self.queue:  list[Song]             = []
        self.current: Song | None           = None
        self.voice:  discord.VoiceClient | None = None
        self.volume  = 0.5
        self._next   = asyncio.Event()
        self._task   = bot.loop.create_task(self._player_loop())

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self._next.clear()

            if not self.queue:
                await self._next.wait()
                continue

            self.current = self.queue.pop(0)

            # ── 1. Resolve stream URL (fresh dari yt-dlp) ──────────────────
            try:
                stream_url = await self.current.get_stream_url()
            except Exception as e:
                print(f"[Music] ✗ Gagal resolve stream: {e}")
                self._next.set()
                continue

            # ── 2. Tunggu voice terkoneksi ──────────────────────────────────
            for _ in range(20):  # tunggu maksimal 10 detik
                if self.voice and self.voice.is_connected():
                    break
                await asyncio.sleep(0.5)

            if not (self.voice and self.voice.is_connected()):
                print("[Music] ✗ Voice tidak terkoneksi, lagu dilewati.")
                self._next.set()
                continue

            # ── 3. Buat source dan play ─────────────────────────────────────
            try:
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
                    volume=self.volume
                )
                self.voice.play(
                    source,
                    after=lambda _: self.bot.loop.call_soon_threadsafe(self._next.set)
                )
                await self._next.wait()
            except Exception as e:
                print(f"[Music] ✗ Error saat play: {e}")
                self._next.set()

    def skip(self):
        if self.voice and self.voice.is_playing():
            self.voice.stop()

    def stop(self):
        self.queue.clear()
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

    # ── Helper ────────────────────────────────────────────────────────────────

    async def _ensure_voice(self, interaction: discord.Interaction) -> GuildMusicState | None:
        """Join voice channel user. Return state atau None jika gagal."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(
                "❌ Kamu harus masuk voice channel dulu!", ephemeral=True
            )
            return None
        state = self.get_state(interaction.guild)
        vc    = interaction.user.voice.channel
        if state.voice and state.voice.is_connected():
            if state.voice.channel.id != vc.id:
                await state.voice.move_to(vc)
        else:
            state.voice = await vc.connect()
        return state

    # ── Slash Commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube (URL atau kata kunci)")
    @app_commands.describe(query="URL YouTube atau kata kunci pencarian")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        state = await self._ensure_voice(interaction)
        if not state:
            return

        await interaction.followup.send(f"🔍 Mencari: **{query}** ...")
        songs = await Song.from_query(query)
        if not songs:
            await interaction.followup.send("❌ Lagu tidak ditemukan!", ephemeral=True)
            return

        for s in songs:
            s.requester = interaction.user
        state.queue.extend(songs)
        state._next.set()  # trigger player loop

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
        await interaction.response.send_message("⏹ Musik dihentikan dan bot keluar dari voice.")

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
        await interaction.response.send_message(f"🔊 Volume diset ke **{level}%**")

    @app_commands.command(name="queue", description="Lihat daftar lagu dalam queue")
    async def queue(self, interaction: discord.Interaction):
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

    @app_commands.command(name="deleteallqueue", description="Hapus semua lagu dari antrian (lagu sekarang tetap diputar)")
    async def deleteallqueue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if not state.queue:
            await interaction.response.send_message(
                "📋 Antrian sudah kosong.", ephemeral=True
            )
            return
        jumlah = len(state.queue)
        state.queue.clear()
        embed = discord.Embed(
            title="🗑️ Antrian Dihapus",
            description=(
                f"**{jumlah} lagu** berhasil dihapus dari antrian.\n"
                + (f"▶ Lagu **{state.current.title}** tetap diputar."
                   if state.current else "")
            ),
            color=0xef4444,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
