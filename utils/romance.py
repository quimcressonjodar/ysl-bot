"""Small, self-contained helpers for the bot's romance commands."""

from __future__ import annotations

import hashlib
import io
import math

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


# ── canvas / timing ──────────────────────────────────────────────────────────
CANVAS_W, CANVAS_H = 800, 520
FRAME_COUNT    = 28
FRAME_DURATION = 65          # ms per frame

# ── character proportions ────────────────────────────────────────────────────
HEAD_R   = 76    # avatar sphere radius
TORSO_HW = 56    # torso half-width
TORSO_H  = 92    # torso height
ARM_R    = 18    # arm tube radius
LEG_R    = 20    # leg tube radius
LEG_H    = 100   # leg length
GROUND_Y = 490   # y of ground plane
HEAD_CY  = 178   # y of head sphere centre

# ── palette ───────────────────────────────────────────────────────────────────
_CLOTH_HI  = (0.32, 0.26, 0.58)
_CLOTH_MID = (0.20, 0.16, 0.42)
_CLOTH_DRK = (0.10, 0.08, 0.24)
_SKIN_HI   = (1.00, 0.88, 0.73)
_SKIN_MID  = (0.94, 0.74, 0.58)
_SKIN_DRK  = (0.72, 0.52, 0.38)


# ─────────────────────────────────────────────────────────────────────────────
# Public API helpers
# ─────────────────────────────────────────────────────────────────────────────

def love_score(first_id: int, second_id: int) -> int:
    pair = ":".join(str(v) for v in sorted((first_id, second_id)))
    digest = hashlib.sha256(pair.encode()).digest()
    return int.from_bytes(digest[:2], "big") % 101


def love_verdict(score: int) -> str:
    if score >= 95: return "The stars are screaming yes."
    if score >= 80: return "There is definitely something special here."
    if score >= 60: return "The chemistry is looking promising."
    if score >= 40: return "There is potential, but someone has to make the first move."
    if score >= 20: return "The spark is shy today."
    return "The cosmic timing is not on your side yet."


def decode_avatar(data: bytes) -> Image.Image:
    if len(data) > 5_000_000:
        raise ValueError("avatar is too large")
    size = HEAD_R * 2
    with Image.open(io.BytesIO(data)) as img:
        return img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


# ─────────────────────────────────────────────────────────────────────────────
# Cairo ↔ PIL conversion
# ─────────────────────────────────────────────────────────────────────────────

def _pil_to_cairo(pil_img: Image.Image) -> cairo.ImageSurface:
    """Convert a PIL RGBA image to a Cairo ARGB32 surface (premultiplied alpha)."""
    arr = np.array(pil_img.convert("RGBA"), dtype=np.float32)
    alpha = arr[:, :, 3:4] / 255.0
    arr[:, :, :3] *= alpha                         # premultiply
    bgra = arr[:, :, [2, 1, 0, 3]].astype(np.uint8)
    buf = bgra.tobytes()
    surf = cairo.ImageSurface.create_for_data(
        bytearray(buf), cairo.FORMAT_ARGB32,
        pil_img.width, pil_img.height, pil_img.width * 4,
    )
    return surf


def _cairo_to_pil(surf: cairo.ImageSurface) -> Image.Image:
    """Convert a Cairo ARGB32 surface to a PIL RGBA image (straight alpha)."""
    w, h = surf.get_width(), surf.get_height()
    surf.flush()
    buf = bytes(surf.get_data())
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 4)).copy()
    # BGRA → RGBA
    rgba = arr[:, :, [2, 1, 0, 3]]
    # un-premultiply
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    a = np.where(a > 0, a, 1.0)
    rgba = rgba.astype(np.float32)
    rgba[:, :, :3] = np.clip(rgba[:, :, :3] / a, 0, 255)
    return Image.fromarray(rgba.astype(np.uint8), "RGBA")


# ─────────────────────────────────────────────────────────────────────────────
# Drawing primitives
# ─────────────────────────────────────────────────────────────────────────────

def _shadow(ctx: cairo.Context, cx: float, gy: float, rx: float, alpha: float):
    ctx.save()
    ctx.translate(cx, gy)
    ctx.scale(1.0, 0.22)
    pat = cairo.RadialGradient(0, 0, 0, 0, 0, rx)
    pat.add_color_stop_rgba(0.0, 0, 0, 0, alpha)
    pat.add_color_stop_rgba(1.0, 0, 0, 0, 0.0)
    ctx.set_source(pat)
    ctx.arc(0, 0, rx, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def _sphere(ctx: cairo.Context, cx: float, cy: float, r: float,
            avatar_surf: cairo.ImageSurface):
    """Textured 3-D sphere: avatar + rim AO + diffuse shading + specular spot."""
    # 1 · avatar texture
    ctx.save()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.clip()
    aw = avatar_surf.get_width()
    s = 2 * r / aw
    ctx.translate(cx - r, cy - r)
    ctx.scale(s, s)
    ctx.set_source_surface(avatar_surf, 0, 0)
    ctx.paint()
    ctx.restore()

    # 2 · rim AO (dark edge vignette)
    ctx.save()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.clip()
    rim = cairo.RadialGradient(cx, cy, r * 0.50, cx, cy, r)
    rim.add_color_stop_rgba(0.0, 0, 0, 0, 0.00)
    rim.add_color_stop_rgba(1.0, 0, 0, 0, 0.60)
    ctx.set_source(rim)
    ctx.paint()
    ctx.restore()

    # 3 · diffuse shading (light top-left → shadow bottom-right)
    ctx.save()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.clip()
    diff = cairo.RadialGradient(cx - r * 0.28, cy - r * 0.38, 0,
                                 cx + r * 0.12, cy + r * 0.18, r * 1.25)
    diff.add_color_stop_rgba(0.0, 1, 1, 1, 0.07)
    diff.add_color_stop_rgba(0.45, 0, 0, 0, 0.00)
    diff.add_color_stop_rgba(1.0, 0, 0, 0, 0.28)
    ctx.set_source(diff)
    ctx.paint()
    ctx.restore()

    # 4 · specular highlight (top-left glossy spot)
    ctx.save()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.clip()
    sx, sy = cx - r * 0.36, cy - r * 0.40
    spec = cairo.RadialGradient(sx, sy, 0, sx, sy, r * 0.50)
    spec.add_color_stop_rgba(0.0, 1, 1, 1, 0.82)
    spec.add_color_stop_rgba(0.4, 1, 1, 1, 0.20)
    spec.add_color_stop_rgba(1.0, 1, 1, 1, 0.00)
    ctx.set_source(spec)
    ctx.paint()
    ctx.restore()

    # 5 · outline
    ctx.save()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.set_source_rgba(0.08, 0.04, 0.18, 0.90)
    ctx.set_line_width(4.0)
    ctx.stroke()
    ctx.restore()


def _tube(ctx: cairo.Context,
          x1: float, y1: float, x2: float, y2: float,
          radius: float, hi: tuple, mid: tuple, drk: tuple):
    """3-D tube from (x1,y1) to (x2,y2) with cross-gradient shading."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length, dx / length          # perpendicular unit vector

    # Build the rect path (with round caps via stroke trick)
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(x1, y1)
    ctx.line_to(x2, y2)
    ctx.set_line_width(radius * 2)

    # Gradient perpendicular to tube axis
    lx = x1 + px * radius * 0.72
    ly = y1 + py * radius * 0.72
    rx = x1 - px * radius * 0.72
    ry = y1 - py * radius * 0.72
    grad = cairo.LinearGradient(lx, ly, rx, ry)
    rh, gh, bh = hi
    rm, gm, bm = mid
    rd, gd, bd = drk
    grad.add_color_stop_rgb(0.00, min(1, rh * 1.20), min(1, gh * 1.20), min(1, bh * 1.20))
    grad.add_color_stop_rgb(0.25, rh, gh, bh)
    grad.add_color_stop_rgb(0.55, rm, gm, bm)
    grad.add_color_stop_rgb(1.00, rd, gd, bd)
    ctx.set_source(grad)
    ctx.stroke_preserve()
    ctx.restore()


def _capsule(ctx: cairo.Context, cx: float, cy: float,
             hw: float, h: float, hi: tuple, drk: tuple):
    """Rounded-rect torso with vertical gradient + side highlight."""
    rad = hw * 0.65
    x, y, w = cx - hw, cy, hw * 2

    def _rrect():
        ctx.new_path()
        ctx.arc(x + rad,     y + rad,     rad,  math.pi, -math.pi / 2)
        ctx.arc(x + w - rad, y + rad,     rad, -math.pi / 2, 0)
        ctx.arc(x + w - rad, y + h - rad, rad,  0, math.pi / 2)
        ctx.arc(x + rad,     y + h - rad, rad,  math.pi / 2, math.pi)
        ctx.close_path()

    ctx.save()
    _rrect()
    ctx.clip()

    # Vertical gradient
    rh, gh, bh = hi
    rd, gd, bd = drk
    vg = cairo.LinearGradient(cx, cy, cx, cy + h)
    vg.add_color_stop_rgb(0.0, min(1, rh * 1.30), min(1, gh * 1.30), min(1, bh * 1.30))
    vg.add_color_stop_rgb(0.45, rh, gh, bh)
    vg.add_color_stop_rgb(1.0, rd, gd, bd)
    ctx.set_source(vg)
    ctx.paint()

    # Left-edge shine
    sg = cairo.LinearGradient(x, cy, x + hw * 0.45, cy)
    sg.add_color_stop_rgba(0.0, 1, 1, 1, 0.28)
    sg.add_color_stop_rgba(1.0, 1, 1, 1, 0.00)
    ctx.set_source(sg)
    ctx.paint()
    ctx.restore()

    # Outline
    ctx.save()
    _rrect()
    ctx.set_source_rgba(0.08, 0.04, 0.18, 0.85)
    ctx.set_line_width(2.5)
    ctx.stroke()
    ctx.restore()


def _lips(ctx: cairo.Context, cx: float, cy: float, scale: float = 1.0):
    """3-D glossy lips: upper (cupid's bow) + lower with shine."""
    w = 24 * scale
    uy = cy - 4 * scale   # upper lip top
    my = cy               # middle crease
    ly = cy + 14 * scale  # lower lip bottom

    # ── upper lip ──────────────────────────────
    ctx.save()
    # Left lobe
    ctx.arc(cx - w * 0.42, my - 1, w * 0.44, math.pi, 0)
    # Cupid's bow valley (go back to centre)
    ctx.line_to(cx + w * 0.42 - w * 0.44, my - 1)
    # Right lobe
    ctx.arc(cx + w * 0.42, my - 1, w * 0.44, math.pi, 0)
    ctx.line_to(cx + w * 0.82, my)
    ctx.line_to(cx, my)
    ctx.line_to(cx - w * 0.82, my)
    ctx.close_path()

    ug = cairo.LinearGradient(cx, uy, cx, my)
    ug.add_color_stop_rgb(0.0, 0.95, 0.28, 0.42)
    ug.add_color_stop_rgb(1.0, 0.70, 0.10, 0.22)
    ctx.set_source(ug)
    ctx.fill()
    ctx.restore()

    # ── lower lip ──────────────────────────────
    ctx.save()
    ctx.move_to(cx - w * 0.82, my)
    ctx.curve_to(cx - w * 0.82, ly + 4 * scale,
                  cx + w * 0.82, ly + 4 * scale,
                  cx + w * 0.82, my)
    ctx.close_path()

    lg = cairo.RadialGradient(cx, my + 3 * scale, 0,
                               cx, my + 6 * scale, w * 0.85)
    lg.add_color_stop_rgb(0.0, 1.00, 0.60, 0.68)
    lg.add_color_stop_rgb(0.45, 0.88, 0.22, 0.35)
    lg.add_color_stop_rgb(1.0,  0.60, 0.08, 0.18)
    ctx.set_source(lg)
    ctx.fill()
    ctx.restore()

    # ── shine on lower lip ─────────────────────
    ctx.save()
    ctx.move_to(cx - w * 0.38, my + 4 * scale)
    ctx.curve_to(cx - w * 0.38, my + 9 * scale,
                  cx + w * 0.38, my + 9 * scale,
                  cx + w * 0.38, my + 4 * scale)
    ctx.close_path()
    sg = cairo.RadialGradient(cx, my + 5 * scale, 0,
                               cx, my + 7 * scale, w * 0.38)
    sg.add_color_stop_rgba(0.0, 1, 1, 1, 0.70)
    sg.add_color_stop_rgba(1.0, 1, 1, 1, 0.00)
    ctx.set_source(sg)
    ctx.fill()
    ctx.restore()

    # ── crease line ────────────────────────────
    ctx.save()
    ctx.move_to(cx - w * 0.82, my)
    ctx.line_to(cx + w * 0.82, my)
    ctx.set_source_rgba(0.45, 0.05, 0.12, 0.65)
    ctx.set_line_width(1.5 * scale)
    ctx.stroke()
    ctx.restore()


def _heart(ctx: cairo.Context, cx: float, cy: float, size: float, alpha: float):
    r = size * 0.5
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(1.0, 0.88)
    ctx.arc(-r * 0.50, -r * 0.08, r * 0.56, math.pi, 0)
    ctx.arc( r * 0.50, -r * 0.08, r * 0.56, math.pi, 0)
    ctx.line_to( r * 1.10,  r * 0.42)
    ctx.line_to( 0,          r * 1.50)
    ctx.line_to(-r * 1.10,  r * 0.42)
    ctx.close_path()
    hg = cairo.RadialGradient(0, -r * 0.15, 0, 0, r * 0.35, r * 1.5)
    hg.add_color_stop_rgba(0.0, 1.00, 0.62, 0.70, alpha)
    hg.add_color_stop_rgba(0.5, 0.92, 0.27, 0.47, alpha)
    hg.add_color_stop_rgba(1.0, 0.68, 0.08, 0.26, alpha)
    ctx.set_source(hg)
    ctx.fill()
    ctx.restore()


# ─────────────────────────────────────────────────────────────────────────────
# Character renderer
# ─────────────────────────────────────────────────────────────────────────────

def _character(ctx: cairo.Context,
               avatar_surf: cairo.ImageSurface,
               cx: float,
               lean_x: float,
               facing_right: bool,
               kiss_t: float,
               hug_target: tuple[float, float] | None):
    """
    Draw one full 3-D character.
    facing_right – True if this person leans toward positive-x (left character).
    hug_target   – (x, y) world-space wrap point for the inner arm.
    kiss_t       – 0 … 1 animation progress.
    """
    hcx = cx + lean_x
    hcy = HEAD_CY
    tcy = hcy + HEAD_R + 10          # torso top
    hip = tcy + TORSO_H              # hip bottom
    tcx = cx + lean_x * 0.55        # torso is less displaced than head

    inner = 1 if facing_right else -1   # +1 means right
    outer = -inner

    # ── ground shadow ──
    _shadow(ctx, cx, GROUND_Y, HEAD_R * 1.7, 0.18 + kiss_t * 0.12)

    # ── legs ──
    spread = int(26 - kiss_t * 8)
    _tube(ctx, tcx, hip, tcx - spread, GROUND_Y, LEG_R,
          _CLOTH_HI, _CLOTH_MID, _CLOTH_DRK)
    _tube(ctx, tcx, hip, tcx + spread, GROUND_Y, LEG_R,
          _CLOTH_HI, _CLOTH_MID, _CLOTH_DRK)

    # ── torso ──
    _capsule(ctx, tcx, tcy, TORSO_HW, TORSO_H, _CLOTH_MID, _CLOTH_DRK)

    # ── outer arm (away from partner) ──
    oax = tcx + outer * (TORSO_HW + 58)
    oay = tcy + TORSO_H * 0.52
    _tube(ctx, tcx + outer * TORSO_HW * 0.8, tcy + 20,
          oax, oay, ARM_R, _CLOTH_HI, _CLOTH_MID, _CLOTH_DRK)
    _tube(ctx, oax, oay,
          oax + outer * 16, oay + 48, ARM_R, _SKIN_HI, _SKIN_MID, _SKIN_DRK)

    # ── inner arm (hugs partner) ──
    isx = tcx + inner * TORSO_HW * 0.8
    isy = tcy + 20

    if hug_target is not None and kiss_t > 0.32:
        hp = max(0.0, (kiss_t - 0.32) / 0.68)   # 0 → 1

        # Upper-arm endpoint (elbow area)
        ex = isx + inner * (52 + hp * 28)
        ey = isy - hp * 28 + (1 - hp) * 36

        tx, ty = hug_target
        mx = (ex + tx) / 2
        my = (ey + ty) / 2 - hp * 18

        _tube(ctx, isx, isy, ex, ey,
              ARM_R, _CLOTH_HI, _CLOTH_MID, _CLOTH_DRK)
        _tube(ctx, ex, ey, mx, my,
              ARM_R, _SKIN_HI, _SKIN_MID, _SKIN_DRK)
        _tube(ctx, mx, my, tx, ty,
              int(ARM_R * 0.82), _SKIN_HI, _SKIN_MID, _SKIN_DRK)
    else:
        iex = tcx + inner * (TORSO_HW + 52)
        iey = tcy + TORSO_H * 0.44
        _tube(ctx, isx, isy, iex, iey,
              ARM_R, _CLOTH_HI, _CLOTH_MID, _CLOTH_DRK)
        _tube(ctx, iex, iey, iex + inner * 14, iey + 50,
              ARM_R, _SKIN_HI, _SKIN_MID, _SKIN_DRK)

    # ── head sphere ──
    _sphere(ctx, hcx, hcy, HEAD_R, avatar_surf)

    # ── lips (shift toward partner as they kiss) ──
    lip_cx = hcx + inner * HEAD_R * 0.28 * kiss_t
    lip_cy = hcy + HEAD_R * 0.52
    _lips(ctx, lip_cx, lip_cy, scale=1.0 + kiss_t * 0.30)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _add_text(pil: Image.Image, first_name: str, second_name: str,
              lcx: int, rcx: int, kiss_t: float):
    """Overlay title + name labels on a PIL image (simpler than Cairo fonts)."""
    draw = ImageDraw.Draw(pil)
    title_font = _font(32, bold=True)
    name_font  = _font(22, bold=True)
    purple = (91, 44, 102, 255)
    ink    = (30, 22, 55, 255)

    # Title
    title = "A YSL love story"
    tb = draw.textbbox((0, 0), title, font=title_font)
    tx = (CANVAS_W - (tb[2] - tb[0])) // 2
    draw.text((tx + 2, 22), title, font=title_font, fill=(0, 0, 0, 60))
    draw.text((tx,     20), title, font=title_font, fill=purple)

    # Names under feet
    label_y = GROUND_Y + 6
    for name, ncx in ((first_name[:18], lcx), (second_name[:18], rcx)):
        nb = draw.textbbox((0, 0), name, font=name_font)
        nx = ncx - (nb[2] - nb[0]) // 2
        draw.text((nx + 1, label_y + 1), name, font=name_font, fill=(0, 0, 0, 80))
        draw.text((nx,     label_y),     name, font=name_font, fill=ink)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_kiss_gif(
    first_avatar: Image.Image,
    second_avatar: Image.Image,
    first_name: str,
    second_name: str,
) -> io.BytesIO:
    """Render a 3-D animated kiss GIF and return it as a BytesIO buffer."""
    av1 = _pil_to_cairo(first_avatar)
    av2 = _pil_to_cairo(second_avatar)

    center = CANVAS_W // 2
    frames: list[Image.Image] = []

    for tick in range(FRAME_COUNT):
        raw_t = tick / (FRAME_COUNT - 1)               # 0 → 1
        kiss_t = math.sin(math.pi * raw_t)             # 0 → 1 → 0 (sine arch)

        gap  = int(190 - kiss_t * 126)                 # 190 → 64 px
        lean = int(kiss_t * 16)

        lcx = center - gap                             # left person X
        rcx = center + gap                             # right person X
        llean = lean                                   # leans right
        rlean = -lean                                  # leans left

        # Hugging arm target (the other person's mid-back)
        l_tcy = HEAD_CY + HEAD_R + 10
        r_tcy = l_tcy
        l_hug_target = (rcx + rlean * 0.55 - TORSO_HW - 8, r_tcy + TORSO_H * 0.48)
        r_hug_target = (lcx + llean * 0.55 + TORSO_HW + 8, l_tcy + TORSO_H * 0.48)

        # ── create Cairo surface ────────────────────────────────────────────
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, CANVAS_W, CANVAS_H)
        ctx  = cairo.Context(surf)

        # Background: warm gradient
        bg = cairo.LinearGradient(0, 0, 0, CANVAS_H)
        bg.add_color_stop_rgb(0.0, 1.00, 0.97, 0.98)
        bg.add_color_stop_rgb(1.0, 1.00, 0.90, 0.93)
        ctx.set_source(bg)
        ctx.paint()

        # Decorative soft bubbles
        for bx, by, br, bt in ((80, 80, 38, tick), (720, 85, 44, tick + 2),
                                 (65, 430, 30, tick + 4), (735, 420, 34, tick + 6)):
            off = math.sin((tick + bt) / 2.5) * 6
            bp = cairo.RadialGradient(bx, by + off, 0, bx, by + off, br)
            bp.add_color_stop_rgba(0.0, 1.0, 0.85, 0.90, 0.55)
            bp.add_color_stop_rgba(1.0, 1.0, 0.85, 0.90, 0.00)
            ctx.set_source(bp)
            ctx.arc(bx, by + off, br, 0, 2 * math.pi)
            ctx.fill()

        # Sparkles
        for idx, (sx, sy) in enumerate(((114, 126), (686, 135), (88, 385), (710, 375))):
            sz = 7 + ((tick + idx * 3) % 4)
            ctx.set_source_rgba(1.0, 0.91, 0.56, 0.85)
            ctx.set_line_width(3)
            ctx.move_to(sx - sz, sy); ctx.line_to(sx + sz, sy); ctx.stroke()
            ctx.move_to(sx, sy - sz); ctx.line_to(sx, sy + sz); ctx.stroke()

        # ── draw characters ────────────────────────────────────────────────
        _character(ctx, av1, lcx, llean, facing_right=True,
                   kiss_t=kiss_t, hug_target=l_hug_target)
        _character(ctx, av2, rcx, rlean, facing_right=False,
                   kiss_t=kiss_t, hug_target=r_hug_target)

        # ── hearts appear near the kiss peak ──────────────────────────────
        if kiss_t > 0.60:
            h_alpha = (kiss_t - 0.60) / 0.40
            _heart(ctx, center, 92  - int(h_alpha * 18), 36, h_alpha)
            _heart(ctx, center - 58, 128, 20, h_alpha * 0.75)
            _heart(ctx, center + 58, 128, 20, h_alpha * 0.75)

        # ── Cairo → PIL ────────────────────────────────────────────────────
        pil = _cairo_to_pil(surf)

        # Name labels (rendered with PIL for easy font support)
        _add_text(pil, first_name, second_name, lcx, rcx, kiss_t)

        frames.append(pil.convert("P", palette=Image.Palette.ADAPTIVE, dither=Image.Dither.NONE))

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION,
        loop=0,
        optimize=False,
    )
    buf.seek(0)
    return buf
