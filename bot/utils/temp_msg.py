"""
utils/temp_msg.py — helper untuk kirim pesan yang auto-delete setelah N detik.
Digunakan sebagai pengganti ephemeral=True di semua cog.
"""
import asyncio
import discord


async def _delete_after(msg: discord.Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def temp_send(
    interaction: discord.Interaction,
    content: str = None,
    embed: discord.Embed = None,
    delay: int = 10,
):
    """
    Kirim pesan (bukan ephemeral) lalu hapus otomatis setelah `delay` detik.
    Bisa dipakai untuk interaction yang belum maupun sudah di-respond.
    """
    try:
        if interaction.response.is_done():
            msg = await interaction.followup.send(content=content, embed=embed, wait=True)
        else:
            await interaction.response.send_message(content=content, embed=embed)
            msg = await interaction.original_response()
        asyncio.create_task(_delete_after(msg, delay))
    except Exception as e:
        print(f"[temp_send] error: {e}", flush=True)
