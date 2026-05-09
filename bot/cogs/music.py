import discord
import wavelink
from discord import app_commands
from discord.ext import commands


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        """Pastikan bot sudah di voice channel. Return player atau None."""
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Masuk voice channel dulu!", ephemeral=True)
            return None

        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.disabled

        return player

    def _track_embed(self, track: wavelink.Playable, title="🎵 Sekarang Diputar") -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=f"[{track.title}]({track.uri})" if track.uri else track.title,
            color=0x9333ea
        )
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        if track.author:
            embed.add_field(name="🎤 Artis", value=track.author, inline=True)
        if track.length:
            m, s = divmod(track.length // 1000, 60)
            h, m2 = divmod(m, 60)
            dur = f"{h}:{m2:02}:{s:02}" if h else f"{m}:{s:02}"
            embed.add_field(name="⏱ Durasi", value=dur, inline=True)
        return embed

    # ── Events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        if not player or not hasattr(player, "_text_channel"):
            return
        channel = player._text_channel
        if channel:
            try:
                await channel.send(embed=self._track_embed(payload.track))
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player
        if not player:
            return
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
        else:
            # Queue kosong, disconnect setelah 5 menit idle
            await discord.utils.sleep_until(
                discord.utils.utcnow() + discord.utils.timedelta(seconds=300)
            )
            if player and not player.playing:
                await player.disconnect()

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        await player.disconnect()

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Putar lagu dari YouTube atau sumber lain")
    @app_commands.describe(query="URL atau kata kunci lagu")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        player = await self._get_player(interaction)
        if not player:
            return

        # Simpan text channel di player untuk notifikasi
        player._text_channel = interaction.channel  # type: ignore

        # Search / load
        tracks = await wavelink.Playable.search(query)
        if not tracks:
            await interaction.followup.send("❌ Lagu tidak ditemukan!", ephemeral=True)
            return

        # Playlist atau single track
        if isinstance(tracks, wavelink.Playlist):
            for track in tracks.tracks:
                track.extras = {"requester": interaction.user.mention}
                player.queue.put(track)
            if not player.playing:
                first = player.queue.get()
                await player.play(first)
            embed = discord.Embed(
                title="✅ Playlist Ditambahkan",
                description=f"**{tracks.name}** — {len(tracks.tracks)} lagu",
                color=0x9333ea
            )
            if hasattr(tracks, 'artwork') and tracks.artwork:
                embed.set_thumbnail(url=tracks.artwork)
            await interaction.followup.send(embed=embed)
        else:
            track = tracks[0]
            track.extras = {"requester": interaction.user.mention}

            if player.playing or not player.queue.is_empty:
                player.queue.put(track)
                await interaction.followup.send(embed=self._track_embed(track, "✅ Ditambahkan ke Queue"))
            else:
                await player.play(track)
                await interaction.followup.send(embed=self._track_embed(track, "▶ Memutar"))

    @app_commands.command(name="skip", description="Skip lagu sekarang")
    async def skip(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.playing:
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)
            return
        await player.skip(force=True)
        await interaction.response.send_message("⏭ Di-skip!")

    @app_commands.command(name="stop", description="Stop musik & keluar voice")
    async def stop(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            await interaction.response.send_message("❌ Bot tidak di voice.", ephemeral=True)
            return
        player.queue.clear()
        await player.stop()
        await player.disconnect()
        await interaction.response.send_message("⏹ Stop & keluar.")

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
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        embed = discord.Embed(title="🎵 Queue", color=0x9333ea)

        if player and player.current:
            t = player.current
            embed.add_field(
                name="▶ Sekarang",
                value=f"[{t.title}]({t.uri})" if t.uri else t.title,
                inline=False
            )

        if player and not player.queue.is_empty:
            lines = []
            for i, t in enumerate(list(player.queue)[:10], 1):
                lines.append(f"`{i}.` [{t.title}]({t.uri})" if t.uri else f"`{i}.` {t.title}")
            total = len(player.queue)
            embed.add_field(name=f"📋 Antrian ({total} lagu)", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📋 Antrian", value="Kosong", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Lagu yang sedang diputar")
    async def nowplaying(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.current:
            await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)
            return
        await interaction.response.send_message(embed=self._track_embed(player.current))

    @app_commands.command(name="deleteallqueue", description="Hapus semua antrian lagu")
    async def deleteallqueue(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            await interaction.response.send_message("❌ Bot tidak di voice.", ephemeral=True)
            return
        n = len(player.queue)
        player.queue.clear()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🗑️ Queue Dihapus",
                description=f"**{n} lagu** dihapus dari antrian." +
                            (f"\n▶ `{player.current.title}` tetap diputar." if player.current else ""),
                color=0xef4444
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
