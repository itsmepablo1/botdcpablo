"""
Music cog — yt-dlp + FFmpeg + discord.py native voice
Tidak memerlukan Lavalink/Java. Lebih stabil dan langsung.
"""
import asyncio
import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands
from collections import deque
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── yt-dlp config ─────────────────────────────────────────────────────────────

YTDL_OPTIONS = {
    "format":           "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist":       True,
    "quiet":            True,
    "no_warnings":      True,
    "default_search":   "ytsearch",
    "source_address":   "0.0.0.0",
    "cookiefile":       None,
    "age_limit":        99,
    "geo_bypass":       True,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn -b:a 128k",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


# ── Song ──────────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, data: dict, requester=None):
        self.title     = data.get("title", "Unknown")
        self.url       = data.get("url", "")          # direct audio stream URL
        self.webpage   = data.get("webpage_url", "")
        self.thumbnail = data.get("thumbnail")
        self.duration  = data.get("duration", 0)
        self.uploader  = data.get("uploader", "Unknown")
        self.requester = requester

    def fmt_dur(self) -> str:
        if not self.duration:
            return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    def embed(self, title: str = "🎵 Sekarang Diputar") -> discord.Embed:
        desc = f"[{self.title}]({self.webpage})" if self.webpage else self.title
        e    = discord.Embed(title=title, description=desc, color=0x9333ea)
        e.add_field(name="⏱ Durasi",   value=self.fmt_dur(),   inline=True)
        e.add_field(name="🎤 Channel",  value=self.uploader,    inline=True)
        if self.requester:
            e.add_field(name="👤 Request", value=self.requester.mention, inline=True)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        return e

    def make_source(self) -> discord.AudioSource:
        return discord.FFmpegOpusAudio(self.url, **FFMPEG_OPTIONS)


# ── GuildMusicState ───────────────────────────────────────────────────────────

class GuildMusicState:
    def __init__(self):
        self.queue:   deque[Song]          = deque()
        self.current: Song | None          = None
        self.channel: discord.TextChannel | None = None
        self.volume:  float                = 1.0
        self._lock:   asyncio.Lock         = asyncio.Lock()

    @property
    def is_playing(self) -> bool:
        return bool(self.current)


# ── fetch helpers ─────────────────────────────────────────────────────────────

async def fetch_song(query: str, requester=None) -> Song | None:
    """Jalankan yt-dlp di thread executor dan kembalikan Song."""
    loop = asyncio.get_event_loop()

    def _extract():
        q = query if query.startswith("http") else f"ytsearch:{query}"
        try:
            data = ytdl.extract_info(q, download=False)
            if not data:
                return None
            # Handle playlist/search result
            if "entries" in data:
                data = data["entries"][0]
            return data
        except Exception as e:
            print(f"[Music] yt-dlp error: {e}", flush=True)
            return None

    data = await loop.run_in_executor(None, _extract)
    if not data:
        return None

    # Pastikan ada stream URL (bukan halaman web)
    url = data.get("url", "")
    if not url:
        print(f"[Music] No stream URL for: {data.get('title')}", flush=True)
        return None

    print(f"[Music] Found: {data.get('title')} | {url[:60]}...", flush=True)
    return Song(data, requester)


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.states: dict[int, GuildMusicState] = {}

    def _state(self, gid: int) -> GuildMusicState:
        if gid not in self.states:
            self.states[gid] = GuildMusicState()
        return self.states[gid]

    # ── internal ──────────────────────────────────────────────────────────────

    async def _join(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Masuk voice channel dulu!", ephemeral=True)
            return None
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if vc and vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)
        elif not vc:
            vc = await interaction.user.voice.channel.connect()
        return vc

    def _play_next(self, vc: discord.VoiceClient, state: GuildMusicState):
        """Callback saat lagu selesai — jalankan lagu berikutnya."""
        if state.queue:
            next_song = state.queue.popleft()
            state.current = next_song
            try:
                source = next_song.make_source()
                vc.play(source, after=lambda e: self._on_finish(e, vc, state))
            except Exception as ex:
                print(f"[Music] play_next error: {ex}", flush=True)
                state.current = None
            # Kirim embed ke channel
            if state.channel:
                asyncio.run_coroutine_threadsafe(
                    state.channel.send(embed=next_song.embed()),
                    self.bot.loop
                )
        else:
            state.current = None

    def _on_finish(self, error, vc: discord.VoiceClient, state: GuildMusicState):
        if error:
            print(f"[Music] Player error: {error}", flush=True)
        self._play_next(vc, state)

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube (URL atau nama lagu)")
    @app_commands.describe(query="URL atau nama lagu yang ingin diputar")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        state = self._state(interaction.guild.id)
        state.channel = interaction.channel

        await interaction.followup.send(f"🔍 Mencari: **{query}**...")

        song = await fetch_song(query, interaction.user)
        if not song:
            await interaction.followup.send("❌ Lagu tidak ditemukan atau terjadi error.", ephemeral=True)
            return

        vc = await self._join(interaction)
        if not vc:
            return

        if vc.is_playing() or vc.is_paused():
            state.queue.append(song)
            await interaction.followup.send(
                embed=song.embed(f"✅ Ditambahkan ke Queue (#{len(state.queue)})")
            )
        else:
            state.current = song
            try:
                source = song.make_source()
                vc.play(source, after=lambda e: self._on_finish(e, vc, state))
                await interaction.followup.send(embed=song.embed("▶ Sekarang Memutar"))
            except Exception as e:
                print(f"[Music] play error: {e}", flush=True)
                await interaction.followup.send(f"❌ Gagal memutar: `{e}`", ephemeral=True)
                state.current = None

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message("⏭ Lagu di-skip!")

    @app_commands.command(name="stop", description="Stop musik dan bot keluar dari voice")
    async def stop(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        state = self._state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹ Musik dihentikan.")

    @app_commands.command(name="pause", description="Pause musik")
    async def pause(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)
            return
        vc.pause()
        await interaction.response.send_message("⏸ Di-pause.")

    @app_commands.command(name="resume", description="Lanjutkan musik")
    async def resume(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.is_paused():
            await interaction.response.send_message("❌ Tidak dalam keadaan pause.", ephemeral=True)
            return
        vc.resume()
        await interaction.response.send_message("▶ Dilanjutkan.")

    @app_commands.command(name="volume", description="Atur volume 0-200")
    @app_commands.describe(level="Volume 0-200 (default: 100)")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 200:
            await interaction.response.send_message("❌ Volume harus 0-200.", ephemeral=True)
            return
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.source:
            await interaction.response.send_message("❌ Bot tidak di voice.", ephemeral=True)
            return
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = level / 100
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="queue", description="Lihat antrian lagu")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        e     = discord.Embed(title="🎵 Queue", color=0x9333ea)
        if state.current:
            e.add_field(
                name="▶ Sekarang",
                value=f"[{state.current.title}]({state.current.webpage}) `{state.current.fmt_dur()}`",
                inline=False
            )
        q = list(state.queue)
        if q:
            lines = [f"`{i}.` [{s.title}]({s.webpage}) `{s.fmt_dur()}`" for i, s in enumerate(q[:10], 1)]
            if len(q) > 10:
                lines.append(f"... dan {len(q) - 10} lagi")
            e.add_field(name=f"📋 Antrian ({len(q)} lagu)", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="📋 Antrian", value="Kosong", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="nowplaying", description="Info lagu yang sedang diputar")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        if not state.current:
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        await interaction.response.send_message(embed=state.current.embed())

    @app_commands.command(name="deleteallqueue", description="Hapus semua antrian lagu")
    async def deleteallqueue(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        n     = len(state.queue)
        state.queue.clear()
        e = discord.Embed(
            title="🗑️ Queue Dihapus",
            description=f"**{n} lagu** dihapus dari antrian."
                        + (f"\n▶ `{state.current.title}` tetap diputar." if state.current else ""),
            color=0xef4444
        )
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="shuffle", description="Acak urutan antrian lagu")
    async def shuffle(self, interaction: discord.Interaction):
        import random
        state = self._state(interaction.guild.id)
        if not state.queue:
            await interaction.response.send_message("❌ Antrian kosong.", ephemeral=True)
            return
        q = list(state.queue)
        random.shuffle(q)
        state.queue = deque(q)
        await interaction.response.send_message(f"🔀 {len(q)} lagu diacak!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
