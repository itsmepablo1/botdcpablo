import discord
from discord import app_commands
from discord.ext import commands
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db
from bot.utils.card_generator import generate_welcome_card, generate_leave_card
from bot.config import BACKGROUNDS_PATH

def _resolve_message(template: str, member: discord.Member) -> str:
    return (
        template
        .replace("{member}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count))
        .replace("{tag}", str(member))
    )

class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Events ───────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await db.get_guild_config(member.guild.id)
        ch_id = cfg.get("welcome_channel_id")
        if not ch_id:
            return
        channel = member.guild.get_channel(ch_id)
        if not channel:
            return
        msg  = _resolve_message(cfg.get("welcome_message", "Selamat datang {member} di {server}!"), member)
        bg   = cfg.get("welcome_background")
        card = await generate_welcome_card(member, bg, msg)
        embed = discord.Embed(
            description=f"🎉 **{member.mention}** bergabung ke **{member.guild.name}**!\nMember ke-**{member.guild.member_count}**",
            color=0x9333ea
        )
        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed, file=card)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = await db.get_guild_config(member.guild.id)
        ch_id = cfg.get("leave_channel_id")
        if not ch_id:
            return
        channel = member.guild.get_channel(ch_id)
        if not channel:
            return
        msg  = _resolve_message(cfg.get("leave_message", "{member} telah meninggalkan {server}."), member)
        bg   = cfg.get("leave_background")
        card = await generate_leave_card(member, bg, msg)
        embed = discord.Embed(
            description=f"👋 **{member.display_name}** telah meninggalkan server.",
            color=0xef4444
        )
        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed, file=card)

    # ── Slash Commands ────────────────────────────────────────────────────────

    welcome_group = app_commands.Group(name="welcome", description="Konfigurasi welcome/leave message")

    @welcome_group.command(name="channel", description="Set channel untuk welcome message menggunakan Channel ID")
    @app_commands.describe(channel_id="Channel ID untuk pesan welcome")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_channel(self, interaction: discord.Interaction, channel_id: str):
        try:
            cid = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID harus berupa angka!", ephemeral=True)
            return
        channel = interaction.guild.get_channel(cid)
        if not channel:
            await interaction.response.send_message(f"❌ Channel dengan ID `{cid}` tidak ditemukan di server ini.", ephemeral=True)
            return
        await db.set_guild_config(interaction.guild.id, welcome_channel_id=cid)
        await interaction.response.send_message(
            f"✅ Welcome channel diset ke {channel.mention} (`{cid}`)", ephemeral=True
        )

    @welcome_group.command(name="message", description="Set teks welcome. Gunakan {member}, {server}, {count}")
    @app_commands.describe(text="Teks pesan welcome")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_message(self, interaction: discord.Interaction, text: str):
        await db.set_guild_config(interaction.guild.id, welcome_message=text)
        await interaction.response.send_message(f"✅ Welcome message diset:\n> {text}", ephemeral=True)

    @welcome_group.command(name="background", description="Upload gambar background untuk welcome card")
    @app_commands.describe(file="File gambar (JPG/PNG, maks 8MB)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_bg(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not file.content_type or not file.content_type.startswith("image/"):
            await interaction.followup.send("❌ File harus berupa gambar!", ephemeral=True)
            return
        os.makedirs(BACKGROUNDS_PATH, exist_ok=True)
        path = os.path.join(BACKGROUNDS_PATH, f"welcome_{interaction.guild.id}.png")
        await file.save(path)
        await db.set_guild_config(interaction.guild.id, welcome_background=path)
        await interaction.followup.send(f"✅ Background welcome berhasil diupload!", ephemeral=True)

    @welcome_group.command(name="bgremove", description="Hapus background custom (kembali ke default)")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_welcome_bg(self, interaction: discord.Interaction):
        await db.set_guild_config(interaction.guild.id, welcome_background=None)
        await interaction.response.send_message("✅ Background welcome direset ke default.", ephemeral=True)

    leave_group = app_commands.Group(name="leave", description="Konfigurasi leave message")

    @leave_group.command(name="channel", description="Set channel untuk leave message menggunakan Channel ID")
    @app_commands.describe(channel_id="Channel ID untuk pesan leave")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_leave_channel(self, interaction: discord.Interaction, channel_id: str):
        try:
            cid = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID harus berupa angka!", ephemeral=True)
            return
        channel = interaction.guild.get_channel(cid)
        if not channel:
            await interaction.response.send_message(f"❌ Channel dengan ID `{cid}` tidak ditemukan.", ephemeral=True)
            return
        await db.set_guild_config(interaction.guild.id, leave_channel_id=cid)
        await interaction.response.send_message(
            f"✅ Leave channel diset ke {channel.mention} (`{cid}`)", ephemeral=True
        )

    @leave_group.command(name="message", description="Set teks leave. Gunakan {member}, {server}")
    @app_commands.describe(text="Teks pesan leave")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_leave_message(self, interaction: discord.Interaction, text: str):
        await db.set_guild_config(interaction.guild.id, leave_message=text)
        await interaction.response.send_message(f"✅ Leave message diset:\n> {text}", ephemeral=True)

    @leave_group.command(name="background", description="Upload background untuk leave card")
    @app_commands.describe(file="File gambar (JPG/PNG)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_leave_bg(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not file.content_type or not file.content_type.startswith("image/"):
            await interaction.followup.send("❌ File harus berupa gambar!", ephemeral=True)
            return
        os.makedirs(BACKGROUNDS_PATH, exist_ok=True)
        path = os.path.join(BACKGROUNDS_PATH, f"leave_{interaction.guild.id}.png")
        await file.save(path)
        await db.set_guild_config(interaction.guild.id, leave_background=path)
        await interaction.followup.send("✅ Background leave berhasil diupload!", ephemeral=True)

    @welcome_group.command(name="test", description="Test kirim welcome card sekarang")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_welcome(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cfg  = await db.get_guild_config(interaction.guild.id)
        msg  = _resolve_message(cfg.get("welcome_message", "Selamat datang {member}!"), interaction.user)
        card = await generate_welcome_card(interaction.user, cfg.get("welcome_background"), msg)
        await interaction.followup.send("Preview welcome card:", file=card, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
