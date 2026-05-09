import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

YTDL_OPTIONS = {
    "format":               "bestaudio/best",
    "noplaylist":           False,
    "nocheckcertificate":   True,
    "ignoreerrors":         True,
    "quiet":                True,
    "no_warnings":          True,
    "default_search":       "ytsearch",
    "source_address":       "0.0.0.0",
    # JANGAN pakai extract_flat agar URL audio stream langsung tersedia
}

# Options khusus untuk playlist (hanya ambil metadata, cepat)
YTDL_FLAT_OPTIONS = {
    "format":               "bestaudio/best",
    "noplaylist":           False,
    "nocheckcertificate":   True,
    "ignoreerrors":         True,
    "quiet":                True,
    "no_warnings":          True,
    "default_search":       "ytsearch",
    "source_address":       "0.0.0.0",
    "extract_flat":         "in_playlist",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn -filter:a 'volume=0.5'",
    "executable":     FFMPEG_PATH,
}

class Song:
    def __init__(self, data: dict):
        # stream URL bisa None untuk entry playlist (akan di-resolve saat play)
        self.url        = data.get("url")
        self.title      = data.get("title", "Unknown")
        self.webpage    = data.get("webpage_url") or data.get("url", "")
        self.thumbnail  = data.get("thumbnail")
        self.duration   = data.get("duration", 0)
        self.uploader   = data.get("uploader", "Unknown")
        self.requester  = None  # set by caller
        self._is_flat   = not data.get("url") or "youtube.com/watch" in (data.get("url") or "")

    @staticmethod
    async def from_query(query: str) -> list["Song"]:
        loop = asyncio.get_event_loop()

        # Deteksi playlist: gunakan flat options agar cepat, lagu di-resolve saat play
        is_playlist_url = "playlist?list=" in query or ("list=" in query and "watch" not in query)

        if is_playlist_url:
            ydl_flat = yt_dlp.YoutubeDL(YTDL_FLAT_OPTIONS)
            data = await loop.run_in_executor(None, lambda: ydl_flat.extract_info(query, download=False))
        else:
            ydl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))

        if not data:
            return []

        if "entries" in data:
            songs = []
            for entry in data["entries"]:
                if not entry:
                    continue
                # Untuk playlist flat, webpage_url digunakan; url-nya belum ada stream
                # Tandai sebagai flat agar di-resolve saat giliran play
                songs.append(Song(entry))
            return songs
        return [Song(data)]

    async def resolve_stream(self):
        """Resolve URL audio stream jika belum tersedia (untuk entry playlist flat)."""
        # Cek apakah url sudah berupa stream audio atau masih URL halaman
        if self.url and not ("youtube.com/watch" in self.url or "youtu.be/" in self.url):
            return  # sudah berupa stream URL
        webpage = self.webpage or self.url
        if not webpage:
            return
        loop = asyncio.get_event_loop()
        ydl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        data = await loop.run_in_executor(None, lambda: ydl.extract_info(webpage, download=False))
        if data:
            self.url       = data.get("url", self.url)
            self.title     = data.get("title", self.title)
            self.thumbnail = data.get("thumbnail") or self.thumbnail
            self.duration  = data.get("duration") or self.duration
            self.uploader  = data.get("uploader") or self.uploader
            self.webpage   = data.get("webpage_url") or self.webpage

    def make_source(self) -> discord.FFmpegPCMAudio:
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.url, **FFMPEG_OPTIONS),
            volume=0.5
        )

    def duration_str(self) -> str:
        if not self.duration:
            return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02}:{s:02}"
        return f"{m}:{s:02}"

    def embed(self, title="🎵 Sekarang Diputar") -> discord.Embed:
        e = discord.Embed(title=title, description=f"[{self.title}]({self.webpage})", color=0x9333ea)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱ Durasi",    value=self.duration_str(), inline=True)
        e.add_field(name="🎤 Artis",    value=self.uploader,       inline=True)
        if self.requester:
            e.add_field(name="👤 Request oleh", value=self.requester.mention, inline=True)
        return e

class GuildMusicState:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot   = bot
        self.guild = guild
        self.queue: list[Song] = []
        self.current: Song | None = None
        self.voice: discord.VoiceClient | None = None
        self.volume = 0.5
        self._next  = asyncio.Event()
        self._task  = bot.loop.create_task(self._player_loop())

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self._next.clear()
            if not self.queue:
                await self._next.wait()
                continue
            self.current = self.queue.pop(0)
            # Resolve stream URL terlebih dahulu (penting untuk playlist)
            try:
                await self.current.resolve_stream()
            except Exception as e:
                print(f"[Music] Gagal resolve stream: {e}")
                self._next.set()
                continue

            if not self.current.url:
                print(f"[Music] Lagu '{self.current.title}' tidak punya stream URL, dilewati.")
                self._next.set()
                continue

            # Tunggu voice client benar-benar terkoneksi
            for _ in range(10):
                if self.voice and self.voice.is_connected():
                    break
                await asyncio.sleep(0.5)

            if self.voice and self.voice.is_connected():
                try:
                    source = self.current.make_source()
                    source.volume = self.volume
                    self.voice.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self._next.set))
                    await self._next.wait()
                except Exception as e:
                    print(f"[Music] Error saat play: {e}")
                    self._next.set()
            else:
                print("[Music] Voice tidak terkoneksi, melewati lagu.")
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _ensure_voice(self, interaction: discord.Interaction) -> GuildMusicState | None:
        """Join user's voice channel if needed. Returns state or None on fail."""
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
        return state

    # ── Slash Commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube (URL atau kata kunci)")
    @app_commands.describe(query="URL YouTube atau kata kunci pencarian")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        state = await self._ensure_voice(interaction)
        if not state:
            return
        await interaction.followup.send(f"🔍 Mencari: **{query}** ...", ephemeral=False)
        songs = await Song.from_query(query)
        if not songs:
            await interaction.followup.send("❌ Lagu tidak ditemukan!", ephemeral=True)
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
        await interaction.response.send_message("⏭ Lagu di-skip!", ephemeral=False)

    @app_commands.command(name="stop", description="Hentikan musik dan kosongkan queue")
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        state.stop()
        if state.voice:
            await state.voice.disconnect()
            state.voice = None
        await interaction.response.send_message("⏹ Musik dihentikan dan bot keluar dari voice.", ephemeral=False)

    @app_commands.command(name="pause", description="Pause musik")
    async def pause(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if state.voice and state.voice.is_playing():
            state.voice.pause()
            await interaction.response.send_message("⏸ Musik di-pause.", ephemeral=False)
        else:
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)

    @app_commands.command(name="resume", description="Lanjutkan musik yang di-pause")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        if state.voice and state.voice.is_paused():
            state.voice.resume()
            await interaction.response.send_message("▶ Musik dilanjutkan.", ephemeral=False)
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
        await interaction.response.send_message(f"🔊 Volume diset ke **{level}%**", ephemeral=False)

    @app_commands.command(name="queue", description="Lihat daftar lagu dalam queue")
    async def queue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        embed = discord.Embed(title="🎵 Music Queue", color=0x9333ea)
        if state.current:
            embed.add_field(name="▶ Sekarang Diputar", value=f"[{state.current.title}]({state.current.webpage}) `{state.current.duration_str()}`", inline=False)
        if state.queue:
            items = []
            for i, s in enumerate(state.queue[:10], 1):
                items.append(f"`{i}.` [{s.title}]({s.webpage}) `{s.duration_str()}`")
            embed.add_field(name=f"📋 Antrian ({len(state.queue)} lagu)", value="\n".join(items), inline=False)
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
