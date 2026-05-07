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
        notif_ch_id = cfg.get("streaming_channel_id")
        role_id     = cfg.get("streaming_role_id")
        if not notif_ch_id or not role_id:
            return

        role = guild.get_role(int(role_id))
        if not role or role not in after.roles:
            return

        channel = guild.get_channel(int(notif_ch_id))
        if not channel:
            return

        key          = (guild.id, after.id)
        was_stream   = get_streaming_activity(before)
        is_stream    = get_streaming_activity(after)

        # Started streaming
        if not was_stream and is_stream:
            if key not in self._active:
                embed = self._build_stream_embed(after, is_stream)
                msg   = await channel.send(
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

        # Stopped streaming
        elif was_stream and not is_stream:
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

    @stream_group.command(name="setup", description="Setup notif streaming dengan Channel ID dan Role ID")
    @app_commands.describe(
        channel_id="Channel ID untuk notifikasi (gunakan Channel ID)",
        role_id="Role ID streamer (gunakan Role ID)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_setup(self, interaction: discord.Interaction, channel_id: str, role_id: str):
        try:
            cid = int(channel_id)
            rid = int(role_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID dan Role ID harus angka!", ephemeral=True)
            return

        ch   = interaction.guild.get_channel(cid)
        role = interaction.guild.get_role(rid)

        if not ch:
            await interaction.response.send_message(f"❌ Channel `{cid}` tidak ditemukan.", ephemeral=True); return
        if not role:
            await interaction.response.send_message(f"❌ Role `{rid}` tidak ditemukan.", ephemeral=True); return

        await db.set_guild_config(
            interaction.guild.id,
            streaming_channel_id=cid,
            streaming_role_id=rid
        )
        embed = discord.Embed(
            title="✅ Streaming Notif Aktif!",
            color=0x9333ea
        )
        embed.add_field(name="📢 Channel Notif", value=ch.mention, inline=True)
        embed.add_field(name="🎭 Role Streamer", value=role.mention, inline=True)
        embed.add_field(
            name="ℹ️ Cara Kerja",
            value=(
                "Member dengan role tersebut yang mulai streaming (Twitch/YouTube/TikTok) "
                "via Discord akan otomatis dinotifikasi."
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stream_group.command(name="info", description="Lihat konfigurasi streaming notif saat ini")
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_info(self, interaction: discord.Interaction):
        cfg = await db.get_guild_config(interaction.guild.id)
        cid = cfg.get("streaming_channel_id")
        rid = cfg.get("streaming_role_id")
        embed = discord.Embed(title="📡 Streaming Config", color=0x9333ea)
        ch   = interaction.guild.get_channel(cid) if cid else None
        role = interaction.guild.get_role(int(rid)) if rid else None
        embed.add_field(name="📢 Channel", value=ch.mention if ch else "Belum diset", inline=True)
        embed.add_field(name="🎭 Role",    value=role.mention if role else "Belum diset", inline=True)
        embed.add_field(name="🔴 Active",  value=str(len(self._active)), inline=True)
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

    @stream_group.command(name="test", description="Test kirim notif streaming (untuk testing)")
    @app_commands.checks.has_permissions(administrator=True)
    async def stream_test(self, interaction: discord.Interaction):
        cfg = await db.get_guild_config(interaction.guild.id)
        cid = cfg.get("streaming_channel_id")
        if not cid:
            await interaction.response.send_message("❌ Setup dulu dengan `/streaming setup`", ephemeral=True); return
        ch = interaction.guild.get_channel(int(cid))
        if not ch:
            await interaction.response.send_message("❌ Channel tidak ditemukan.", ephemeral=True); return
        fake_info = {
            "platform":  "YouTube",
            "title":     "🧪 Test Stream Notification",
            "url":       "https://youtube.com",
            "thumbnail": None,
        }
        embed = self._build_stream_embed(interaction.user, fake_info)
        await ch.send(content=f"🔴 {interaction.user.mention} sedang **LIVE!** *(test)*", embed=embed)
        await interaction.response.send_message("✅ Test notif terkirim!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Streaming(bot))
