"""Generate rank-card and leaderboard images for the leveling system."""

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

BG       = (10,  14,  26)
ACCENT   = (0,  220, 255)
TRACK_BG = (20,  32,  58)
ROW_ALT  = (15,  22,  44)
TEXT_W   = (255, 255, 255)
TEXT_G   = (130, 150, 185)
TEXT_C   = (0,  220, 255)
GOLD     = (255, 215,  0)
SILVER   = (192, 192, 192)
BRONZE   = (205, 127,  50)


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


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


# ── Rank card ─────────────────────────────────────────────────────────────────

def _build_card(
    display_name: str,
    avatar_raw: bytes | None,
    level: int,
    xp_in_level: int,
    xp_needed: int,
    rank: int,
    messages: int,
) -> io.BytesIO:
    W, H = 920, 210
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
            ImageDraw.Draw(ring).ellipse(
                [0, 0, AVT + 5, AVT + 5], outline=(*ACCENT, 180), width=3
            )
            card.alpha_composite(ring, (AX - 3, AY - 3))
            card.alpha_composite(avt, (AX, AY))
        except Exception:
            draw.ellipse([AX, AY, AX + AVT, AY + AVT], fill=(30, 50, 80))
    else:
        draw.ellipse([AX, AY, AX + AVT, AY + AVT], fill=(30, 50, 80))

    TX = 185          # left edge of text/bar area
    RX = W - 22       # right edge

    # Username
    draw.text((TX, 28), display_name[:22], font=_font(30), fill=TEXT_W)

    # Level (left) — Rank (right-aligned)
    draw.text((TX, 76), f"LEVEL {level}", font=_font(40), fill=TEXT_C)
    rank_str = f"RANK #{rank}"
    rw = _text_w(draw, rank_str, _font(40, bold=False))
    draw.text((RX - rw, 76), rank_str, font=_font(40, bold=False), fill=TEXT_G)

    # Message count — plain text, no emoji
    draw.text((TX, 130), f"Messages: {messages:,}", font=_font(18, bold=False), fill=TEXT_G)

    # XP fraction right-aligned above bar
    xp_label = f"{_fmt(xp_in_level)} / {_fmt(xp_needed)} XP"
    xl_w = _text_w(draw, xp_label, _font(16, bold=False))
    draw.text((RX - xl_w, 131), xp_label, font=_font(16, bold=False), fill=TEXT_G)

    # XP bar — full width between TX and RX
    BX, BY = TX, 162
    BW = RX - TX
    BH = 26
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

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out


# ── Leaderboard image ─────────────────────────────────────────────────────────

def _build_leaderboard(
    title: str,
    rows: list[tuple[int, str, str]],   # (position, display_name, stat_text)
    caller_rank: int,
    caller_name: str,
    page: int,
    total_pages: int,
) -> io.BytesIO:
    W = 720
    ROW_H = 54
    HEADER_H = 76
    FOOTER_H = 60
    H = HEADER_H + ROW_H * max(len(rows), 1) + FOOTER_H

    card = Image.new("RGBA", (W, H), (*BG, 255))
    draw = ImageDraw.Draw(card)

    # Top accent bar
    draw.rectangle([0, 0, W, 5], fill=(*ACCENT, 255))

    # Header
    draw.text((20, 14), title, font=_font(30), fill=TEXT_C)
    page_str = f"Page {page}/{total_pages}"
    pw = _text_w(draw, page_str, _font(18, bold=False))
    draw.text((W - pw - 20, 22), page_str, font=_font(18, bold=False), fill=TEXT_G)

    # Separator
    draw.rectangle([20, HEADER_H - 4, W - 20, HEADER_H - 3], fill=TRACK_BG)

    # Rows
    medal = {1: "1ST", 2: "2ND", 3: "3RD"}
    medal_col = {1: GOLD, 2: SILVER, 3: BRONZE}

    for i, (pos, name, stat) in enumerate(rows):
        y = HEADER_H + i * ROW_H
        row_bg = ROW_ALT if i % 2 == 0 else BG
        draw.rectangle([0, y, W, y + ROW_H], fill=(*row_bg, 255))

        # Position badge
        pos_text = medal.get(pos, str(pos))
        pos_col  = medal_col.get(pos, TEXT_G)
        draw.text((20, y + 14), pos_text, font=_font(20), fill=pos_col)

        # Name
        short = name[:24]
        draw.text((80, y + 14), short, font=_font(22), fill=TEXT_W)

        # Stat right-aligned
        sw = _text_w(draw, stat, _font(20, bold=False))
        draw.text((W - sw - 20, y + 15), stat, font=_font(20, bold=False), fill=TEXT_C)

    # Footer separator + caller rank
    fy = H - FOOTER_H
    draw.rectangle([20, fy, W - 20, fy + 1], fill=TRACK_BG)
    caller_txt = f"Your position: #{caller_rank}  ({caller_name})"
    draw.text((20, fy + 16), caller_txt, font=_font(20, bold=False), fill=TEXT_G)

    # Bottom accent
    draw.rectangle([0, H - 5, W, H], fill=(*ACCENT, 255))

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out


# ── Public async entry points ─────────────────────────────────────────────────

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


async def generate_leaderboard_card(
    title: str,
    rows: list[tuple[int, str, str]],
    caller_rank: int,
    caller_name: str,
    page: int,
    total_pages: int,
) -> io.BytesIO:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _build_leaderboard,
        title, rows, caller_rank, caller_name, page, total_pages,
    )
