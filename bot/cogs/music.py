import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

# ─── yt-dlp options ──────────────────────────────────────────────────────────

# Untuk single video / pencarian (ambil stream URL sekaligus)
YTDL_SINGLE = {
    "format":             "bestaudio/best",
    "noplaylist":         True,
    "nocheckcertificate": True,
    "ignoreerrors":       True,
    "quiet":              True,
    "no_warnings":        True,
    "default_search":     "ytsearch",
    "source_address":     "0.0.0.0",
}

# Untuk playlist (cepat, ambil metadata saja)
YTDL_PLAYLIST = {
    "format":             "bestaudio/best",
    "noplaylist":         False,
    "nocheckcertificate": True,
    "ignoreerrors":       True,
    "quiet":              True,
    "no_warnings":        True,
    "source_address":     "0.0.0.0",
    "extract_flat":       "in_playlist",
}

# Untuk resolve stream URL per lagu saat play (playlist entries)
YTDL_RESOLVE = {
    "format":             "bestaudio/best",
    "noplaylist":         True,
    "nocheckcertificate": True,
    "ignoreerrors":       False,
    "quiet":              True,
    "no_warnings":        True,
    "source_address":     "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
    "executable":     FFMPEG_PATH,
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_stream_url(url: str) -> bool:
    """Cek apakah URL adalah stream audio (bukan halaman YouTube)."""
    if not url:
        return False
    NOT_STREAM = ("youtube.com/watch", "youtu.be/", "youtube.com/shorts", "youtube.com/playlist")
    return not any(s in url for s in NOT_STREAM)

def _extract_stream_from_data(data: dict) -> str | None:
    """Ambil URL stream audio dari hasil extract_info yt-dlp."""
    # Coba dari key 'url' langsung
    url = data.get("url", "")
    if _is_stream_url(url):
        return url

    # Cari di formats[] — pilih audio-only, bitrate tertinggi
    formats = data.get("formats", [])
    audio_only = [
        f for f in formats
        if f.get("url")
        and f.get("acodec", "none") != "none"
        and f.get("vcodec", "none") == "none"
        and _is_stream_url(f.get("url", ""))
    ]
    if audio_only:
        audio_only.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
        return audio_only[0]["url"]

    # Fallback: format apapun yang punya stream URL
    all_fmts = [f for f in formats if f.get("url") and _is_stream_url(f.get("url", ""))]
    if all_fmts:
        all_fmts.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
        return all_fmts[0]["url"]

    return None


# ─── Song ─────────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, data: dict, stream_url: str = None):
        self.webpage    = data.get("webpage_url") or data.get("url", "")
        self.title      = data.get("title", "Unknown")
        self.thumbnail  = data.get("thumbnail")
        self.duration   = data.get("duration", 0)
        self.uploader   = data.get("uploader", "Unknown")
        self.requester  = None

        # Stream URL sudah tersedia (untuk single video) atau None (playlist, resolve saat play)
        self._stream_url = stream_url or _extract_stream_from_data(data)

        # Kalau stream URL ada di 'url' tapi itu adalah halaman YouTube,
        # simpan sebagai webpage dan clear stream
        if self._stream_url and not _is_stream_url(self._stream_url):
            self._stream_url = None
        if self.webpage and _is_stream_url(self.webpage):
            # webpage adalah stream URL, bukan halaman — swap
            self._stream_url = self._stream_url or self.webpage
            self.webpage = data.get("webpage_url", "")

    # ── Factory ───────────────────────────────────────────────────────────────

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
            # ── Playlist: ambil metadata saja (cepat) ────────────────────────
            print(f"[Music] Mode: PLAYLIST | {query[:80]}")
            ydl  = yt_dlp.YoutubeDL(YTDL_PLAYLIST)
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            if not data:
                print("[Music] from_query: playlist extraction return None")
                return []
            if "entries" in data:
                songs = []
                for entry in data["entries"]:
                    if not entry:
                        continue
                    songs.append(Song(entry))  # stream URL akan di-resolve saat play
                print(f"[Music] Playlist: {len(songs)} lagu masuk antrian")
                return songs[:100]
            return [Song(data)]

        else:
            # ── Single video / search: ambil stream URL sekaligus ─────────────
            print(f"[Music] Mode: SINGLE/SEARCH | {query[:80]}")
            ydl  = yt_dlp.YoutubeDL(YTDL_SINGLE)
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            if not data:
                print("[Music] from_query: single extraction return None")
                return []

            # Kalau ada entries (hasil ytsearch), ambil entri pertama yang punya data lengkap
            if "entries" in data:
                for entry in data["entries"]:
                    if not entry:
                        continue
                    # Entry dari ytsearch mungkin hanya metadata, extract full info
                    stream = _extract_stream_from_data(entry)
                    if stream:
                        s = Song(entry, stream_url=stream)
                        print(f"[Music] ✓ Found: {s.title} | stream cached")
                        return [s]
                    # Tidak ada stream di entry, coba resolve full
                    entry_url = entry.get("webpage_url") or entry.get("url", "")
                    if entry_url:
                        full = await loop.run_in_executor(
                            None, lambda u=entry_url: yt_dlp.YoutubeDL(YTDL_RESOLVE).extract_info(u, download=False)
                        )
                        if full:
                            stream = _extract_stream_from_data(full)
                            s = Song(full, stream_url=stream)
                            print(f"[Music] ✓ Found (resolved): {s.title}")
                            return [s]
                return []

            # Data langsung (bukan list entries)
            stream = _extract_stream_from_data(data)
            song   = Song(data, stream_url=stream)
            print(f"[Music] ✓ Found: {song.title} | stream {'cached' if stream else 'will resolve'}")
            return [song]

    # ── Stream resolve (lazy, untuk playlist) ─────────────────────────────────

    async def get_stream_url(self) -> str:
        # Jika sudah ada stream URL (dari single video), langsung pakai
        if self._stream_url and _is_stream_url(self._stream_url):
            print(f"[Music] ✓ Using cached stream: {self.title}")
            return self._stream_url

        # Playlist entry: resolve sekarang
        resolve_url = self.webpage
        if not resolve_url:
            raise Exception(f"Tidak ada URL untuk: {self.title}")

        print(f"[Music] Resolving stream (playlist entry): {resolve_url[:80]}")
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(YTDL_RESOLVE).extract_info(resolve_url, download=False)
        )
        if not data:
            raise Exception(f"yt-dlp return None untuk: {resolve_url}")

        stream = _extract_stream_from_data(data)
        if not stream:
            raise Exception(f"Tidak dapat menemukan stream URL untuk: {self.title} ({resolve_url})")

        # Update metadata
        self.title     = data.get("title")     or self.title
        self.thumbnail = data.get("thumbnail") or self.thumbnail
        self.duration  = data.get("duration")  or self.duration
        self.uploader  = data.get("uploader")  or self.uploader
        self.webpage   = data.get("webpage_url") or self.webpage
        self._stream_url = stream

        print(f"[Music] ✓ Resolved: {self.title}")
        return stream

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
            description=f"[{self.title}]({self.webpage})" if self.webpage else self.title,
            color=0x9333ea
        )
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱ Durasi",   value=self.duration_str(), inline=True)
        e.add_field(name="🎤 Artis",   value=self.uploader,       inline=True)
        if self.requester:
            e.add_field(name="👤 Request oleh", value=self.requester.mention, inline=True)
        return e


# ─── GuildMusicState ──────────────────────────────────────────────────────────

class GuildMusicState:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot          = bot
        self.guild        = guild
        self.queue:       list[Song]                 = []
        self.current:     Song | None                = None
        self.voice:       discord.VoiceClient | None = None
        self.volume       = 0.5
        self.text_channel: discord.TextChannel | None = None  # untuk kirim notif error
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
            print(f"[Music] Mulai proses: {self.current.title}")

            # ── 1. Resolve stream URL ─────────────────────────────────────────
            try:
                stream_url = await self.current.get_stream_url()
            except Exception as e:
                print(f"[Music] ✗ Gagal resolve stream '{self.current.title}': {e}")
                await self._notify(f"⚠️ Gagal load `{self.current.title}`: {e}")
                self._next.set()
                continue

            # ── 2. Tunggu voice terkoneksi ────────────────────────────────────
            for _ in range(20):
                if self.voice and self.voice.is_connected():
                    break
                await asyncio.sleep(0.5)

            if not (self.voice and self.voice.is_connected()):
                print("[Music] ✗ Voice tidak terkoneksi.")
                self._next.set()
                continue

            # ── 3. Play ──────────────────────────────────────────────────────
            try:
                print(f"[Music] Playing: {self.current.title} | URL: {stream_url[:60]}...")
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
                    volume=self.volume
                )
                self.voice.play(
                    source,
                    after=lambda e: self._on_play_end(e)
                )

                # Kirim embed "Sekarang Diputar"
                await self._notify(embed=self.current.embed())
                await self._next.wait()

            except Exception as e:
                print(f"[Music] ✗ Error saat play '{self.current.title}': {e}")
                await self._notify(f"⚠️ Error play `{self.current.title}`: {e}")
                self._next.set()

        print("[Music] Player loop selesai.")

    def _on_play_end(self, error):
        if error:
            print(f"[Music] FFmpeg error: {error}")
        self.bot.loop.call_soon_threadsafe(self._next.set)

    async def _notify(self, content: str = None, embed: discord.Embed = None):
        """Kirim notifikasi ke text channel jika tersedia."""
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
        # Simpan text channel untuk notifikasi
        state.text_channel = interaction.channel
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
            await interaction.response.send_message("📋 Antrian sudah kosong.", ephemeral=True)
            return
        jumlah = len(state.queue)
        state.queue.clear()
        embed = discord.Embed(
            title="🗑️ Antrian Dihapus",
            description=(
                f"**{jumlah} lagu** berhasil dihapus dari antrian.\n"
                + (f"▶ Lagu **{state.current.title}** tetap diputar." if state.current else "")
            ),
            color=0xef4444,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
