import discord
from discord import app_commands
from discord.ext import commands, tasks
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db
from bot.utils.stream_checker import get_streaming_activity, check_youtube_live, check_tiktok_live

class Streaming(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active: dict[tuple, int] = {}  # (guild_id, user_id) -> alert_id

    # ── Discord Presence Detection ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild
        cfg   = await db.get_guild_config(guild.id)
        notif_ch_id        = cfg.get("streaming_channel_id")
        streamer_role_id   = cfg.get("streaming_role_id")
        on_stream_role_id  = cfg.get("streaming_on_stream_role_id")

        # Harus ada minimal streamer_role_id
        if not streamer_role_id:
            return

        streamer_role = guild.get_role(int(streamer_role_id))
        if not streamer_role or streamer_role not in after.roles:
            return

        key        = (guild.id, after.id)
        was_stream = get_streaming_activity(before)
        is_stream  = get_streaming_activity(after)

        # ── Started streaming ──────────────────────────────────────────────────
        if not was_stream and is_stream:
            # Add "On Stream" role
            if on_stream_role_id:
                on_role = guild.get_role(int(on_stream_role_id))
                if on_role and on_role not in after.roles:
                    try:
                        await after.add_roles(on_role, reason="Member mulai streaming")
                    except discord.Forbidden:
                        pass

            # Kirim notif ke channel (kalau diset)
            if notif_ch_id and key not in self._active:
                channel = guild.get_channel(int(notif_ch_id))
                if channel:
                    embed    = self._build_stream_embed(after, is_stream)
                    msg      = await channel.send(
                        content=f"🔴 {after.mention} sedang **LIVE!**",
                        embed=embed
                    )
                    alert_id = await db.add_streamer_alert(
                        guild.id, after.id,
                        is_stream["platform"],
                        is_stream["url"]
                    )
                    await db.update_streamer_alert_message(alert_id, msg.id)
                    self._active[key] = alert_id

        # ── Stopped streaming ──────────────────────────────────────────────────
        elif was_stream and not is_stream:
            # Remove "On Stream" role
            if on_stream_role_id:
                on_role = guild.get_role(int(on_stream_role_id))
                if on_role and on_role in after.roles:
                    try:
                        await after.remove_roles(on_role, reason="Member berhenti streaming")
                    except discord.Forbidden:
                        pass

            if key in self._active:
                await db.end_streamer_alert(guild.id, after.id)
                del self._active[key]

    def _build_stream_embed(self, member: discord.Member, info: dict) -> discord.Embed:
        platform = info.get("platform", "Unknown")
        colors   = {"YouTube": 0xFF0000, "TikTok": 0x000000, "Twitch": 0x9146FF}
        icons    = {"YouTube": "🎬", "TikTok": "🎵", "Twitch": "🟣"}
        color    = colors.get(platform, 0x9333ea)
        icon     = icons.get(platform, "🔴")

        embed = discord.Embed(
            title=f"{icon} {info.get('title', member.display_name + ' is streaming')}",
            url=info.get("url") or discord.embeds.EmptyEmbed,
            color=color
        )
        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url
        )
        embed.add_field(name="📺 Platform", value=platform, inline=True)
        embed.add_field(name="🎙 Streamer", value=member.mention, inline=True)
        if info.get("url"):
            embed.add_field(name="🔗 Link", value=info["url"], inline=False)
        if info.get("thumbnail"):
            embed.set_image(url=info["thumbnail"])
        embed.set_footer(text="Klik link untuk nonton!")
        return embed

    # ── Slash Commands ────────────────────────────────────────────────────────

    stream_group = app_commands.Group(name="streaming", description="Konfigurasi notifikasi streaming")

    @stream_group.command(name="setup", description="Setup notif streaming dengan Channel ID, Streamer Role, dan On Stream Role")
    @app_commands.describe(
        channel_id="Channel ID untuk notifikasi (kosongkan jika tidak perlu notif)",
        role_id="Role ID Streamer — role yang menandai siapa streamer",
        on_stream_role_id="Role ID On Stream — otomatis ditambah saat live, dihapus saat offline"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_setup(
        self,
        interaction: discord.Interaction,
        role_id: str,
        on_stream_role_id: str,
        channel_id: str = ""
    ):
        try:
            rid  = int(role_id)
            orid = int(on_stream_role_id)
            cid  = int(channel_id) if channel_id else None
        except ValueError:
            await interaction.response.send_message("❌ Role ID harus angka!", ephemeral=True)
            return

        streamer_role = interaction.guild.get_role(rid)
        on_role       = interaction.guild.get_role(orid)
        ch            = interaction.guild.get_channel(cid) if cid else None

        if not streamer_role:
            await interaction.response.send_message(f"❌ Streamer Role `{rid}` tidak ditemukan.", ephemeral=True); return
        if not on_role:
            await interaction.response.send_message(f"❌ On Stream Role `{orid}` tidak ditemukan.", ephemeral=True); return
        if cid and not ch:
            await interaction.response.send_message(f"❌ Channel `{cid}` tidak ditemukan.", ephemeral=True); return

        await db.set_guild_config(
            interaction.guild.id,
            streaming_channel_id=cid,
            streaming_role_id=rid,
            streaming_on_stream_role_id=orid
        )
        embed = discord.Embed(title="✅ Streaming Setup Berhasil!", color=0x9333ea)
        embed.add_field(name="🎭 Streamer Role",  value=streamer_role.mention, inline=True)
        embed.add_field(name="🔴 On Stream Role", value=on_role.mention, inline=True)
        embed.add_field(name="📢 Notif Channel",  value=ch.mention if ch else "Tidak diset", inline=True)
        embed.add_field(
            name="ℹ️ Cara Kerja",
            value=(
                f"Member dengan **{streamer_role.mention}** yang mulai streaming via Discord "
                f"akan otomatis mendapat **{on_role.mention}**. "
                f"Role tersebut dihapus saat mereka berhenti streaming."
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stream_group.command(name="info", description="Lihat konfigurasi streaming notif saat ini")
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_info(self, interaction: discord.Interaction):
        cfg  = await db.get_guild_config(interaction.guild.id)
        cid  = cfg.get("streaming_channel_id")
        rid  = cfg.get("streaming_role_id")
        orid = cfg.get("streaming_on_stream_role_id")
        embed = discord.Embed(title="📡 Streaming Config", color=0x9333ea)
        ch       = interaction.guild.get_channel(cid) if cid else None
        role     = interaction.guild.get_role(int(rid))  if rid  else None
        on_role  = interaction.guild.get_role(int(orid)) if orid else None
        embed.add_field(name="📢 Notif Channel",  value=ch.mention      if ch      else "Belum diset", inline=True)
        embed.add_field(name="🎭 Streamer Role",  value=role.mention     if role    else "Belum diset", inline=True)
        embed.add_field(name="🔴 On Stream Role", value=on_role.mention  if on_role else "Belum diset", inline=True)
        embed.add_field(name="🔴 Sedang Live",    value=str(len(self._active)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stream_group.command(name="disable", description="Matikan notifikasi streaming")
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_disable(self, interaction: discord.Interaction):
        await db.set_guild_config(
            interaction.guild.id,
            streaming_channel_id=None,
            streaming_role_id=None
        )
        await interaction.response.send_message("✅ Streaming notif dimatikan.", ephemeral=True)

    @stream_group.command(name="test", description="Test kirim notif streaming ke channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cfg = await db.get_guild_config(interaction.guild.id)
        cid  = cfg.get("streaming_channel_id")
        rid  = cfg.get("streaming_role_id")
        orid = cfg.get("streaming_on_stream_role_id")

        results = []

        # Test 1: Notif channel
        if cid:
            ch = interaction.guild.get_channel(int(cid))
            if ch:
                fake_info = {
                    "platform":  "YouTube",
                    "title":     "🧪 Test Stream Notification",
                    "url":       "https://youtube.com",
                    "thumbnail": None,
                }
                embed = self._build_stream_embed(interaction.user, fake_info)
                await ch.send(content=f"🔴 {interaction.user.mention} sedang **LIVE!** *(test)*", embed=embed)
                results.append(f"✅ Notif dikirim ke {ch.mention}")
            else:
                results.append("❌ Channel notif tidak ditemukan")
        else:
            results.append("⚠️ Channel notif belum diset (skip)")

        # Test 2: On Stream role
        if orid:
            on_role = interaction.guild.get_role(int(orid))
            if on_role:
                try:
                    await interaction.user.add_roles(on_role, reason="Test /testnotif")
                    results.append(f"✅ On Stream role **{on_role.name}** ditambahkan ke kamu")
                    # Remove setelah 5 detik
                    import asyncio
                    await asyncio.sleep(5)
                    await interaction.user.remove_roles(on_role, reason="Test selesai")
                    results.append(f"✅ On Stream role dihapus (5 detik)")
                except discord.Forbidden:
                    results.append("❌ Bot tidak punya izin kelola role ini")
            else:
                results.append("❌ On Stream role tidak ditemukan")
        else:
            results.append("⚠️ On Stream role belum diset (skip)")

        # Test 3: Streamer role check
        if rid:
            streamer_role = interaction.guild.get_role(int(rid))
            has_role = streamer_role in interaction.user.roles if streamer_role else False
            results.append(f"{'✅' if has_role else '⚠️'} Streamer role: **{streamer_role.name if streamer_role else 'tidak ditemukan'}** "
                          f"({'kamu punya' if has_role else 'kamu belum punya — assign dulu untuk auto-detect'})")
        else:
            results.append("⚠️ Streamer role belum diset")

        embed = discord.Embed(
            title="🧪 Streaming Test Results",
            description="\n".join(results),
            color=0x9333ea
        )
        embed.set_footer(text="Semua fitur streaming sudah ditest!")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Streaming(bot))
