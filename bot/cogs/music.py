"""
Music cog — yt-dlp subprocess + FFmpegOpusAudio
- Join voice DULU, baru fetch lagu
- Timeout 30 detik untuk yt-dlp
- Error handling lengkap
"""
import asyncio
import subprocess
import json
import discord
import sys
import os
from discord import app_commands
from discord.ext import commands
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Path ke yt-dlp
YTDLP_PATH = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP_PATH):
    YTDLP_PATH = "yt-dlp"

FFMPEG_OPTS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 "
        "-reconnect_delay_max 5 -nostdin"
    ),
    "options": "-vn",
}


# ── fetch ──────────────────────────────────────────────────────────────────────

async def fetch_song(query: str, requester=None, timeout: int = 30):
    """Jalankan yt-dlp subprocess dengan timeout ketat."""
    loop = asyncio.get_event_loop()

    def _run():
        q = query if query.startswith("http") else f"ytsearch1:{query}"
        cmd = [
            YTDLP_PATH,
            "--no-playlist",
            "--no-warnings",
            "--quiet",
            "-f", "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "--dump-json",
            "--no-check-certificates",
            "--geo-bypass",
            q,
        ]
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if r.returncode != 0 or not r.stdout.strip():
                print(f"[Music] yt-dlp stderr: {r.stderr[:300]}", flush=True)
                return None
            return json.loads(r.stdout.strip().splitlines()[0])
        except subprocess.TimeoutExpired:
            print("[Music] yt-dlp timeout!", flush=True)
            return None
        except Exception as e:
            print(f"[Music] fetch error: {e}", flush=True)
            return None

    data = await asyncio.wait_for(
        loop.run_in_executor(None, _run),
        timeout=timeout + 5
    )
    if not data:
        return None

    # Dapatkan direct stream URL
    url = data.get("url", "")
    if not url:
        # Cari dari formats
        for fmt in reversed(data.get("formats", [])):
            u = fmt.get("url", "")
            if u and "googlevideo" in u:
                url = u
                break

    if not url:
        print(f"[Music] No stream URL for: {data.get('title')}", flush=True)
        return None

    print(f"[Music] OK: {data.get('title', 'Unknown')} | {url[:60]}", flush=True)
    return Song(data, url, requester)


# ── Song ──────────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, data: dict, stream_url: str, requester=None):
        self.title     = data.get("title", "Unknown")
        self.stream    = stream_url
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
        e.add_field(name="⏱ Durasi",  value=self.fmt_dur(), inline=True)
        e.add_field(name="🎤 Channel", value=self.uploader,  inline=True)
        if self.requester:
            e.add_field(name="👤 Request", value=self.requester.mention, inline=True)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        return e

    def make_source(self) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(self.stream, **FFMPEG_OPTS)


# ── State ─────────────────────────────────────────────────────────────────────

class GuildState:
    def __init__(self):
        self.queue:     deque[Song]                  = deque()
        self.current:   Song | None                  = None
        self.channel:   discord.abc.Messageable | None = None
        self.loop:      bool                         = False
        self.idle_task: asyncio.Task | None          = None


# ── Cog ───────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.states: dict[int, GuildState] = {}

    def _state(self, gid: int) -> GuildState:
        if gid not in self.states:
            self.states[gid] = GuildState()
        return self.states[gid]

    # ── internal ──────────────────────────────────────────────────────────────

    async def _join_vc(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        """Join atau pindah ke voice channel user."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Kamu harus masuk voice channel dulu!", ephemeral=True)
            return None
        target = interaction.user.voice.channel
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        try:
            if vc:
                if vc.channel.id != target.id:
                    await vc.move_to(target)
            else:
                vc = await target.connect(timeout=10, reconnect=True)
            return vc
        except Exception as e:
            print(f"[Music] join error: {e}", flush=True)
            await interaction.followup.send(f"❌ Gagal join voice: `{e}`", ephemeral=True)
            return None

    def _play_next(self, vc: discord.VoiceClient, state: GuildState):
        # Jika repeat aktif, putar ulang lagu yang sama
        if state.loop and state.current:
            song = state.current
            try:
                src = song.make_source()
                vc.play(src, after=lambda e: self._after(e, vc, state))
            except Exception as ex:
                print(f"[Music] repeat error: {ex}", flush=True)
                state.current = None
            return

        if state.queue:
            song = state.queue.popleft()
            state.current = song
            try:
                src = song.make_source()
                vc.play(src, after=lambda e: self._after(e, vc, state))
                if state.channel:
                    asyncio.run_coroutine_threadsafe(
                        state.channel.send(embed=song.embed()),
                        self.bot.loop,
                    )
            except Exception as ex:
                print(f"[Music] _play_next error: {ex}", flush=True)
                state.current = None
        else:
            # Queue habis — mulai timer idle
            state.current = None
            asyncio.run_coroutine_threadsafe(
                self._start_idle_timer(vc, state),
                self.bot.loop,
            )

    def _after(self, error, vc: discord.VoiceClient, state: GuildState):
        if error:
            print(f"[Music] after error: {error}", flush=True)
        self._play_next(vc, state)

    async def _start_idle_timer(self, vc: discord.VoiceClient, state: GuildState):
        """Tunggu 5 menit, lalu disconnect jika masih idle."""
        self._cancel_idle(state)  # batalkan timer sebelumnya jika ada

        async def _wait_and_leave():
            await asyncio.sleep(300)  # 5 menit
            if not state.current and vc and vc.is_connected():
                await vc.disconnect()
                if state.channel:
                    try:
                        await state.channel.send(
                            embed=discord.Embed(
                                title="👋 Auto Disconnect",
                                description="Bot keluar dari voice karena tidak ada lagu selama **5 menit**.",
                                color=0x6b7280,
                            )
                        )
                    except Exception:
                        pass

        state.idle_task = asyncio.create_task(_wait_and_leave())

    def _cancel_idle(self, state: GuildState):
        """Batalkan timer idle jika ada."""
        if state.idle_task and not state.idle_task.done():
            state.idle_task.cancel()
            state.idle_task = None

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube")
    @app_commands.describe(query="URL atau nama lagu")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        state = self._state(interaction.guild.id)
        state.channel = interaction.channel

        # 1. Join voice DULU
        vc = await self._join_vc(interaction)
        if not vc:
            return

        # Batalkan idle timer jika sedang berjalan
        self._cancel_idle(state)

        # 2. Beri tahu user kita sedang mencari
        await interaction.followup.send(f"🔍 Mencari: **{query}**...")

        # 3. Fetch dengan timeout
        try:
            song = await fetch_song(query, interaction.user, timeout=30)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Timeout! YouTube tidak merespons. Coba lagi.", ephemeral=True)
            return

        if not song:
            await interaction.followup.send(
                "❌ Lagu tidak ditemukan. Coba:\n"
                "• Gunakan URL langsung: `https://youtu.be/...`\n"
                "• Ganti kata kunci pencarian",
                ephemeral=True
            )
            return

        # 4. Play atau tambah ke queue
        if vc.is_playing() or vc.is_paused():
            state.queue.append(song)
            await interaction.followup.send(
                embed=song.embed(f"✅ Ditambahkan ke Queue (#{len(state.queue)})")
            )
        else:
            state.current = song
            try:
                src = song.make_source()
                vc.play(src, after=lambda e: self._after(e, vc, state))
                await interaction.followup.send(embed=song.embed("▶ Sekarang Memutar"))
            except Exception as e:
                print(f"[Music] play error: {e}", flush=True)
                state.current = None
                await interaction.followup.send(f"❌ Gagal memutar: `{e}`", ephemeral=True)

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message("⏭ Skip!")

    @app_commands.command(name="stop", description="Stop dan keluar voice")
    async def stop(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        state = self._state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹ Stop.")

    @app_commands.command(name="pause", description="Pause musik")
    async def pause(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)
            return
        vc.pause()
        await interaction.response.send_message("⏸ Pause.")

    @app_commands.command(name="resume", description="Lanjutkan musik")
    async def resume(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
        if not vc or not vc.is_paused():
            await interaction.response.send_message("❌ Tidak dalam keadaan pause.", ephemeral=True)
            return
        vc.resume()
        await interaction.response.send_message("▶ Lanjut.")

    @app_commands.command(name="queue", description="Lihat antrian lagu")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        e     = discord.Embed(title="🎵 Queue", color=0x9333ea)
        if state.current:
            c = state.current
            e.add_field(name="▶ Now", value=f"[{c.title}]({c.webpage}) `{c.fmt_dur()}`", inline=False)
        q = list(state.queue)
        if q:
            lines = [f"`{i}.` [{s.title}]({s.webpage}) `{s.fmt_dur()}`" for i, s in enumerate(q[:10], 1)]
            if len(q) > 10:
                lines.append(f"... +{len(q)-10} lagi")
            e.add_field(name=f"📋 ({len(q)} lagu)", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="📋", value="Kosong", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="nowplaying", description="Info lagu sekarang")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        if not state.current:
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        await interaction.response.send_message(embed=state.current.embed())

    @app_commands.command(name="deleteallqueue", description="Hapus semua antrian")
    async def deleteallqueue(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        n = len(state.queue)
        state.queue.clear()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🗑️ Queue Dihapus",
                description=f"**{n} lagu** dihapus."
                            + (f"\n▶ `{state.current.title}` tetap diputar." if state.current else ""),
                color=0xef4444
            )
        )

    @app_commands.command(name="shuffle", description="Acak urutan antrian")
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

    @app_commands.command(name="repeat", description="Aktifkan atau matikan repeat lagu sekarang")
    @app_commands.describe(mode="on = repeat aktif, off = repeat mati")
    @app_commands.choices(mode=[
        app_commands.Choice(name="on",  value="on"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def repeat(self, interaction: discord.Interaction, mode: str):
        state = self._state(interaction.guild.id)
        state.loop = (mode == "on")
        if state.loop:
            song_name = state.current.title if state.current else "—"
            e = discord.Embed(
                title="🔁 Repeat ON",
                description=f"Lagu **{song_name}** akan diputar berulang.",
                color=0x9333ea
            )
        else:
            e = discord.Embed(
                title="➡️ Repeat OFF",
                description="Repeat dinonaktifkan. Lagu berikutnya dari queue.",
                color=0x6b7280
            )
        await interaction.response.send_message(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
