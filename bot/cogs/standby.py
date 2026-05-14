"""
standby.py — Bot 24/7 Standby di Voice Channel
- /standby set [channel]  → bot masuk & standby di channel ini
- /standby stop           → bot keluar & hapus standby
- Background loop 30 detik: kalau bot terputus, otomatis rejoin
- Tidak mengganggu musik: hanya rejoin kalau bot tidak ada di voice manapun
"""
import asyncio
import sys, os

import discord
from discord import app_commands
from discord.ext import commands, tasks

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db
from bot.utils.temp_msg import temp_send


class Standby(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._joining: set[int] = set()   # guild_id yang sedang proses join
        self.standby_loop.start()

    def cog_unload(self):
        self.standby_loop.cancel()

    # ── Slash Commands ────────────────────────────────────────────────────────

    standby_group = app_commands.Group(
        name="standby",
        description="Atur bot standby 24/7 di voice channel"
    )

    @standby_group.command(name="set", description="Set bot standby 24/7 di voice channel ini")
    @app_commands.describe(channel="Voice channel tempat bot standby")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def standby_set(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel
    ):
        await db.set_standby(interaction.guild_id, channel.id, enabled=True)

        # Langsung join sekarang
        try:
            vc = interaction.guild.voice_client
            if vc and vc.channel.id != channel.id:
                await vc.move_to(channel)
            elif not vc:
                await channel.connect(self_deaf=True)
        except Exception as e:
            await temp_send(interaction, f"⚠️ Gagal join channel: {e}", ephemeral=True)
            return

        await temp_send(
            interaction,
            f"✅ Bot sekarang standby 24/7 di **{channel.name}**!\n"
            f"Bot akan otomatis rejoin jika terputus.",
            ephemeral=True
        )

    @standby_group.command(name="stop", description="Hentikan standby bot dan keluarkan dari voice")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def standby_stop(self, interaction: discord.Interaction):
        await db.disable_standby(interaction.guild_id)

        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect(force=True)

        await temp_send(
            interaction,
            "⏹️ Standby bot dihentikan. Bot keluar dari voice channel.",
            ephemeral=True
        )

    @standby_group.command(name="status", description="Lihat status standby saat ini")
    async def standby_status(self, interaction: discord.Interaction):
        cfg = await db.get_standby(interaction.guild_id)
        if not cfg or not cfg["enabled"]:
            await temp_send(interaction, "❌ Standby tidak aktif.", ephemeral=True)
            return

        ch = interaction.guild.get_channel(cfg["channel_id"])
        ch_name = ch.name if ch else f"ID {cfg['channel_id']}"
        vc = interaction.guild.voice_client
        status = "🟢 Terhubung" if (vc and vc.channel and vc.channel.id == cfg["channel_id"]) else "🔴 Terputus (akan rejoin)"

        await temp_send(
            interaction,
            f"📡 **Standby aktif** di **{ch_name}**\n"
            f"Status: {status}",
            ephemeral=True
        )

    # ── Background Loop ───────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def standby_loop(self):
        await self.bot.wait_until_ready()
        try:
            rows = await db.get_all_standby()
        except Exception as e:
            print(f"[Standby] DB error: {e}", flush=True)
            return

        for row in rows:
            guild_id   = row["guild_id"]
            channel_id = row["channel_id"]

            if guild_id in self._joining:
                continue

            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            vc = guild.voice_client

            # Kalau bot sedang di voice channel lain (musik sedang main) → skip
            if vc and vc.channel and vc.channel.id != channel_id:
                continue

            # Kalau sudah di standby channel → tidak perlu join ulang
            if vc and vc.is_connected() and vc.channel.id == channel_id:
                continue

            # Bot tidak ada di voice / terputus → rejoin standby channel
            channel = guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                continue

            self._joining.add(guild_id)
            try:
                if vc and not vc.is_connected():
                    try:
                        await vc.disconnect(force=True)
                    except Exception:
                        pass

                await channel.connect(self_deaf=True)
                print(f"[Standby] Rejoin guild={guild_id} channel={channel.name}", flush=True)
            except Exception as e:
                print(f"[Standby] Gagal rejoin guild={guild_id}: {e}", flush=True)
            finally:
                self._joining.discard(guild_id)

    @standby_loop.before_loop
    async def before_standby(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)  # kasih waktu bot fully ready


async def setup(bot: commands.Bot):
    await bot.add_cog(Standby(bot))
