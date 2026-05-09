import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Tampilkan semua command yang tersedia")
    async def help(self, interaction: discord.Interaction):
        embeds = self._build_help_embeds(interaction)
        await interaction.response.send_message(embeds=embeds, ephemeral=False)

    def _build_help_embeds(self, interaction: discord.Interaction) -> list[discord.Embed]:
        bot = self.bot

        # ── Embed 1: Header ────────────────────────────────────────────────────
        header = discord.Embed(
            title="📖  Daftar Command Bot",
            description=(
                "Halo! Berikut semua command yang tersedia.\n"
                "Gunakan `/` untuk memunculkan command di Discord.\n\n"
                "🔒 = Hanya Admin  •  🌐 = Semua Member"
            ),
            color=0x9333ea,
        )
        header.set_thumbnail(url=bot.user.display_avatar.url if bot.user else discord.embeds.EmptyEmbed)
        header.set_author(
            name="Bot by Pablo",
            icon_url=bot.user.display_avatar.url if bot.user else discord.embeds.EmptyEmbed,
        )

        # ── Embed 2: 🎵 Musik ─────────────────────────────────────────────────
        music = discord.Embed(title="🎵  Musik — YouTube Player", color=0x9333ea)
        music.add_field(
            name="🌐 `/play <lagu>`",
            value="Putar lagu dari YouTube. Bisa URL atau kata kunci pencarian.\nSupport single video & playlist.",
            inline=False,
        )
        music.add_field(name="🌐 `/skip`",       value="Skip lagu yang sedang diputar.",           inline=True)
        music.add_field(name="🌐 `/stop`",       value="Hentikan musik & bot keluar dari voice.",  inline=True)
        music.add_field(name="🌐 `/pause`",      value="Pause musik.",                             inline=True)
        music.add_field(name="🌐 `/resume`",     value="Lanjutkan musik yang di-pause.",           inline=True)
        music.add_field(name="🌐 `/queue`",      value="Lihat daftar antrian lagu.",               inline=True)
        music.add_field(name="🌐 `/nowplaying`", value="Tampilkan lagu yang sedang diputar.",      inline=True)
        music.add_field(name="🌐 `/volume <0-100>`", value="Atur volume musik.",                   inline=True)

        # ── Embed 3: 🔊 Auto Voice ────────────────────────────────────────────
        voice = discord.Embed(title="🔊  Auto Voice Channel", color=0x7c3aed)
        voice.add_field(
            name="🔒 `/setupvoice create`",
            value="Buat kategori + hub voice channel otomatis.\nMember join hub → bot buat VC baru untuk mereka.",
            inline=False,
        )
        voice.add_field(name="🔒 `/setupvoice remove`", value="Matikan Auto Voice.",             inline=True)
        voice.add_field(name="🔒 `/setupvoice info`",   value="Lihat konfigurasi Auto Voice.",   inline=True)
        voice.add_field(name="🔒 `/autovoice setup <channel_id>`", value="Set hub channel secara manual.", inline=False)
        voice.add_field(name="🔒 `/autovoice disable`", value="Matikan Auto Voice.",             inline=True)
        voice.add_field(name="", value="**Kelola VC milik kamu:**", inline=False)
        voice.add_field(name="🌐 `/vc name <nama>`",  value="Ganti nama VC kamu.",               inline=True)
        voice.add_field(name="🌐 `/vc limit <0-99>`", value="Set batas member.",                 inline=True)
        voice.add_field(name="🌐 `/vc lock`",         value="Kunci VC kamu.",                    inline=True)
        voice.add_field(name="🌐 `/vc unlock`",       value="Buka kunci VC.",                    inline=True)
        voice.add_field(name="🌐 `/vc kick <user_id>`", value="Kick member dari VC.",            inline=True)
        voice.add_field(name="🌐 `/vc claim`",         value="Ambil ownership VC.",              inline=True)
        voice.add_field(name="🌐 `/vc info`",          value="Lihat info VC kamu.",              inline=True)

        # ── Embed 4: 👋 Welcome / Leave ───────────────────────────────────────
        welcome = discord.Embed(title="👋  Welcome & Leave System", color=0x059669)
        welcome.add_field(
            name="🔒 `/welcome channel <channel_id>`",
            value="Set channel untuk pesan welcome.",
            inline=False,
        )
        welcome.add_field(
            name="🔒 `/welcome message <teks>`",
            value="Set pesan welcome. Variabel: `{member}` `{server}` `{count}` `{tag}`",
            inline=False,
        )
        welcome.add_field(name="🔒 `/welcome background`", value="Upload gambar background welcome card.", inline=True)
        welcome.add_field(name="🔒 `/welcome bgremove`",   value="Hapus background custom.",              inline=True)
        welcome.add_field(name="🔒 `/welcome test`",       value="Preview welcome card sekarang.",        inline=True)
        welcome.add_field(name="🔒 `/leave channel <channel_id>`",  value="Set channel leave message.", inline=False)
        welcome.add_field(name="🔒 `/leave message <teks>`",        value="Set teks leave message.",    inline=True)
        welcome.add_field(name="🔒 `/leave background`",            value="Upload background leave card.", inline=True)

        # ── Embed 5: 🎭 Role Selector ─────────────────────────────────────────
        roles = discord.Embed(title="🎭  Role Selector Panel", color=0xd97706)
        roles.add_field(
            name="🔒 `/roles create <channel_id>`",
            value="Buat panel role baru di sebuah channel.",
            inline=False,
        )
        roles.add_field(
            name="🔒 `/roles addgroup <panel_id> <nama>`",
            value="Tambah grup/kategori role ke panel.",
            inline=False,
        )
        roles.add_field(
            name="🔒 `/roles add <group_id> <role_id>`",
            value="Tambah role ke grup. Bisa tambah emoji & deskripsi.",
            inline=False,
        )
        roles.add_field(name="🔒 `/roles post <panel_id>`",   value="Kirim panel role ke channel.",    inline=True)
        roles.add_field(name="🔒 `/roles list`",              value="Lihat semua panel role.",         inline=True)
        roles.add_field(name="🔒 `/roles delete <panel_id>`", value="Hapus panel role.",               inline=True)

        # ── Embed 6: 📊 Status Channel ────────────────────────────────────────
        status = discord.Embed(title="📊  Status Channel", color=0x0ea5e9)
        status.add_field(
            name="🔒 `/status setup`",
            value="Buat kategori + channel statistik server otomatis.\n(Total Member & Online Member)",
            inline=False,
        )
        status.add_field(name="🔒 `/status setmember <channel_id>`", value="Set channel Total Member secara manual.",  inline=False)
        status.add_field(name="🔒 `/status setonline <channel_id>`", value="Set channel Total Online secara manual.",  inline=True)
        status.add_field(name="🔒 `/status refresh`",                value="Paksa update status sekarang.",            inline=True)
        status.add_field(name="🔒 `/status disable`",                value="Hapus & nonaktifkan status channel.",      inline=True)

        # ── Embed 7: 📡 Streaming Notif ───────────────────────────────────────
        streaming = discord.Embed(title="📡  Streaming Notification", color=0xef4444)
        streaming.add_field(
            name="🔒 `/streaming setup <channel_id> <role_id>`",
            value=(
                "Setup notifikasi streaming.\n"
                "Member dengan role tersebut yang mulai streaming (Twitch/YouTube/TikTok) "
                "lewat Discord akan otomatis dinotifikasi."
            ),
            inline=False,
        )
        streaming.add_field(name="🔒 `/streaming info`",    value="Lihat konfigurasi streaming.",     inline=True)
        streaming.add_field(name="🔒 `/streaming disable`", value="Matikan notifikasi streaming.",    inline=True)
        streaming.add_field(name="🔒 `/streaming test`",    value="Test kirim notif streaming.",      inline=True)

        # ── Embed 8: Footer ───────────────────────────────────────────────────
        footer = discord.Embed(
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💜  **Bot Discord** — Dibuat dengan ❤️ oleh **Pablo**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔒 = Butuh permission **Administrator**\n"
                "🌐 = Bisa digunakan semua member"
            ),
            color=0x9333ea,
        )
        footer.set_footer(
            text="© Pablo • Bot DC | Gunakan /help untuk melihat panduan ini kapan saja",
            icon_url=bot.user.display_avatar.url if bot.user else discord.embeds.EmptyEmbed,
        )

        return [header, music, voice, welcome, roles, status, streaming, footer]


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
