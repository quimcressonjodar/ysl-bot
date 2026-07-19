"""Generate rank-card images for the leveling system."""

import asyncio
import io

import discord
from PIL import Image, ImageDraw, ImageFont

# ── Fonts ─────────────────────────────────────────────────────────────────────

_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_BOLD if bold else _REGULAR, size)


# ── Palette ───────────────────────────────────────────────────────────────────

BG       = (10,  14,  26)    # very dark navy
ACCENT   = (0,  220, 255)    # bright cyan
TRACK_BG = (20,  32,  58)    # dark bar track
TEXT_W   = (255, 255, 255)
TEXT_G   = (130, 150, 185)
TEXT_C   = (0,  220, 255)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _circle_avatar(raw: bytes, size: int) -> Image.Image:
    img = Image.open(io.BytesIO(raw)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _gradient_bar(width: int, height: int) -> Image.Image:
    """Cyan → blue horizontal gradient for the XP bar fill."""
    img = Image.new("RGBA", (width, height))
    pix = img.load()
    for x in range(width):
        t = x / max(width - 1, 1)
        r = int(t * 30)
        g = int(220 - t * 80)
        b = int(255 - t * 45)
        for y in range(height):
            pix[x, y] = (r, g, b, 255)
    return img


# ── Card builder (sync — run in executor) ─────────────────────────────────────

def _build_card(
    display_name: str,
    avatar_raw: bytes | None,
    level: int,
    xp_in_level: int,
    xp_needed: int,
    rank: int,
    messages: int,
) -> io.BytesIO:
    W, H = 900, 210
    card = Image.new("RGBA", (W, H), (*BG, 255))
    draw = ImageDraw.Draw(card)

    # Left cyan accent bar
    draw.rectangle([0, 0, 6, H], fill=(*ACCENT, 255))

    # Avatar
    AVT = 142
    AX, AY = 22, 34
    if avatar_raw:
        try:
            avt = _circle_avatar(avatar_raw, AVT)
            ring = Image.new("RGBA", (AVT + 6, AVT + 6), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse([0, 0, AVT + 5, AVT + 5], outline=(*ACCENT, 180), width=3)
            card.alpha_composite(ring, (AX - 3, AY - 3))
            card.alpha_composite(avt, (AX, AY))
        except Exception:
            draw.ellipse([AX, AY, AX + AVT, AY + AVT], fill=(30, 50, 80))
    else:
        draw.ellipse([AX, AY, AX + AVT, AY + AVT], fill=(30, 50, 80))

    # Text area
    TX = 185

    # Username
    draw.text((TX, 28), display_name[:22], font=_font(30), fill=TEXT_W)

    # Level (left) and Rank (right-aligned)
    draw.text((TX, 78), f"LEVEL {level}", font=_font(40), fill=TEXT_C)
    rank_str = f"RANK #{rank}"
    rw = draw.textbbox((0, 0), rank_str, font=_font(40, bold=False))[2]
    draw.text((W - rw - 22, 78), rank_str, font=_font(40, bold=False), fill=TEXT_G)

    # Message count
    draw.text((TX, 130), f"💬  {messages:,} messages", font=_font(18, bold=False), fill=TEXT_G)

    # XP bar
    BX, BY, BW, BH = TX, 162, 650, 26
    r = BH // 2
    draw.rounded_rectangle([BX, BY, BX + BW, BY + BH], radius=r, fill=TRACK_BG)

    fill_ratio = min(xp_in_level / max(xp_needed, 1), 1.0)
    fill_px = max(int(BW * fill_ratio), BH if fill_ratio > 0 else 0)
    if fill_px > 0:
        grad = _gradient_bar(fill_px, BH)
        bar_mask = Image.new("L", (fill_px, BH), 0)
        ImageDraw.Draw(bar_mask).rounded_rectangle([0, 0, fill_px, BH], radius=r, fill=255)
        grad.putalpha(bar_mask)
        card.alpha_composite(grad, (BX, BY))

    # XP label next to bar
    xp_label = f"{_fmt(xp_in_level)} / {_fmt(xp_needed)} XP"
    draw.text((BX + BW + 12, BY + 4), xp_label, font=_font(16, bold=False), fill=TEXT_G)

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out


# ── Public async entry point ──────────────────────────────────────────────────

async def generate_rank_card(
    user: discord.abc.User,
    level: int,
    xp_in_level: int,
    xp_needed: int,
    rank: int,
    messages: int,
) -> io.BytesIO:
    try:
        avatar_raw = await user.display_avatar.with_size(128).read()
    except Exception:
        avatar_raw = None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _build_card,
        user.display_name, avatar_raw,
        level, xp_in_level, xp_needed, rank, messages,
    )
