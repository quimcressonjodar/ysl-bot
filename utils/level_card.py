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

BG       = (22,  26,  42)          # dark navy card
TRACK    = (38,  46,  72)          # bar track
ACCENT   = (0,  180, 255)          # bright blue
ACCENT2  = (0,  100, 200)          # deeper blue
TEXT_W   = (230, 235, 255)         # near-white
TEXT_G   = (110, 130, 170)         # muted blue-grey


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


def _th(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _circle_avatar(raw: bytes | None, size: int) -> Image.Image:
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if raw:
        try:
            src  = Image.open(io.BytesIO(raw)).convert("RGBA").resize(
                (size, size), Image.LANCZOS
            )
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
            out.paste(src, (0, 0), mask)
            return out
        except Exception:
            pass
    ImageDraw.Draw(out).ellipse([0, 0, size - 1, size - 1], fill=(*TRACK, 255))
    return out


def _gradient_h(width: int, height: int, c1: tuple, c2: tuple) -> Image.Image:
    img = Image.new("RGBA", (width, height))
    pix = img.load()
    for x in range(width):
        t   = x / max(width - 1, 1)
        r   = int(c1[0] + (c2[0] - c1[0]) * t)
        g   = int(c1[1] + (c2[1] - c1[1]) * t)
        b   = int(c1[2] + (c2[2] - c1[2]) * t)
        for y in range(height):
            pix[x, y] = (r, g, b, 255)
    return img


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ── Card builder ──────────────────────────────────────────────────────────────
#
# Layout (matches reference screenshot):
#
#   ┌─────────────────────────────────────┐
#   │ [avt]  LEVEL X          RANK #Y     │
#   │        username          xp / total │
#   │        [═══════bar══════════      ] │
#   └─────────────────────────────────────┘

def _build_card(
    display_name: str,
    avatar_raw: bytes | None,
    level: int,
    xp_in_level: int,
    xp_needed: int,
    rank: int,
) -> io.BytesIO:
    W, H = 440, 108
    PAD  = 12

    card = Image.new("RGBA", (W, H), (*BG, 255))
    draw = ImageDraw.Draw(card)

    # Avatar
    AVT_SZ = 80
    AVT_X, AVT_Y = PAD, (H - AVT_SZ) // 2
    avt = _circle_avatar(avatar_raw, AVT_SZ)
    # Thin cyan ring
    ring = Image.new("RGBA", (AVT_SZ + 4, AVT_SZ + 4), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse(
        [0, 0, AVT_SZ + 3, AVT_SZ + 3], outline=(*ACCENT, 180), width=2
    )
    card.alpha_composite(ring, (AVT_X - 2, AVT_Y - 2))
    card.alpha_composite(avt, (AVT_X, AVT_Y))

    # Right section bounds
    RX  = AVT_X + AVT_SZ + PAD    # left edge of text block
    RW  = W - RX - PAD            # width of text block

    f_label  = _font(14, bold=False)
    f_name   = _font(17)
    f_xp     = _font(14, bold=False)
    f_small  = _font(13, bold=False)

    # ── Row 1: LEVEL X (left)   RANK #Y (right) ──────────────────────────────
    TOP_Y = 14
    lv_text   = f"LEVEL {level}"
    rank_text = f"RANK {rank}"
    draw.text((RX, TOP_Y), lv_text,   font=f_label, fill=TEXT_G)
    rw = _tw(draw, rank_text, f_label)
    draw.text((W - PAD - rw, TOP_Y), rank_text, font=f_label, fill=TEXT_G)

    # ── Row 2: username (left)   XP (right) ──────────────────────────────────
    NAME_Y = TOP_Y + _th(draw, lv_text, f_label) + 6
    short  = display_name[:20]
    draw.text((RX, NAME_Y), short, font=f_name, fill=TEXT_W)
    xp_txt = f"{_fmt(xp_in_level)} / {_fmt(xp_needed)}"
    xw     = _tw(draw, xp_txt, f_xp)
    draw.text(
        (W - PAD - xw, NAME_Y + (_th(draw, short, f_name) - _th(draw, xp_txt, f_xp)) // 2),
        xp_txt, font=f_xp, fill=TEXT_G,
    )

    # ── Row 3: progress bar ───────────────────────────────────────────────────
    BAR_Y  = H - PAD - 18
    BAR_H  = 14
    BAR_W  = W - RX - PAD
    r      = BAR_H // 2
    # Track
    draw.rounded_rectangle(
        [RX, BAR_Y, RX + BAR_W, BAR_Y + BAR_H], radius=r, fill=(*TRACK, 255)
    )
    # Fill
    ratio   = min(xp_in_level / max(xp_needed, 1), 1.0)
    fill_px = max(int(BAR_W * ratio), r * 2 if ratio > 0 else 0)
    if fill_px > 0:
        grad     = _gradient_h(fill_px, BAR_H, ACCENT, ACCENT2)
        bar_mask = Image.new("L", (fill_px, BAR_H), 0)
        ImageDraw.Draw(bar_mask).rounded_rectangle(
            [0, 0, fill_px - 1, BAR_H - 1], radius=r, fill=255
        )
        grad.putalpha(bar_mask)
        card.alpha_composite(grad, (RX, BAR_Y))

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
    messages: int,          # kept for API compat but not shown (clean card)
) -> io.BytesIO:
    try:
        avatar_raw = await user.display_avatar.with_size(128).read()
    except Exception:
        avatar_raw = None
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _build_card,
        user.display_name, avatar_raw, level, xp_in_level, xp_needed, rank,
    )
