import asyncio
import io
import os
import aiohttp
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import discord

FONT_PATH = Path(__file__).parent.parent.parent / "assets" / "fonts"

def _get_font(size: int):
    """Try to load a bundled or system font, fallback to default."""
    candidates = [
        FONT_PATH / "NotoSans-Bold.ttf",
        FONT_PATH / "Roboto-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),  # Linux
        Path("C:/Windows/Fonts/arialbd.ttf"),  # Windows
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()

def _get_font_regular(size: int):
    candidates = [
        FONT_PATH / "NotoSans-Regular.ttf",
        FONT_PATH / "Roboto-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()

def _make_circle_avatar(avatar_bytes: bytes, size: int = 128) -> Image.Image:
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    avatar.putalpha(mask)
    return avatar

def _make_gradient_bg(width: int, height: int, color1=(30,15,60), color2=(10,40,80)) -> Image.Image:
    """Generate a diagonal gradient background."""
    base = Image.new("RGB", (width, height), color1)
    top  = Image.new("RGB", (width, height), color2)
    mask = Image.new("L", (width, height))
    for y in range(height):
        for x in range(width):
            val = int(255 * ((x + y) / (width + height)))
            mask.putpixel((x, y), val)
    base.paste(top, mask=mask)
    return base

async def _fetch_avatar(user: discord.Member) -> bytes:
    url = user.display_avatar.replace(size=256, format="png").url
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.read()

async def generate_welcome_card(
    member: discord.Member,
    background_path: str | None,
    message: str,
) -> discord.File:
    W, H = 900, 300

    # ── Background ──────────────────────────────────────────────────────────
    if background_path and os.path.exists(background_path):
        bg = Image.open(background_path).convert("RGB").resize((W, H))
    else:
        bg = _make_gradient_bg(W, H, (30, 12, 60), (8, 35, 80))

    # Dark overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 140))
    bg = bg.convert("RGBA")
    bg.paste(overlay, mask=overlay)

    # ── Avatar ───────────────────────────────────────────────────────────────
    avatar_bytes = await _fetch_avatar(member)
    avatar_img   = _make_circle_avatar(avatar_bytes, 150)

    # Avatar glow ring
    glow = Image.new("RGBA", (170, 170), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((0, 0, 169, 169), outline=(147, 90, 255, 200), width=5)
    bg.paste(glow, (65, 65), mask=glow)
    bg.paste(avatar_img, (75, 75), mask=avatar_img)

    # ── Text ─────────────────────────────────────────────────────────────────
    draw = ImageDraw.Draw(bg)
    font_big  = _get_font(38)
    font_mid  = _get_font_regular(22)
    font_sm   = _get_font_regular(18)

    # Decorative line
    draw.rectangle([(250, 85), (254, 215)], fill=(147, 90, 255, 220))

    # Welcome label
    draw.text((270, 88), "WELCOME", font=font_sm, fill=(180, 140, 255, 200))

    # Username
    display = member.display_name
    if len(display) > 22:
        display = display[:20] + "…"
    draw.text((270, 115), display, font=font_big, fill=(255, 255, 255, 255))

    # Tag
    draw.text((270, 165), f"#{member.name}", font=font_mid, fill=(180, 180, 200, 210))

    # Message
    draw.text((270, 200), message, font=font_sm, fill=(200, 200, 220, 200))

    # Decorative corner dots
    for x, y in [(W-20, 20), (W-20, H-20), (20, H-20)]:
        draw.ellipse((x-4, y-4, x+4, y+4), fill=(147, 90, 255, 160))

    # ── Output ───────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="welcome.png")


async def generate_leave_card(
    member: discord.Member,
    background_path: str | None,
    message: str,
) -> discord.File:
    W, H = 900, 300

    if background_path and os.path.exists(background_path):
        bg = Image.open(background_path).convert("RGB").resize((W, H))
    else:
        bg = _make_gradient_bg(W, H, (50, 10, 10), (25, 10, 40))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    bg = bg.convert("RGBA")
    bg.paste(overlay, mask=overlay)

    avatar_bytes = await _fetch_avatar(member)
    avatar_img   = _make_circle_avatar(avatar_bytes, 150)

    # Greyscale avatar for leave
    grey = avatar_img.convert("LA").convert("RGBA")
    glow = Image.new("RGBA", (170, 170), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((0, 0, 169, 169), outline=(200, 80, 80, 200), width=5)
    bg.paste(glow, (65, 65), mask=glow)
    bg.paste(grey, (75, 75), mask=grey)

    draw = ImageDraw.Draw(bg)
    font_big = _get_font(38)
    font_mid = _get_font_regular(22)
    font_sm  = _get_font_regular(18)

    draw.rectangle([(250, 85), (254, 215)], fill=(220, 80, 80, 220))
    draw.text((270, 88), "GOODBYE", font=font_sm, fill=(255, 140, 140, 200))

    display = member.display_name
    if len(display) > 22:
        display = display[:20] + "…"
    draw.text((270, 115), display, font=font_big, fill=(255, 255, 255, 255))
    draw.text((270, 165), f"#{member.name}", font=font_mid, fill=(200, 180, 180, 210))
    draw.text((270, 200), message, font=font_sm, fill=(220, 200, 200, 200))

    for x, y in [(W-20, 20), (W-20, H-20), (20, H-20)]:
        draw.ellipse((x-4, y-4, x+4, y+4), fill=(220, 80, 80, 160))

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="goodbye.png")
