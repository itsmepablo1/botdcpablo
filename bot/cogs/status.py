import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db

def _count_online(guild: discord.Guild) -> int:
    return sum(
        1 for m in guild.members
        if m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd)
        and not m.bot
    )

class Status(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot          = bot
        self._pending: set[int] = set()   # guild IDs waiting for update
        self.status_updater.start()

    def cog_unload(self):
        self.status_updater.cancel()

    # ── Background Task: update every 5 min or on demand ─────────────────────

    @tasks.loop(minutes=5)
    async def status_updater(self):
        for guild in self.bot.guilds:
            await self._update_status(guild)

    @status_updater.before_loop
    async def before_updater(self):
        await self.bot.wait_until_ready()

    async def _update_status(self, guild: discord.Guild):
        cfg = await db.get_guild_config(guild.id)
        member_ch_id = cfg.get("status_member_channel_id")
        online_ch_id = cfg.get("status_online_channel_id")

        total   = guild.member_count or 0
        online  = _count_online(guild)

        if member_ch_id:
            ch = guild.get_channel(member_ch_id)
            if ch:
                new_name = f"👥 Total Member: {total:,}"
                if ch.name != new_name:
                    try:
                        await ch.edit(name=new_name)
                    except discord.HTTPException:
                        pass

        if online_ch_id:
            ch = guild.get_channel(online_ch_id)
            if ch:
                new_name = f"🟢 Online: {online:,}"
                if ch.name != new_name:
                    try:
                        await ch.edit(name=new_name)
                    except discord.HTTPException:
                        pass

    # ── Events that trigger update ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._update_status(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._update_status(member.guild)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        # Only update if online status changed
        if before.status != after.status:
            await self._update_status(after.guild)

    # ── Slash Commands ────────────────────────────────────────────────────────

    status_group = app_commands.Group(name="status", description="Konfigurasi status channel server")

    @status_group.command(name="setup", description="Buat kategori + channel statistik server otomatis")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # Create category
        category = await guild.create_category("📊 Server Stats")

        # Deny @everyone from sending messages / connecting
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                connect=False, send_messages=False, view_channel=True
            )
        }

        member_ch = await guild.create_voice_channel(
            "👥 Total Member: 0", category=category, overwrites=overwrites
        )
        online_ch = await guild.create_voice_channel(
            "🟢 Online: 0", category=category, overwrites=overwrites
        )

        await db.set_guild_config(
            guild.id,
            status_member_channel_id=member_ch.id,
            status_online_channel_id=online_ch.id,
            status_category_id=category.id,
        )
        await self._update_status(guild)
        await interaction.followup.send(
            f"✅ Status channel dibuat di kategori **{category.name}**!\n"
            f"📊 Update otomatis setiap 5 menit atau saat ada perubahan member.",
            ephemeral=True
        )

    @status_group.command(name="setmember", description="Set channel untuk Total Member (Channel ID)")
    @app_commands.describe(channel_id="Channel ID (Voice Channel)")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_setmember(self, interaction: discord.Interaction, channel_id: str):
        try:
            cid = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID harus angka!", ephemeral=True); return
        ch = interaction.guild.get_channel(cid)
        if not ch:
            await interaction.response.send_message(f"❌ Channel `{cid}` tidak ditemukan.", ephemeral=True); return
        await db.set_guild_config(interaction.guild.id, status_member_channel_id=cid)
        await self._update_status(interaction.guild)
        await interaction.response.send_message(f"✅ Member counter diset ke {ch.mention}", ephemeral=True)

    @status_group.command(name="setonline", description="Set channel untuk Total Online (Channel ID)")
    @app_commands.describe(channel_id="Channel ID (Voice Channel)")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_setonline(self, interaction: discord.Interaction, channel_id: str):
        try:
            cid = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID harus angka!", ephemeral=True); return
        ch = interaction.guild.get_channel(cid)
        if not ch:
            await interaction.response.send_message(f"❌ Channel `{cid}` tidak ditemukan.", ephemeral=True); return
        await db.set_guild_config(interaction.guild.id, status_online_channel_id=cid)
        await self._update_status(interaction.guild)
        await interaction.response.send_message(f"✅ Online counter diset ke {ch.mention}", ephemeral=True)

    @status_group.command(name="refresh", description="Paksa update status channel sekarang")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_refresh(self, interaction: discord.Interaction):
        await self._update_status(interaction.guild)
        await interaction.response.send_message("✅ Status channel direfresh!", ephemeral=True)

    @status_group.command(name="disable", description="Hapus status channel yang dibuat bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_disable(self, interaction: discord.Interaction):
        cfg = await db.get_guild_config(interaction.guild.id)
        for key in ("status_member_channel_id", "status_online_channel_id", "status_category_id"):
            cid = cfg.get(key)
            if cid:
                ch = interaction.guild.get_channel(cid)
                if ch:
                    try:
                        await ch.delete()
                    except Exception:
                        pass
        await db.set_guild_config(
            interaction.guild.id,
            status_member_channel_id=None,
            status_online_channel_id=None,
            status_category_id=None,
        )
        await interaction.response.send_message("✅ Status channel dinonaktifkan.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
