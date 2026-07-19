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

BG_DARK  = (12,  18,  36)
BG_MID   = (18,  26,  52)
BG_ROW   = (24,  34,  64)
ACCENT   = (0,  210, 255)        # bright cyan
ACCENT2  = (0,  140, 200)        # deeper cyan
TEXT_W   = (235, 240, 255)       # near-white
TEXT_G   = (120, 145, 185)       # muted blue-grey
TEXT_C   = (0,  210, 255)        # cyan
GOLD     = (255, 200,  40)
SILVER   = (185, 195, 210)
BRONZE   = (200, 130,  60)
DIVIDER  = (30,  44,  80)


# ── Micro helpers ─────────────────────────────────────────────────────────────

def _tw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """Text pixel width."""
    return draw.textbbox((0, 0), text, font=font)[2]


def _circle(raw: bytes | None, size: int, fallback: tuple = BG_ROW) -> Image.Image:
    """Return a circular RGBA image of `size` × `size`."""
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if raw:
        try:
            src = Image.open(io.BytesIO(raw)).convert("RGBA").resize(
                (size, size), Image.LANCZOS
            )
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
            base.paste(src, (0, 0), mask)
            return base
        except Exception:
            pass
    # Fallback: solid coloured circle
    ImageDraw.Draw(base).ellipse([0, 0, size - 1, size - 1], fill=(*fallback, 255))
    return base


def _gradient_h(width: int, height: int,
                c1: tuple, c2: tuple) -> Image.Image:
    """Horizontal gradient from c1 to c2."""
    img = Image.new("RGBA", (width, height))
    pix = img.load()
    for x in range(width):
        t = x / max(width - 1, 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for y in range(height):
            pix[x, y] = (r, g, b, 255)
    return img


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ══════════════════════════════════════════════════════════════════════════════
# RANK CARD
# ══════════════════════════════════════════════════════════════════════════════

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
    card = Image.new("RGBA", (W, H), (*BG_DARK, 255))
    draw = ImageDraw.Draw(card)

    # Subtle gradient background panel on right side
    panel = _gradient_h(W - 174, H, BG_DARK, BG_MID)
    card.alpha_composite(panel, (174, 0))

    # Left accent strip with gradient
    strip = _gradient_h(6, H, ACCENT, ACCENT2)
    card.alpha_composite(strip, (0, 0))

    # Avatar with cyan ring
    AVT, AX, AY = 140, 20, 35
    ring_sz = AVT + 8
    ring_img = Image.new("RGBA", (ring_sz, ring_sz), (0, 0, 0, 0))
    ImageDraw.Draw(ring_img).ellipse(
        [0, 0, ring_sz - 1, ring_sz - 1], outline=(*ACCENT, 200), width=3
    )
    card.alpha_composite(ring_img, (AX - 4, AY - 4))
    avt = _circle(avatar_raw, AVT)
    card.alpha_composite(avt, (AX, AY))

    TX = 182   # text / bar left edge
    RX = W - 22  # right edge

    # ── Name ──────────────────────────────────────────────────────────────────
    draw.text((TX, 26), display_name[:24], font=_font(28), fill=TEXT_W)

    # ── Level (left) + Rank (right) ───────────────────────────────────────────
    draw.text((TX, 68), f"LEVEL {level}", font=_font(42), fill=TEXT_C)
    rank_str = f"RANK #{rank}"
    rw = _tw(draw, rank_str, _font(26, bold=False))
    draw.text((RX - rw, 80), rank_str, font=_font(26, bold=False), fill=TEXT_G)

    # ── Messages ───────────────────────────────────────────────────────────────
    draw.text((TX, 124), f"Messages: {messages:,}", font=_font(18, bold=False), fill=TEXT_G)

    # ── XP label above bar (right-aligned) ───────────────────────────────────
    xp_label = f"{_fmt(xp_in_level)} / {_fmt(xp_needed)} XP"
    xl_w = _tw(draw, xp_label, _font(15, bold=False))
    draw.text((RX - xl_w, 125), xp_label, font=_font(15, bold=False), fill=TEXT_G)

    # ── Progress bar ──────────────────────────────────────────────────────────
    BX, BY, BW, BH = TX, 158, RX - TX, 26
    r = BH // 2
    # Track
    draw.rounded_rectangle([BX, BY, BX + BW, BY + BH], radius=r, fill=(*BG_ROW, 255))
    # Fill
    fill_ratio = min(xp_in_level / max(xp_needed, 1), 1.0)
    fill_px = max(int(BW * fill_ratio), r * 2 if fill_ratio > 0 else 0)
    if fill_px > 0:
        grad = _gradient_h(fill_px, BH, ACCENT, ACCENT2)
        bar_mask = Image.new("L", (fill_px, BH), 0)
        ImageDraw.Draw(bar_mask).rounded_rectangle(
            [0, 0, fill_px - 1, BH - 1], radius=r, fill=255
        )
        grad.putalpha(bar_mask)
        card.alpha_composite(grad, (BX, BY))

    # Bottom divider line
    draw.rectangle([TX, 194, RX, 195], fill=(*DIVIDER, 255))

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD CARD
# ══════════════════════════════════════════════════════════════════════════════

_ROW_H   = 64
_HEAD_H  = 80
_FOOT_H  = 56
_PAD     = 18
_AVT_SZ  = 38

_MEDAL_TEXT  = {1: "1ST", 2: "2ND", 3: "3RD"}
_MEDAL_COLOR = {1: GOLD,  2: SILVER, 3: BRONZE}


def _build_leaderboard(
    title: str,
    rows: list[tuple[int, str, str, bytes | None]],   # pos, name, stat, avatar_bytes
    caller_rank: int,
    caller_name: str,
    page: int,
    total_pages: int,
) -> io.BytesIO:
    W = 740
    n = max(len(rows), 1)
    H = _HEAD_H + _ROW_H * n + _FOOT_H

    card = Image.new("RGBA", (W, H), (*BG_DARK, 255))
    draw = ImageDraw.Draw(card)

    # ── Header ────────────────────────────────────────────────────────────────
    # Background panel
    draw.rectangle([0, 0, W, _HEAD_H], fill=(*BG_MID, 255))
    # Left accent
    draw.rectangle([0, 0, 5, _HEAD_H], fill=(*ACCENT, 255))
    # Title
    draw.text((_PAD + 8, _HEAD_H // 2 - 17), title, font=_font(28), fill=TEXT_W)
    # Page indicator right-aligned
    pg = f"{page} / {total_pages}"
    pg_w = _tw(draw, pg, _font(18, bold=False))
    draw.text((W - _PAD - pg_w, _HEAD_H // 2 - 11), pg, font=_font(18, bold=False), fill=TEXT_G)
    # Thin separator
    draw.rectangle([0, _HEAD_H - 2, W, _HEAD_H], fill=(*DIVIDER, 255))

    # ── Rows ──────────────────────────────────────────────────────────────────
    for i, (pos, name, stat, avt_bytes) in enumerate(rows):
        y = _HEAD_H + i * _ROW_H
        row_bg = BG_ROW if i % 2 == 0 else BG_DARK
        draw.rectangle([0, y, W, y + _ROW_H - 1], fill=(*row_bg, 255))

        # Position badge
        pos_txt = _MEDAL_TEXT.get(pos, str(pos))
        pos_col = _MEDAL_COLOR.get(pos, TEXT_G)
        badge_font = _font(18, bold=(pos <= 3))
        bw = _tw(draw, pos_txt, badge_font)
        draw.text((_PAD + (34 - bw) // 2, y + (_ROW_H - 22) // 2), pos_txt,
                  font=badge_font, fill=pos_col)

        # Avatar circle
        avt_x = _PAD + 38
        avt_y = y + (_ROW_H - _AVT_SZ) // 2
        avt_img = _circle(avt_bytes, _AVT_SZ, BG_MID)
        card.alpha_composite(avt_img, (avt_x, avt_y))

        # Name
        name_x = avt_x + _AVT_SZ + 10
        short = name[:26]
        draw.text((name_x, y + (_ROW_H - 24) // 2), short, font=_font(21), fill=TEXT_W)

        # Stat right-aligned
        sw = _tw(draw, stat, _font(20, bold=False))
        draw.text((W - _PAD - sw, y + (_ROW_H - 22) // 2), stat,
                  font=_font(20, bold=False), fill=TEXT_C)

        # Row bottom divider
        draw.rectangle([_PAD, y + _ROW_H - 1, W - _PAD, y + _ROW_H - 1],
                       fill=(*DIVIDER, 120))

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = _HEAD_H + n * _ROW_H
    draw.rectangle([0, fy, W, H], fill=(*BG_MID, 255))
    draw.rectangle([0, fy, W, fy + 2], fill=(*DIVIDER, 255))
    caller_txt = f"Your position:  #{caller_rank}  —  {caller_name}"
    draw.text((_PAD + 8, fy + (_FOOT_H - 22) // 2), caller_txt,
              font=_font(20, bold=False), fill=TEXT_G)
    # Bottom accent
    draw.rectangle([0, H - 4, W, H], fill=(*ACCENT2, 255))

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ASYNC ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════════

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
        user.display_name, avatar_raw, level, xp_in_level, xp_needed, rank, messages,
    )


async def fetch_leaderboard_avatars(
    bot: discord.Client,
    docs: list[dict],
) -> list[bytes | None]:
    """Fetch 32×32 avatar bytes for each doc in parallel."""
    async def _fetch(doc: dict) -> bytes | None:
        try:
            user = bot.get_user(int(doc["_id"])) or await bot.fetch_user(int(doc["_id"]))
            return await user.display_avatar.with_size(32).read()
        except Exception:
            return None
    return list(await asyncio.gather(*[_fetch(d) for d in docs]))


async def generate_leaderboard_card(
    title: str,
    rows: list[tuple[int, str, str, bytes | None]],
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
