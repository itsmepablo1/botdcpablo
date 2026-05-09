import asyncio, discord, subprocess, json, sys, os
from discord import app_commands
from discord.ext import commands

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

# Path yt-dlp dari venv yang sama dengan Python yang berjalan
YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

print(f"[Music] yt-dlp path: {YTDLP}", flush=True)

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
    "executable": FFMPEG_PATH,
}


# ── Fetch info via CLI (lebih reliable dari Python API) ───────────────────────

async def fetch_info(query: str) -> dict | None:
    loop = asyncio.get_event_loop()

    def _run():
        cmd = [
            YTDLP,
            "--no-playlist",
            "-f", "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "--default-search", "ytsearch",
            "--dump-json",
            "--no-warnings",
            "--quiet",
            query,
        ]
        print(f"[Music] CMD: {' '.join(cmd)}", flush=True)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            if r.returncode != 0 or not r.stdout.strip():
                print(f"[Music] yt-dlp stderr: {r.stderr[:400]}", flush=True)
                return None
            return json.loads(r.stdout.strip())
        except subprocess.TimeoutExpired:
            print("[Music] yt-dlp timeout", flush=True)
            return None
        except Exception as e:
            print(f"[Music] fetch_info error: {e}", flush=True)
            return None

    data = await loop.run_in_executor(None, _run)
    if not data:
        return None

    # Ambil stream URL
    url = data.get("url", "")
    if not url or "youtube.com/watch" in url or "youtu.be" in url:
        # Cari di formats[]
        for fmt in reversed(data.get("formats", [])):
            u = fmt.get("url", "")
            if u and ("googlevideo" in u or u.startswith("http")):
                url = u
                break

    if not url:
        print(f"[Music] No stream URL: {data.get('title')}", flush=True)
        return None

    print(f"[Music] ✓ {data.get('title')} | {url[:70]}...", flush=True)
    return {
        "title":     data.get("title", "Unknown"),
        "url":       url,
        "webpage":   data.get("webpage_url", ""),
        "thumbnail": data.get("thumbnail"),
        "duration":  data.get("duration", 0),
        "uploader":  data.get("uploader", "Unknown"),
    }


async def fetch_playlist(url: str) -> list[dict]:
    loop = asyncio.get_event_loop()

    def _run():
        cmd = [
            YTDLP, "--flat-playlist", "--dump-json",
            "--no-warnings", "--quiet", url,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            results = []
            for line in r.stdout.strip().splitlines():
                try:
                    e = json.loads(line)
                    results.append({
                        "title":    e.get("title", "Unknown"),
                        "url":      None,
                        "webpage":  e.get("url") or e.get("webpage_url", ""),
                        "thumbnail": e.get("thumbnail"),
                        "duration": e.get("duration", 0),
                        "uploader": e.get("uploader", "Unknown"),
                    })
                except Exception:
                    continue
            return results
        except Exception as e:
            print(f"[Music] playlist error: {e}", flush=True)
            return []

    return await loop.run_in_executor(None, _run)


# ── Song item ─────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, info: dict, requester=None):
        self.title     = info["title"]
        self.url       = info.get("url")       # stream URL (None = lazy)
        self.webpage   = info.get("webpage", "")
        self.thumbnail = info.get("thumbnail")
        self.duration  = info.get("duration", 0)
        self.uploader  = info.get("uploader", "Unknown")
        self.requester = requester

    async def resolve(self) -> bool:
        if self.url:
            return True
        if not self.webpage:
            return False
        info = await fetch_info(self.webpage)
        if info:
            self.url      = info["url"]
            self.title    = info["title"] or self.title
            self.thumbnail = info["thumbnail"] or self.thumbnail
            return True
        return False

    def fmt_dur(self):
        if not self.duration:
            return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    def embed(self, title="🎵 Sekarang Diputar"):
        desc = f"[{self.title}]({self.webpage})" if self.webpage else self.title
        e = discord.Embed(title=title, description=desc, color=0x9333ea)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱", value=self.fmt_dur(), inline=True)
        e.add_field(name="🎤", value=self.uploader, inline=True)
        if self.requester:
            e.add_field(name="👤", value=self.requester.mention, inline=True)
        return e


# ── Guild state ───────────────────────────────────────────────────────────────

class MusicState:
    IDLE = 300  # detik sebelum auto-disconnect

    def __init__(self, bot, guild):
        self.bot     = bot
        self.guild   = guild
        self.queue:  list[Song]               = []
        self.current: Song | None             = None
        self.voice:  discord.VoiceClient | None = None
        self.volume  = 0.5
        self.channel: discord.TextChannel | None = None
        self._next   = asyncio.Event()
        self._task   = bot.loop.create_task(self._loop())

    async def _loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self._next.clear()
            self.current = None

            if not self.queue:
                try:
                    await asyncio.wait_for(self._next.wait(), timeout=self.IDLE)
                except asyncio.TimeoutError:
                    if self.voice and self.voice.is_connected():
                        await self.voice.disconnect()
                        self.voice = None
                        await self._send("⏹ Keluar dari voice (idle).")
                    continue
                self._next.clear()

            if not self.queue:
                continue

            song = self.queue.pop(0)
            self.current = song
            print(f"[Music] Playing: {song.title}", flush=True)

            ok = await song.resolve()
            if not ok or not song.url:
                await self._send(f"⚠️ Gagal load **{song.title}** — di-skip.")
                self._next.set()
                continue

            if not (self.voice and self.voice.is_connected()):
                print("[Music] Voice disconnected before play", flush=True)
                self._next.set()
                continue

            try:
                src = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTS),
                    volume=self.volume
                )
                self.voice.play(src, after=lambda e: self._after(e))
                await self._send(embed=song.embed())
                await self._next.wait()
            except Exception as e:
                print(f"[Music] Play error: {e}", flush=True)
                await self._send(f"⚠️ Error: `{e}`")
                self._next.set()

    def _after(self, err):
        if err:
            print(f"[Music] FFmpeg error: {err}", flush=True)
        self.bot.loop.call_soon_threadsafe(self._next.set)

    async def _send(self, msg=None, embed=None):
        if not self.channel:
            return
        try:
            if embed:
                await self.channel.send(embed=embed)
            elif msg:
                await self.channel.send(msg)
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
        self._task.cancel()


# ── Cog ───────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot    = bot
        self.states: dict[int, MusicState] = {}

    def _state(self, guild) -> MusicState:
        if guild.id not in self.states:
            self.states[guild.id] = MusicState(self.bot, guild)
        return self.states[guild.id]

    def cog_unload(self):
        for s in self.states.values():
            s.cleanup()

    async def _join(self, interaction) -> MusicState | None:
        if not interaction.user.voice:
            await interaction.followup.send("❌ Masuk voice channel dulu!", ephemeral=True)
            return None
        state = self._state(interaction.guild)
        vc = interaction.user.voice.channel
        if state.voice and state.voice.is_connected():
            if state.voice.channel.id != vc.id:
                await state.voice.move_to(vc)
        else:
            state.voice = await vc.connect()
        state.channel = interaction.channel
        return state

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu — masukkan URL YouTube/Spotify atau kata kunci")
    @app_commands.describe(query="URL atau kata kunci lagu (YouTube, SoundCloud, dll)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await interaction.followup.send(f"🔍 Mencari: **{query}**...")

        is_playlist = ("playlist?list=" in query or
                       ("list=" in query and "watch" not in query and "youtube.com" in query))

        if is_playlist:
            entries = await fetch_playlist(query)
            if not entries:
                await interaction.followup.send("❌ Playlist tidak ditemukan!", ephemeral=True)
                return
            state = await self._join(interaction)
            if not state:
                return
            for e in entries:
                state.queue.append(Song(e, interaction.user))
            state._next.set()
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Playlist Ditambahkan",
                    description=f"{len(entries)} lagu masuk queue",
                    color=0x9333ea
                )
            )
        else:
            info = await fetch_info(query)
            if not info:
                await interaction.followup.send(
                    "❌ Lagu tidak ditemukan!\n"
                    f"Coba jalankan di VPS: `{YTDLP} --dump-json \"{query}\"`",
                    ephemeral=True
                )
                return
            state = await self._join(interaction)
            if not state:
                return
            song = Song(info, interaction.user)
            state.queue.append(song)
            state._next.set()
            await interaction.followup.send(embed=song.embed("✅ Ditambahkan ke Queue"))

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        if not s.voice or not s.voice.is_playing():
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        s.skip()
        await interaction.response.send_message("⏭ Skip!")

    @app_commands.command(name="stop", description="Stop & keluar dari voice")
    async def stop(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        s.stop()
        if s.voice:
            await s.voice.disconnect()
            s.voice = None
        await interaction.response.send_message("⏹ Stop.")

    @app_commands.command(name="pause", description="Pause musik")
    async def pause(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        if s.voice and s.voice.is_playing():
            s.voice.pause()
            await interaction.response.send_message("⏸ Pause.")
        else:
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)

    @app_commands.command(name="resume", description="Lanjutkan musik")
    async def resume(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        if s.voice and s.voice.is_paused():
            s.voice.resume()
            await interaction.response.send_message("▶ Resume.")
        else:
            await interaction.response.send_message("❌ Tidak dalam keadaan pause.", ephemeral=True)

    @app_commands.command(name="volume", description="Atur volume 0-100")
    @app_commands.describe(level="Volume 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Volume 0-100.", ephemeral=True)
            return
        s = self._state(interaction.guild)
        s.volume = level / 100
        if s.voice and s.voice.source:
            s.voice.source.volume = s.volume
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="queue", description="Lihat antrian")
    async def queue_cmd(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        e = discord.Embed(title="🎵 Queue", color=0x9333ea)
        if s.current:
            e.add_field(name="▶ Now", value=f"[{s.current.title}]({s.current.webpage}) `{s.current.fmt_dur()}`", inline=False)
        if s.queue:
            lines = [f"`{i}.` [{x.title}]({x.webpage}) `{x.fmt_dur()}`" for i, x in enumerate(s.queue[:10], 1)]
            e.add_field(name=f"📋 ({len(s.queue)} lagu)", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="📋", value="Kosong", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="nowplaying", description="Lagu sekarang")
    async def nowplaying(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        if not s.current:
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        await interaction.response.send_message(embed=s.current.embed())

    @app_commands.command(name="deleteallqueue", description="Hapus semua antrian")
    async def deleteallqueue(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        n = len(s.queue)
        s.queue.clear()
        await interaction.response.send_message(
            embed=discord.Embed(title="🗑️ Queue Dihapus", description=f"{n} lagu dihapus.", color=0xef4444)
        )

    @app_commands.command(name="musictest", description="Test yt-dlp & stream URL")
    @app_commands.describe(url="URL untuk test (default: Rick Astley)")
    async def musictest(self, interaction: discord.Interaction, url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
        await interaction.response.defer()
        info = await fetch_info(url)
        if info:
            e = discord.Embed(title="✅ yt-dlp OK", color=0x22c55e)
            e.add_field(name="Judul", value=info["title"], inline=False)
            e.add_field(name="Stream URL", value=f"`{info['url'][:80]}...`", inline=False)
            e.add_field(name="yt-dlp path", value=f"`{YTDLP}`", inline=False)
            await interaction.followup.send(embed=e)
        else:
            await interaction.followup.send(f"❌ Gagal!\nyt-dlp path: `{YTDLP}`\nCek log VPS.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
