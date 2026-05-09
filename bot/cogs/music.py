"""
Music cog — Hybrid approach:
- yt-dlp CLI  : ambil stream URL dari YouTube (terbukti berhasil)
- wavelink     : play URL tersebut via Lavalink (handles Discord DAVE encryption)
"""
import asyncio, discord, subprocess, json, sys, os
import wavelink
from discord import app_commands
from discord.ext import commands

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YTDLP):
    YTDLP = "yt-dlp"

print(f"[Music] yt-dlp: {YTDLP}", flush=True)


# ── yt-dlp fetch ──────────────────────────────────────────────────────────────

async def fetch_info(query: str) -> dict | None:
    """Gunakan yt-dlp CLI untuk dapatkan stream URL langsung."""
    loop = asyncio.get_event_loop()

    def _run():
        cmd = [
            YTDLP, "--no-playlist",
            "-f", "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "--default-search", "ytsearch",
            "--dump-json", "--no-warnings", "--quiet", query,
        ]
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
        print(f"[Music] no stream URL: {data.get('title')}", flush=True)
        return None

    print(f"[Music] OK: {data.get('title')} | {url[:60]}...", flush=True)
    return {
        "title":    data.get("title", "Unknown"),
        "url":      url,
        "webpage":  data.get("webpage_url", ""),
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration", 0),
        "uploader": data.get("uploader", "Unknown"),
    }


# ── Song (metadata holder) ────────────────────────────────────────────────────

class Song:
    def __init__(self, info: dict, requester=None):
        self.title    = info["title"]
        self.url      = info["url"]
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

    def embed(self, title="🎵 Sekarang Diputar") -> discord.Embed:
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
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.queue: list[Song] = []
        self.current: Song | None = None
        self.channel: discord.TextChannel | None = None

    async def play_song(self, song: Song, player: wavelink.Player):
        """Load stream URL ke Lavalink dan play."""
        self.current = song
        print(f"[Music] Playing via Lavalink: {song.title}", flush=True)

        # Load URL langsung ke Lavalink (HTTP source, bukan YouTube source)
        tracks = await wavelink.Playable.search(song.url)
        if not tracks:
            print(f"[Music] Lavalink gagal load URL untuk: {song.title}", flush=True)
            if self.channel:
                await self.channel.send(f"⚠️ Gagal load **{song.title}**")
            return

        track = tracks[0] if isinstance(tracks, list) else tracks
        await player.play(track)

    async def send(self, msg=None, embed=None):
        if not self.channel:
            return
        try:
            if embed:
                await self.channel.send(embed=embed)
            elif msg:
                await self.channel.send(msg)
        except Exception:
            pass


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, MusicState] = {}

    def _state(self, guild_id: int) -> MusicState:
        if guild_id not in self.states:
            self.states[guild_id] = MusicState(guild_id)
        return self.states[guild_id]

    async def _get_player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Masuk voice channel dulu!", ephemeral=True)
            return None
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.disabled
        state = self._state(interaction.guild.id)
        state.channel = interaction.channel
        player._state = state  # type: ignore
        return player

    # ── Events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return
        state: MusicState = getattr(player, "_state", None)
        if not state:
            return
        if state.queue:
            next_song = state.queue.pop(0)
            await state.play_song(next_song, player)
            await state.send(embed=next_song.embed())
        else:
            state.current = None

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        player = payload.player
        state: MusicState = getattr(player, "_state", None)
        err = payload.exception.get("message", "Unknown error") if payload.exception else "Unknown"
        print(f"[Music] Track exception: {err}", flush=True)
        if state:
            await state.send(f"⚠️ Error saat memutar: `{err}`")
            if state.queue:
                next_song = state.queue.pop(0)
                await state.play_song(next_song, player)

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube atau sumber lain")
    @app_commands.describe(query="URL atau kata kunci lagu")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await interaction.followup.send(f"🔍 Mencari: **{query}**...")

        # Fetch stream URL via yt-dlp (terbukti berhasil)
        info = await fetch_info(query)
        if not info:
            await interaction.followup.send("❌ Lagu tidak ditemukan!", ephemeral=True)
            return

        # Join voice via Lavalink (handles Discord DAVE encryption)
        player = await self._get_player(interaction)
        if not player:
            return

        song = Song(info, interaction.user)
        state = self._state(interaction.guild.id)

        if player.playing or player.paused:
            state.queue.append(song)
            await interaction.followup.send(embed=song.embed("✅ Ditambahkan ke Queue"))
        else:
            await state.play_song(song, player)
            await interaction.followup.send(embed=song.embed("▶ Memutar"))

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.playing:
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        await player.skip(force=True)
        await interaction.response.send_message("⏭ Di-skip!")

    @app_commands.command(name="stop", description="Stop musik & keluar voice")
    async def stop(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        state = self._state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        if player:
            await player.stop()
            await player.disconnect()
        await interaction.response.send_message("⏹ Stop.")

    @app_commands.command(name="pause", description="Pause musik")
    async def pause(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.playing:
            await interaction.response.send_message("❌ Tidak ada yang diputar.", ephemeral=True)
            return
        await player.pause(True)
        await interaction.response.send_message("⏸ Di-pause.")

    @app_commands.command(name="resume", description="Lanjutkan musik")
    async def resume(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.paused:
            await interaction.response.send_message("❌ Tidak dalam keadaan pause.", ephemeral=True)
            return
        await player.pause(False)
        await interaction.response.send_message("▶ Dilanjutkan.")

    @app_commands.command(name="volume", description="Atur volume 0-100")
    @app_commands.describe(level="Volume 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Volume harus 0-100.", ephemeral=True)
            return
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            await interaction.response.send_message("❌ Bot tidak di voice.", ephemeral=True)
            return
        await player.set_volume(level)
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="queue", description="Lihat antrian lagu")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        e = discord.Embed(title="🎵 Queue", color=0x9333ea)
        if state.current:
            e.add_field(name="▶ Now", value=f"[{state.current.title}]({state.current.webpage}) `{state.current.fmt_dur()}`", inline=False)
        if state.queue:
            lines = [f"`{i}.` [{s.title}]({s.webpage}) `{s.fmt_dur()}`" for i, s in enumerate(state.queue[:10], 1)]
            e.add_field(name=f"📋 ({len(state.queue)} lagu)", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="📋", value="Kosong", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="nowplaying", description="Lagu yang sedang diputar")
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
                description=f"**{n} lagu** dihapus." + (f"\n▶ `{state.current.title}` tetap diputar." if state.current else ""),
                color=0xef4444
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
