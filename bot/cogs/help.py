import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Tampilkan semua command yang tersedia")
    async def help(self, interaction: discord.Interaction):
        # Defer dulu agar Discord tidak timeout "application did not respond"
        await interaction.response.defer()

        bot = self.bot
        avatar_url = bot.user.display_avatar.url if bot.user else None

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
        if avatar_url:
            header.set_thumbnail(url=avatar_url)
            header.set_author(name="Bot by Pablo", icon_url=avatar_url)
        else:
            header.set_author(name="Bot by Pablo")

        # ── Embed 2: 🎵 Musik ─────────────────────────────────────────────────
        music = discord.Embed(title="🎵  Musik — YouTube Player", color=0x9333ea)
        music.add_field(name="🌐 `/play <lagu>`",    value="Putar dari YouTube (URL/kata kunci). Support playlist.", inline=False)
        music.add_field(name="🌐 `/skip`",            value="Skip lagu sekarang.",             inline=True)
        music.add_field(name="🌐 `/stop`",            value="Stop & keluar dari voice.",        inline=True)
        music.add_field(name="🌐 `/pause`",           value="Pause musik.",                     inline=True)
        music.add_field(name="🌐 `/resume`",          value="Lanjutkan musik.",                 inline=True)
        music.add_field(name="🌐 `/queue`",           value="Lihat antrian lagu.",              inline=True)
        music.add_field(name="🌐 `/nowplaying`",      value="Lagu yang sedang diputar.",        inline=True)
        music.add_field(name="🌐 `/volume <0-100>`",  value="Atur volume.",                     inline=True)

        # ── Embed 3: 🔊 Auto Voice ────────────────────────────────────────────
        voice = discord.Embed(title="🔊  Auto Voice Channel", color=0x7c3aed)
        voice.add_field(name="🔒 `/setupvoice create`",           value="Buat hub VC otomatis.",         inline=True)
        voice.add_field(name="🔒 `/setupvoice remove`",           value="Matikan Auto Voice.",            inline=True)
        voice.add_field(name="🔒 `/setupvoice info`",             value="Info konfigurasi.",             inline=True)
        voice.add_field(name="🔒 `/autovoice setup <ch_id>`",     value="Set hub manual.",               inline=True)
        voice.add_field(name="🔒 `/autovoice disable`",           value="Matikan Auto Voice.",            inline=True)
        voice.add_field(name="🌐 `/vc name <nama>`",              value="Ganti nama VC.",                inline=True)
        voice.add_field(name="🌐 `/vc limit <0-99>`",             value="Set batas member.",             inline=True)
        voice.add_field(name="🌐 `/vc lock` / `/vc unlock`",      value="Kunci/buka VC.",                inline=True)
        voice.add_field(name="🌐 `/vc kick <user_id>`",           value="Kick member dari VC.",          inline=True)
        voice.add_field(name="🌐 `/vc claim`",                    value="Ambil ownership VC.",           inline=True)
        voice.add_field(name="🌐 `/vc info`",                     value="Info VC kamu.",                 inline=True)

        # ── Embed 4: 👋 Welcome / Leave ───────────────────────────────────────
        welcome = discord.Embed(title="👋  Welcome & Leave", color=0x059669)
        welcome.add_field(name="🔒 `/welcome channel <ch_id>`",   value="Set channel welcome.",          inline=True)
        welcome.add_field(name="🔒 `/welcome message <teks>`",    value="Set teks welcome.\n`{member}` `{server}` `{count}`", inline=True)
        welcome.add_field(name="🔒 `/welcome background`",        value="Upload background card.",       inline=True)
        welcome.add_field(name="🔒 `/welcome bgremove`",          value="Hapus background.",             inline=True)
        welcome.add_field(name="🔒 `/welcome test`",              value="Preview welcome card.",         inline=True)
        welcome.add_field(name="🔒 `/leave channel <ch_id>`",     value="Set channel leave.",            inline=True)
        welcome.add_field(name="🔒 `/leave message <teks>`",      value="Set teks leave.",               inline=True)
        welcome.add_field(name="🔒 `/leave background`",          value="Upload background leave.",      inline=True)

        # Kirim batch pertama
        await interaction.followup.send(embeds=[header, music, voice, welcome])

        # ── Embed 5: 🎭 Role Selector ─────────────────────────────────────────
        roles = discord.Embed(title="🎭  Role Selector Panel", color=0xd97706)
        roles.add_field(name="🔒 `/roles create <ch_id>`",        value="Buat panel role baru.",         inline=True)
        roles.add_field(name="🔒 `/roles addgroup <id> <nama>`",  value="Tambah grup role.",             inline=True)
        roles.add_field(name="🔒 `/roles add <grp_id> <role_id>`",value="Tambah role ke grup.",          inline=True)
        roles.add_field(name="🔒 `/roles post <id>`",             value="Kirim panel ke channel.",       inline=True)
        roles.add_field(name="🔒 `/roles list`",                  value="Lihat semua panel.",            inline=True)
        roles.add_field(name="🔒 `/roles delete <id>`",           value="Hapus panel role.",             inline=True)

        # ── Embed 6: 📊 Status Channel ────────────────────────────────────────
        status = discord.Embed(title="📊  Status Channel", color=0x0ea5e9)
        status.add_field(name="🔒 `/status setup`",               value="Buat channel statistik otomatis.", inline=True)
        status.add_field(name="🔒 `/status setmember <ch_id>`",   value="Set channel total member.",    inline=True)
        status.add_field(name="🔒 `/status setonline <ch_id>`",   value="Set channel total online.",    inline=True)
        status.add_field(name="🔒 `/status refresh`",             value="Paksa update sekarang.",        inline=True)
        status.add_field(name="🔒 `/status disable`",             value="Nonaktifkan status channel.",   inline=True)

        # ── Embed 7: 📡 Streaming Notif ───────────────────────────────────────
        streaming = discord.Embed(title="📡  Streaming Notification", color=0xef4444)
        streaming.add_field(
            name="🔒 `/streaming setup <ch_id> <role_id>`",
            value="Setup notif streaming otomatis (Twitch/YouTube/TikTok).",
            inline=False,
        )
        streaming.add_field(name="🔒 `/streaming info`",          value="Lihat konfigurasi.",            inline=True)
        streaming.add_field(name="🔒 `/streaming disable`",       value="Matikan notifikasi.",           inline=True)
        streaming.add_field(name="🔒 `/streaming test`",          value="Test kirim notif.",             inline=True)

        # ── Embed 8: Footer ───────────────────────────────────────────────────
        footer = discord.Embed(
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💜  Dibuat dengan ❤️ oleh **Pablo**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔒 Butuh permission **Administrator**\n"
                "🌐 Bisa digunakan semua member"
            ),
            color=0x9333ea,
        )
        if avatar_url:
            footer.set_footer(
                text="© Pablo • Bot DC | /help untuk melihat panduan ini kapan saja",
                icon_url=avatar_url,
            )
        else:
            footer.set_footer(text="© Pablo • Bot DC | /help untuk melihat panduan ini kapan saja")

        # Kirim batch kedua
        await interaction.followup.send(embeds=[roles, status, streaming, footer])


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
