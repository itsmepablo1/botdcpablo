import discord
from discord import app_commands
from discord.ext import commands
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import database as db

# ── Persistent Role Dropdown View ─────────────────────────────────────────────

class RoleSelectMenu(discord.ui.Select):
    def __init__(self, group_name: str, options: list[dict], guild: discord.Guild):
        self.guild_ref = guild
        items = []
        for opt in options[:25]:
            role = guild.get_role(opt["role_id"])
            if not role:
                continue
            items.append(
                discord.SelectOption(
                    label=role.name,
                    value=str(opt["role_id"]),
                    emoji=opt.get("emoji") or None,
                    description=(opt.get("description") or "")[:100],
                )
            )
        super().__init__(
            placeholder=f"📋 {group_name} — Pilih role...",
            min_values=0,
            max_values=len(items) if items else 1,
            options=items or [discord.SelectOption(label="Kosong", value="0")],
            custom_id=f"rolesel_{group_name[:50]}",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        guild  = interaction.guild

        # Collect all role_ids from this select's options
        all_role_ids = {int(o.value) for o in self.options if o.value != "0"}
        chosen_ids   = {int(v) for v in self.values}

        to_add    = [guild.get_role(rid) for rid in chosen_ids   if guild.get_role(rid)]
        to_remove = [guild.get_role(rid) for rid in all_role_ids - chosen_ids if guild.get_role(rid)]

        try:
            if to_add:    await member.add_roles(*to_add, reason="Role selector")
            if to_remove: await member.remove_roles(*to_remove, reason="Role selector")
            names = ", ".join(r.name for r in to_add) if to_add else "—"
            await interaction.followup.send(
                f"✅ Role diupdate!\n➕ Ditambah: **{names}**",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot tidak punya izin untuk mengelola role ini.", ephemeral=True)


class RolePanelView(discord.ui.View):
    def __init__(self, groups_data: list[dict], guild: discord.Guild):
        super().__init__(timeout=None)
        for g in groups_data:
            if g.get("options"):
                self.add_item(RoleSelectMenu(g["name"], g["options"], guild))


# ── Roles Cog ─────────────────────────────────────────────────────────────────

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Recreate persistent views once bot is ready."""
        for guild in self.bot.guilds:
            await self._restore_panels(guild)

    async def _restore_panels(self, guild: discord.Guild):
        panels = await db.get_role_panels(guild.id)
        for panel in panels:
            if not panel.get("message_id"):
                continue
            groups_data = await self._build_groups_data(panel["id"])
            view = RolePanelView(groups_data, guild)
            self.bot.add_view(view, message_id=panel["message_id"])

    async def _build_groups_data(self, panel_id: int) -> list[dict]:
        groups = await db.get_role_groups(panel_id)
        result = []
        for g in groups:
            opts = await db.get_role_options(g["id"])
            result.append({"name": g["name"], "options": opts})
        return result

    # ── Commands ─────────────────────────────────────────────────────────────

    roles_group = app_commands.Group(name="roles", description="Kelola panel role selector")

    @roles_group.command(name="create", description="Buat panel role baru di sebuah channel")
    @app_commands.describe(
        channel_id="Channel ID tempat panel role dikirim",
        title="Judul panel",
        description="Deskripsi panel"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_create(
        self,
        interaction: discord.Interaction,
        channel_id: str,
        title: str = "🎭 Pilih Role Kamu",
        description: str = "Pilih satu atau lebih role menggunakan dropdown di bawah."
    ):
        try:
            cid = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Channel ID harus angka!", ephemeral=True)
            return
        channel = interaction.guild.get_channel(cid)
        if not channel:
            await interaction.response.send_message(f"❌ Channel `{cid}` tidak ditemukan.", ephemeral=True)
            return
        panel_id = await db.create_role_panel(interaction.guild.id, cid, title, description)
        await interaction.response.send_message(
            f"✅ Panel role dibuat! ID Panel: `{panel_id}`\n"
            f"Sekarang tambahkan grup dengan `/roles addgroup {panel_id} <nama>`",
            ephemeral=True
        )

    @roles_group.command(name="addgroup", description="Tambah grup/kategori role ke panel")
    @app_commands.describe(
        panel_id="ID panel (dari /roles create)",
        name="Nama grup (contoh: 'Game', 'Hobby')"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_addgroup(self, interaction: discord.Interaction, panel_id: int, name: str):
        panels = await db.get_role_panels(interaction.guild.id)
        if not any(p["id"] == panel_id for p in panels):
            await interaction.response.send_message("❌ Panel ID tidak valid untuk server ini.", ephemeral=True)
            return
        group_id = await db.create_role_group(panel_id, name)
        await interaction.response.send_message(
            f"✅ Grup **{name}** dibuat! ID Grup: `{group_id}`\n"
            f"Tambahkan role dengan `/roles add {group_id} <role_id>`",
            ephemeral=True
        )

    @roles_group.command(name="add", description="Tambah role ke sebuah grup menggunakan Role ID")
    @app_commands.describe(
        group_id="ID grup (dari /roles addgroup)",
        role_id="Role ID yang ingin ditambahkan",
        emoji="Emoji untuk role ini (opsional)",
        description="Deskripsi singkat role (opsional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_add(
        self,
        interaction: discord.Interaction,
        group_id: int,
        role_id: str,
        emoji: str = "",
        description: str = ""
    ):
        try:
            rid = int(role_id)
        except ValueError:
            await interaction.response.send_message("❌ Role ID harus angka!", ephemeral=True)
            return
        role = interaction.guild.get_role(rid)
        if not role:
            await interaction.response.send_message(f"❌ Role dengan ID `{rid}` tidak ditemukan.", ephemeral=True)
            return
        await db.add_role_option(group_id, rid, emoji or None, description or None)
        await interaction.response.send_message(
            f"✅ Role **{role.name}** (`{rid}`) ditambahkan ke grup!", ephemeral=True
        )

    @roles_group.command(name="post", description="Kirim/update panel role ke channel")
    @app_commands.describe(panel_id="ID panel yang ingin dikirim")
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_post(self, interaction: discord.Interaction, panel_id: int):
        await interaction.response.defer(ephemeral=True)
        panels = await db.get_role_panels(interaction.guild.id)
        panel  = next((p for p in panels if p["id"] == panel_id), None)
        if not panel:
            await interaction.followup.send("❌ Panel ID tidak valid.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(panel["channel_id"])
        if not channel:
            await interaction.followup.send("❌ Channel tidak ditemukan.", ephemeral=True)
            return

        groups_data = await self._build_groups_data(panel_id)
        view  = RolePanelView(groups_data, interaction.guild)
        embed = discord.Embed(
            title=panel["title"],
            description=panel["description"],
            color=0x9333ea
        )
        embed.set_footer(text="Pilih role dengan dropdown di bawah. Pilih ulang untuk melepas.")

        # Delete old message if exists
        if panel.get("message_id"):
            try:
                old_msg = await channel.fetch_message(panel["message_id"])
                await old_msg.delete()
            except Exception:
                pass

        msg = await channel.send(embed=embed, view=view)
        await db.update_panel_message_id(panel_id, msg.id)
        self.bot.add_view(view, message_id=msg.id)
        await interaction.followup.send(f"✅ Panel role dikirim ke {channel.mention}!", ephemeral=True)

    @roles_group.command(name="list", description="Lihat semua panel role di server ini")
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_list(self, interaction: discord.Interaction):
        panels = await db.get_role_panels(interaction.guild.id)
        if not panels:
            await interaction.response.send_message("❌ Tidak ada panel role.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 Daftar Role Panel", color=0x9333ea)
        for p in panels:
            ch = interaction.guild.get_channel(p["channel_id"])
            embed.add_field(
                name=f"Panel #{p['id']}: {p['title']}",
                value=f"Channel: {ch.mention if ch else p['channel_id']}\nMessage ID: `{p.get('message_id','Belum dikirim')}`",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @roles_group.command(name="delete", description="Hapus panel role")
    @app_commands.describe(panel_id="ID panel yang ingin dihapus")
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_delete(self, interaction: discord.Interaction, panel_id: int):
        panels = await db.get_role_panels(interaction.guild.id)
        panel  = next((p for p in panels if p["id"] == panel_id), None)
        if not panel:
            await interaction.response.send_message("❌ Panel tidak ditemukan.", ephemeral=True)
            return
        # Delete the message if possible
        if panel.get("message_id"):
            ch = interaction.guild.get_channel(panel["channel_id"])
            if ch:
                try:
                    msg = await ch.fetch_message(panel["message_id"])
                    await msg.delete()
                except Exception:
                    pass
        await db.delete_role_panel(panel_id)
        await interaction.response.send_message(f"✅ Panel `{panel_id}` dihapus.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
