import asyncio, discord, subprocess, json, sys, os
from discord import app_commands
from discord.ext import commands

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.config import FFMPEG_PATH

YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

print(f"[Music] yt-dlp: {YTDLP}", flush=True)

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
    "executable": FFMPEG_PATH,
}


async def fetch_info(query: str) -> dict | None:
    loop = asyncio.get_event_loop()
    def _run():
        cmd = [YTDLP, "--no-playlist", "-f",
               "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
               "--default-search", "ytsearch",
               "--dump-json", "--no-warnings", "--quiet", query]
        print(f"[Music] yt-dlp: {query[:60]}", flush=True)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            if r.returncode != 0 or not r.stdout.strip():
                print(f"[Music] yt-dlp err: {r.stderr[:200]}", flush=True)
                return None
            return json.loads(r.stdout.strip())
        except Exception as e:
            print(f"[Music] fetch err: {e}", flush=True)
            return None

    data = await loop.run_in_executor(None, _run)
    if not data:
        return None

    url = data.get("url", "")
    if not url or "youtube.com/watch" in url or "youtu.be" in url:
        for fmt in reversed(data.get("formats", [])):
            u = fmt.get("url", "")
            if u and "googlevideo" in u:
                url = u
                break

    if not url:
        print(f"[Music] no stream URL for: {data.get('title')}", flush=True)
        return None

    print(f"[Music] OK: {data.get('title')} | {url[:60]}...", flush=True)
    return {
        "title":     data.get("title", "Unknown"),
        "url":       url,
        "webpage":   data.get("webpage_url", ""),
        "thumbnail": data.get("thumbnail"),
        "duration":  data.get("duration", 0),
        "uploader":  data.get("uploader", "Unknown"),
    }


class Song:
    def __init__(self, info: dict, requester=None):
        self.title    = info["title"]
        self.url      = info["url"]           # stream URL — always set
        self.webpage  = info.get("webpage", "")
        self.thumbnail= info.get("thumbnail")
        self.duration = info.get("duration", 0)
        self.uploader = info.get("uploader", "Unknown")
        self.requester= requester

    def fmt_dur(self):
        if not self.duration: return "∞"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    def embed(self, title="🎵 Sekarang Diputar"):
        desc = f"[{self.title}]({self.webpage})" if self.webpage else self.title
        e = discord.Embed(title=title, description=desc, color=0x9333ea)
        if self.thumbnail: e.set_thumbnail(url=self.thumbnail)
        e.add_field(name="⏱", value=self.fmt_dur(), inline=True)
        e.add_field(name="🎤", value=self.uploader, inline=True)
        if self.requester: e.add_field(name="👤", value=self.requester.mention, inline=True)
        return e


class MusicState:
    def __init__(self, bot, guild):
        self.bot     = bot
        self.guild   = guild
        self.queue:  list[Song]                = []
        self.current: Song | None              = None
        self.voice:  discord.VoiceClient | None = None
        self.volume  = 0.5
        self.channel: discord.TextChannel | None = None

    def play_next(self):
        """Dipanggil dari after callback — schedule play song berikutnya."""
        self.bot.loop.create_task(self._advance())

    async def _advance(self):
        if not self.queue:
            self.current = None
            return
        song = self.queue.pop(0)
        await self._play(song)

    async def _play(self, song: Song):
        if not (self.voice and self.voice.is_connected()):
            print("[Music] voice not connected in _play", flush=True)
            return
        self.current = song
        print(f"[Music] Playing: {song.title}", flush=True)
        try:
            src = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTS),
                volume=self.volume
            )
            self.voice.play(src, after=lambda e: self._after(e))
            await self._send(embed=song.embed())
        except Exception as e:
            print(f"[Music] play error: {e}", flush=True)
            await self._send(f"⚠️ Error: `{e}`")
            self.play_next()

    def _after(self, err):
        if err:
            print(f"[Music] FFmpeg err: {err}", flush=True)
        self.play_next()

    async def _send(self, msg=None, embed=None):
        if not self.channel: return
        try:
            if embed: await self.channel.send(embed=embed)
            elif msg: await self.channel.send(msg)
        except Exception: pass

    def skip(self):
        if self.voice and self.voice.is_playing():
            self.voice.stop()  # triggers _after → play_next

    def stop(self):
        self.queue.clear()
        self.current = None
        if self.voice and self.voice.is_playing():
            self.voice.stop()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot    = bot
        self.states: dict[int, MusicState] = {}

    def _state(self, guild) -> MusicState:
        if guild.id not in self.states:
            self.states[guild.id] = MusicState(self.bot, guild)
        return self.states[guild.id]

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

    @app_commands.command(name="play", description="Putar lagu dari YouTube atau sumber lain")
    @app_commands.describe(query="URL YouTube atau kata kunci pencarian")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await interaction.followup.send(f"🔍 Mencari: **{query}**...")

        # Ambil stream URL SEBELUM join voice
        info = await fetch_info(query)
        if not info:
            await interaction.followup.send("❌ Lagu tidak ditemukan!", ephemeral=True)
            return

        # Join voice SETELAH dapat URL
        state = await self._join(interaction)
        if not state:
            return

        song = Song(info, interaction.user)

        # Kalau sudah ada yang diputar → masuk queue
        if state.voice.is_playing() or state.voice.is_paused():
            state.queue.append(song)
            await interaction.followup.send(embed=song.embed("✅ Ditambahkan ke Queue"))
        else:
            # Langsung play sekarang — tidak lewat task
            await state._play(song)
            await interaction.followup.send(embed=song.embed("▶ Memutar"))

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        if not s.voice or not s.voice.is_playing():
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        s.skip()
        await interaction.response.send_message("⏭ Skip!")

    @app_commands.command(name="stop", description="Stop & keluar voice")
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

    @app_commands.command(name="queue", description="Lihat antrian lagu")
    async def queue_cmd(self, interaction: discord.Interaction):
        s = self._state(interaction.guild)
        e = discord.Embed(title="🎵 Queue", color=0x9333ea)
        if s.current:
            e.add_field(name="▶ Now", value=f"[{s.current.title}]({s.current.webpage}) `{s.current.fmt_dur()}`", inline=False)
        if s.queue:
            lines = [f"`{i}.` [{x.title}]({x.webpage}) `{x.fmt_dur()}`" for i, x in enumerate(s.queue[:10], 1)]
            e.add_field(name=f"📋 ({len(s.queue)})", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="📋", value="Kosong", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="nowplaying", description="Lagu yang sedang diputar")
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

    @app_commands.command(name="musictest", description="Test yt-dlp dan stream URL")
    @app_commands.describe(url="URL untuk test")
    async def musictest(self, interaction: discord.Interaction, url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
        await interaction.response.defer()
        info = await fetch_info(url)
        if info:
            e = discord.Embed(title="✅ yt-dlp OK!", color=0x22c55e)
            e.add_field(name="Judul", value=info["title"], inline=False)
            e.add_field(name="Stream URL", value=f"`{info['url'][:80]}...`", inline=False)
            e.add_field(name="yt-dlp", value=f"`{YTDLP}`", inline=False)
            await interaction.followup.send(embed=e)
        else:
            await interaction.followup.send(f"❌ Gagal! Path: `{YTDLP}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
