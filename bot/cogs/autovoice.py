import discord
from discord import app_commands
from discord.ext import commands
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db

class AutoVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild  = member.guild
        cfg    = await db.get_guild_config(guild.id)
        hub_id = cfg.get("autovoice_channel_id")

        if after.channel and after.channel.id == hub_id:
            category = after.channel.category
            new_ch = await guild.create_voice_channel(
                name=f"🔊 {member.display_name}", category=category, reason="Auto VC"
            )
            await db.add_auto_voice(new_ch.id, guild.id, member.id, new_ch.name)
            await member.move_to(new_ch)

        if before.channel and before.channel.id != hub_id:
            row = await db.get_auto_voice(before.channel.id)
            if row and len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Auto VC — empty")
                except discord.NotFound:
                    pass
                await db.remove_auto_voice(before.channel.id)

    vc_group = app_commands.Group(name="autovoice", description="Konfigurasi Auto Voice Channel")

    @vc_group.command(name="setup", description="Set trigger channel untuk Auto Voice (gunakan Channel ID)")
    @app_commands.describe(channel_id="Channel ID voice yang jadi trigger")
    @app_commands.checks.has_permissions(administrator=True)
    async def av_setup(self, interaction: discord.Interaction, channel_id: str):
        try:
            cid = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID harus angka!", ephemeral=True)
            return
        ch = interaction.guild.get_channel(cid)
        if not ch or not isinstance(ch, discord.VoiceChannel):
            await interaction.response.send_message(f"❌ Voice channel `{cid}` tidak ditemukan.", ephemeral=True)
            return
        await db.set_guild_config(interaction.guild.id, autovoice_channel_id=cid)
        await interaction.response.send_message(
            f"✅ Auto Voice aktif! Join {ch.mention} untuk buat VC baru.", ephemeral=True
        )

    @vc_group.command(name="disable", description="Matikan Auto Voice Channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def av_disable(self, interaction: discord.Interaction):
        await db.set_guild_config(interaction.guild.id, autovoice_channel_id=None)
        await interaction.response.send_message("✅ Auto Voice dimatikan.", ephemeral=True)

    vc_ctrl = app_commands.Group(name="vc", description="Kelola voice channel otomatis kamu")

    async def _get_owned_vc(self, interaction):
        member = interaction.user
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message("❌ Kamu harus di voice channel!", ephemeral=True)
            return None, None
        ch  = member.voice.channel
        row = await db.get_auto_voice(ch.id)
        if not row:
            await interaction.response.send_message("❌ Ini bukan Auto Voice Channel.", ephemeral=True)
            return None, None
        if row["owner_id"] != member.id:
            await interaction.response.send_message("❌ Kamu bukan pemilik channel ini.", ephemeral=True)
            return None, None
        return ch, row

    @vc_ctrl.command(name="name", description="Ganti nama voice channel kamu")
    @app_commands.describe(name="Nama baru")
    async def vc_name(self, interaction: discord.Interaction, name: str):
        ch, _ = await self._get_owned_vc(interaction)
        if not ch: return
        await ch.edit(name=name)
        await db.update_auto_voice(ch.id, name=name)
        await interaction.response.send_message(f"✅ Channel dinamai **{name}**", ephemeral=True)

    @vc_ctrl.command(name="limit", description="Set batas member (0 = unlimited)")
    @app_commands.describe(limit="0-99")
    async def vc_limit(self, interaction: discord.Interaction, limit: int):
        if not 0 <= limit <= 99:
            await interaction.response.send_message("❌ Limit 0-99.", ephemeral=True); return
        ch, _ = await self._get_owned_vc(interaction)
        if not ch: return
        await ch.edit(user_limit=limit)
        await db.update_auto_voice(ch.id, user_limit=limit)
        await interaction.response.send_message(f"✅ Limit: **{limit or 'Unlimited'}**", ephemeral=True)

    @vc_ctrl.command(name="lock", description="Kunci channel")
    async def vc_lock(self, interaction: discord.Interaction):
        ch, _ = await self._get_owned_vc(interaction)
        if not ch: return
        ow = ch.overwrites_for(interaction.guild.default_role)
        ow.connect = False
        await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
        await db.update_auto_voice(ch.id, is_locked=1)
        await interaction.response.send_message("🔒 Channel dikunci!", ephemeral=True)

    @vc_ctrl.command(name="unlock", description="Buka channel")
    async def vc_unlock(self, interaction: discord.Interaction):
        ch, _ = await self._get_owned_vc(interaction)
        if not ch: return
        ow = ch.overwrites_for(interaction.guild.default_role)
        ow.connect = None
        await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
        await db.update_auto_voice(ch.id, is_locked=0)
        await interaction.response.send_message("🔓 Channel dibuka!", ephemeral=True)

    @vc_ctrl.command(name="kick", description="Kick member dari VC (gunakan User ID)")
    @app_commands.describe(user_id="User ID member")
    async def vc_kick(self, interaction: discord.Interaction, user_id: str):
        ch, _ = await self._get_owned_vc(interaction)
        if not ch: return
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ User ID harus angka!", ephemeral=True); return
        target = interaction.guild.get_member(uid)
        if not target or not target.voice or target.voice.channel != ch:
            await interaction.response.send_message("❌ Member tidak ada di channel kamu.", ephemeral=True); return
        await target.move_to(None)
        await interaction.response.send_message(f"✅ **{target.display_name}** dikick.", ephemeral=True)

    @vc_ctrl.command(name="claim", description="Ambil ownership jika owner sudah keluar")
    async def vc_claim(self, interaction: discord.Interaction):
        member = interaction.user
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message("❌ Kamu harus di VC!", ephemeral=True); return
        ch  = member.voice.channel
        row = await db.get_auto_voice(ch.id)
        if not row:
            await interaction.response.send_message("❌ Bukan Auto VC.", ephemeral=True); return
        owner = interaction.guild.get_member(row["owner_id"])
        if owner and owner.voice and owner.voice.channel == ch:
            await interaction.response.send_message("❌ Owner masih di channel.", ephemeral=True); return
        await db.update_auto_voice(ch.id, owner_id=member.id)
        await interaction.response.send_message("✅ Kamu sekarang owner channel ini!", ephemeral=True)

    @vc_ctrl.command(name="info", description="Lihat info VC kamu")
    async def vc_info(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Kamu harus di VC!", ephemeral=True); return
        ch  = interaction.user.voice.channel
        row = await db.get_auto_voice(ch.id)
        if not row:
            await interaction.response.send_message("❌ Bukan Auto VC.", ephemeral=True); return
        owner = interaction.guild.get_member(row["owner_id"])
        embed = discord.Embed(title=f"🔊 {ch.name}", color=0x9333ea)
        embed.add_field(name="👑 Owner",  value=owner.mention if owner else str(row["owner_id"]), inline=True)
        embed.add_field(name="👥 Member", value=f"{len(ch.members)}/{ch.user_limit or '∞'}", inline=True)
        embed.add_field(name="🔒 Status", value="Terkunci" if row["is_locked"] else "Terbuka", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoVoice(bot))
