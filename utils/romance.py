"""Stick-figure kiss animation: walk → stop → hug → kiss."""
from __future__ import annotations

import hashlib
import io
import math

from PIL import Image, ImageDraw, ImageFont, ImageOps


# ── Canvas ────────────────────────────────────────────────────────────────────
CW, CH = 720, 450
GY     = 418      # ground Y

# ── Stick-figure proportions ─────────────────────────────────────────────────
HR   = 56         # avatar circle radius
BODY = 80         # shoulder → hip
THIGH_L = 70      # hip → knee
SHIN_L  = 60      # knee → foot
ARM_UP  = 58      # shoulder → elbow
ARM_LO  = 46      # elbow → hand
LINE_W  = 7       # limb stroke width

# Standing geometry (top of figure to bottom = HR + 5 + BODY + THIGH_L + SHIN_L)
SHY_BASE = GY - SHIN_L - THIGH_L - BODY    # shoulder Y (no bob)
HCY_BASE = SHY_BASE - HR - 5               # head centre Y (no bob)

# ── Phase boundaries ─────────────────────────────────────────────────────────
WALK_F = 20      # frames 0-19:  walk toward each other
STOP_F = 4       # frames 20-23: legs settle
HUG_F  = 8       # frames 24-31: full embrace
KISS_F = 12      # frames 32-43: lean in, lips meet, hearts
N_FRAMES  = WALK_F + STOP_F + HUG_F + KISS_F   # 44
FRAME_MS  = 70

# Horizontal positions
SX_L, SX_R  = 78,  642   # walk start (from edges)
EX_L, EX_R  = 244, 476   # walk end / hug position
KX_L, KX_R  = 296, 424   # kiss position (gap ≈ 128 px, heads nearly touching)

# ── Colours ───────────────────────────────────────────────────────────────────
INK    = (30, 22, 55, 255)
BG     = (255, 247, 251, 255)
HEART  = (236, 73, 123, 255)
SPARK  = (255, 232, 145, 220)
PURPLE = (91, 44, 102, 255)


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
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
    d = HR * 2
    with Image.open(io.BytesIO(data)) as img:
        return img.convert("RGBA").resize((d, d), Image.Resampling.LANCZOS)


# ─────────────────────────────────────────────────────────────────────────────
# Small utilities
# ─────────────────────────────────────────────────────────────────────────────

def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 2


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _polar(ox: float, oy: float, angle_deg: float, length: float):
    """Endpoint from origin; angle from vertical (straight down = 0°)."""
    r = math.radians(angle_deg)
    return int(ox + math.sin(r) * length), int(oy + math.cos(r) * length)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _avatar_circle(avatar: Image.Image) -> Image.Image:
    d = HR * 2
    av = ImageOps.fit(avatar, (d, d), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d - 1, d - 1), fill=255)
    av.putalpha(mask)
    return av


def _centered_text(draw, text, y, font, fill):
    b = draw.textbbox((0, 0), text, font=font)
    x = (CW - (b[2] - b[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)


# ─────────────────────────────────────────────────────────────────────────────
# Drawing sub-routines
# ─────────────────────────────────────────────────────────────────────────────

def _draw_heart(draw, cx: int, cy: int, scale: float, alpha: int = 255):
    r = int(16 * scale)
    fill = (*HEART[:3], alpha)
    top = cy - r // 2
    draw.ellipse((cx - r, top, cx, top + r), fill=fill)
    draw.ellipse((cx, top, cx + r, top + r), fill=fill)
    draw.polygon([(cx - r, top + r // 2), (cx + r, top + r // 2),
                  (cx, top + r * 2)], fill=fill)


def _draw_sparkles(draw, tick: int):
    for i, (x, y) in enumerate(((108, 125), (612, 132), (86, 368), (638, 374))):
        s = 7 + ((tick + i * 3) % 4)
        draw.line((x - s, y, x + s, y), fill=SPARK, width=3)
        draw.line((x, y - s, x, y + s), fill=SPARK, width=3)


def _draw_lips(draw, cx: float, cy: float, scale: float = 1.0):
    """Realistic glossy lips at (cx, cy) — cupid's bow upper, full lower, gloss highlights."""
    cx, cy = int(cx), int(cy)
    w   = int(26 * scale)   # half-width
    hu  = int(10 * scale)   # upper lip height
    hl  = int(14 * scale)   # lower lip height

    # ── Colours ──────────────────────────────────────────────────────────────
    lip_dark   = (155, 10,  35, 255)   # deep shadow / outline
    lip_mid    = (210, 30,  60, 255)   # main body
    lip_bright = (235, 55,  80, 255)   # lighter facing planes
    shine1     = (255, 180, 195, 220)  # primary gloss streak
    shine2     = (255, 230, 235, 160)  # soft secondary highlight
    divider    = (130,  5,  25, 220)   # centre crease between lips

    # ── Shadow base (slightly larger, dark) ──────────────────────────────────
    draw.ellipse((cx - w - 2, cy - hu - 2, cx + w + 2, cy + hl * 2 + 2),
                 fill=lip_dark)

    # ── Upper lip body ────────────────────────────────────────────────────────
    # Left lobe
    draw.ellipse((cx - w,       cy - hu, cx - 1,    cy + 3),  fill=lip_mid)
    # Right lobe
    draw.ellipse((cx + 1,       cy - hu, cx + w,    cy + 3),  fill=lip_mid)
    # Fill in centre strip so lobes connect
    draw.rectangle((cx - w // 2, cy - hu + 3, cx + w // 2, cy + 3), fill=lip_mid)

    # Cupid's-bow valley (background-coloured notch at top centre)
    bow_depth = int(5 * scale)
    draw.polygon([
        (cx - int(7 * scale), cy - hu + 2),
        (cx + int(7 * scale), cy - hu + 2),
        (cx,                   cy - bow_depth),
    ], fill=BG)

    # ── Lower lip body ────────────────────────────────────────────────────────
    draw.ellipse((cx - w + 2, cy, cx + w - 2, cy + hl * 2), fill=lip_bright)

    # Subtle darker shadow at corners of lower lip
    corner_r = int(8 * scale)
    draw.ellipse((cx - w + 2, cy, cx - w + 2 + corner_r * 2, cy + corner_r * 2),
                 fill=lip_dark)
    draw.ellipse((cx + w - 2 - corner_r * 2, cy, cx + w - 2, cy + corner_r * 2),
                 fill=lip_dark)

    # ── Centre crease between upper and lower lip ─────────────────────────────
    draw.line([(cx - w + 4, cy + 1), (cx + w - 4, cy + 1)],
              fill=divider, width=max(2, int(2 * scale)))

    # ── Primary gloss streak on lower lip ─────────────────────────────────────
    gx1 = cx - int(w * 0.55)
    gx2 = cx + int(w * 0.55)
    gy1 = cy + int(hl * 0.28)
    gy2 = cy + int(hl * 0.85)
    draw.ellipse((gx1, gy1, gx2, gy2), fill=shine1)

    # ── Soft secondary highlight (narrower, brighter centre) ─────────────────
    draw.ellipse((cx - int(w * 0.28), gy1 + int(2 * scale),
                  cx + int(w * 0.28), gy1 + int(hl * 0.45)),
                 fill=shine2)

    # ── Small upper-lip highlight (left lobe) ─────────────────────────────────
    draw.ellipse((cx - int(w * 0.7), cy - int(hu * 0.7),
                  cx - int(w * 0.2), cy - int(hu * 0.1)),
                 fill=shine2)


# ── Legs ──────────────────────────────────────────────────────────────────────

def _draw_legs_walking(draw, cx: int, hip_y: int, step_t: float):
    """2-segment walking legs.  Each leg lives permanently on its own side."""
    for side in (-1, 1):
        # Opposite phase so legs alternate
        phase = step_t if side == -1 else step_t + math.pi
        swing = math.sin(phase)          # -1 … +1  (forward = positive)

        # ── knee: always on its side, rises slightly when striding forward ──
        knee_x = cx + side * 18 + int(side * swing * 8)
        knee_y = hip_y + THIGH_L - max(0, int(swing * 14))

        # ── foot: further out and lifted when striding ──
        foot_x = cx + side * 28 + int(side * swing * 16)
        foot_y = GY - max(0, int(swing * 22))

        draw.line([(cx, hip_y), (knee_x, knee_y)], fill=INK, width=LINE_W)
        draw.line([(knee_x, knee_y), (foot_x, foot_y)], fill=INK, width=LINE_W - 1)
        draw.line([(foot_x - 6, foot_y), (foot_x + 10, foot_y)], fill=INK, width=4)


def _draw_legs_stand(draw, cx: int, hip_y: int):
    """Still standing legs."""
    for sign in (-1, 1):
        kx = cx + sign * 14
        ky = hip_y + THIGH_L
        fx = cx + sign * 26
        fy = GY
        draw.line([(cx, hip_y), (kx, ky)], fill=INK, width=LINE_W)
        draw.line([(kx, ky), (fx, fy)],    fill=INK, width=LINE_W - 1)
        draw.line([(fx - 6, fy), (fx + 10, fy)], fill=INK, width=4)


# ── Arms ──────────────────────────────────────────────────────────────────────

def _draw_arms_walking(draw, cx: int, sy: int, step_t: float):
    """Arms swing opposite to legs. Each arm stays on its own side."""
    for side in (-1, 1):
        # Arms opposite phase to same-side leg → use opposite of leg phase
        # Left leg phase = step_t  → left arm phase = step_t + π
        # Right leg phase = step_t + π → right arm phase = step_t
        phase = step_t + math.pi if side == -1 else step_t
        swing = math.sin(phase)  # -1 … +1

        # Elbow: always on its side, shifts slightly with swing
        ex = cx + side * 46 + int(side * swing * 12)
        ey = sy + 36 - int(swing * 10)

        # Hand: further out, follows elbow swing
        hx = ex + side * 12 + int(side * swing * 8)
        hy = ey + 34 + int(swing * 8)

        draw.line([(cx, sy), (ex, ey)], fill=INK, width=LINE_W)
        draw.line([(ex, ey), (hx, hy)], fill=INK, width=LINE_W - 1)


def _draw_arms_rest(draw, cx: int, sy: int):
    """Neutral hanging arms."""
    for sign in (-1, 1):
        ex, ey = cx + sign * 50, sy + 44
        hx, hy = ex + sign * 14, ey + 40
        draw.line([(cx, sy), (ex, ey)], fill=INK, width=LINE_W)
        draw.line([(ex, ey), (hx, hy)], fill=INK, width=LINE_W - 1)


def _draw_arms_hug(draw, cx: int, sy: int, other_cx: int,
                    facing_right: bool, hug_t: float):
    """
    Both arms embrace the partner.
    inner arm wraps around partner's back; outer arm also sweeps in.
    """
    inner = 1 if facing_right else -1      # sign pointing toward partner

    for arm_sign in (1, -1):
        is_inner = (arm_sign == inner)

        # Neutral elbow / hand positions
        ex_n = cx + arm_sign * 50
        ey_n = sy + 44
        hx_n = ex_n + arm_sign * 14
        hy_n = ey_n + 40

        if is_inner:
            # Elbow sweeps toward partner at hug
            mid_x  = (cx + other_cx) // 2
            ex_h   = int(_lerp(ex_n, mid_x, hug_t))
            ey_h   = int(_lerp(ey_n, sy + 18, hug_t))
            # Hand wraps to partner's back
            wrap_x = other_cx - inner * 30
            wrap_y = sy + BODY // 2 + 12
            hx_h   = int(_lerp(hx_n, wrap_x, hug_t))
            hy_h   = int(_lerp(hy_n, wrap_y, hug_t))
        else:
            # Outer arm: also reaches in (lower wrap)
            wrap_x = other_cx - inner * 20
            wrap_y = sy + BODY // 2 + 32
            ex_h   = int(_lerp(ex_n, cx + arm_sign * 46, hug_t))
            ey_h   = int(_lerp(ey_n, sy + 50, hug_t))
            hx_h   = int(_lerp(hx_n, wrap_x, hug_t * 0.75))
            hy_h   = int(_lerp(hy_n, wrap_y, hug_t * 0.75))

        draw.line([(cx, sy), (ex_h, ey_h)], fill=INK, width=LINE_W)
        draw.line([(ex_h, ey_h), (hx_h, hy_h)], fill=INK, width=LINE_W - 1)


# ─────────────────────────────────────────────────────────────────────────────
# Full character renderer
# ─────────────────────────────────────────────────────────────────────────────

def _draw_person(canvas: Image.Image, avatar: Image.Image,
                  cx: int, name: str, facing_right: bool,
                  phase: str, phase_t: float,
                  walk_step: float = 0.0, other_cx: int = 360,
                  head_lean: int = 0):
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Vertical body bob while walking
    bob = int(math.sin(walk_step * 2) * 5) if phase == 'walk' else 0

    hcy = HCY_BASE + bob      # head centre Y
    sy  = hcy + HR + 5         # shoulder Y
    hy  = sy + BODY            # hip Y

    # ── Legs ──────────────────────────────────────────────────────────────
    if phase == 'walk':
        _draw_legs_walking(draw, cx, hy, walk_step)
    else:
        _draw_legs_stand(draw, cx, hy)

    # ── Torso ─────────────────────────────────────────────────────────────
    draw.line([(cx, sy), (cx, hy)], fill=INK, width=LINE_W)

    # ── Arms ──────────────────────────────────────────────────────────────
    if phase == 'walk':
        _draw_arms_walking(draw, cx, sy, walk_step)
    elif phase == 'stop':
        _draw_arms_rest(draw, cx, sy)
    else:   # hug or kiss
        _draw_arms_hug(draw, cx, sy, other_cx, facing_right, phase_t)

    # ── Head (avatar circle) ───────────────────────────────────────────────
    av = _avatar_circle(avatar)
    if not facing_right:
        av = ImageOps.mirror(av)
    canvas.alpha_composite(av, (cx - HR + head_lean, hcy - HR))

    # Avatar ring
    draw.ellipse(
        (cx - HR - 4 + head_lean, hcy - HR - 4,
         cx + HR + 4 + head_lean, hcy + HR + 4),
        outline=INK, width=4,
    )

    # ── Lips (kiss phase only) ─────────────────────────────────────────────
    if phase == 'kiss':
        inner = 1 if facing_right else -1
        lip_cx = cx + head_lean + inner * int(HR * 0.20 * phase_t)
        lip_cy = hcy + int(HR * 0.52)
        _draw_lips(draw, lip_cx, lip_cy, scale=1.0 + phase_t * 0.35)

    # ── Name label ─────────────────────────────────────────────────────────
    nfont = _font(20, bold=True)
    b = draw.textbbox((0, 0), name, font=nfont)
    draw.text((cx - (b[2] - b[0]) // 2, GY + 5), name, font=nfont, fill=INK)


# ─────────────────────────────────────────────────────────────────────────────
# Main GIF renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_kiss_gif(
    first_avatar: Image.Image,
    second_avatar: Image.Image,
    first_name: str,
    second_name: str,
) -> io.BytesIO:
    """44-frame GIF: walk → stop → hug → kiss."""
    title_font = _font(30, bold=True)
    frames: list[Image.Image] = []

    for fi in range(N_FRAMES):
        canvas = Image.new("RGBA", (CW, CH), BG)
        draw   = ImageDraw.Draw(canvas, "RGBA")

        # Floating background bubbles
        for idx, (bx, by, br) in enumerate(((85, 80, 34), (640, 84, 40),
                                              (70, 378, 28), (656, 370, 33))):
            off = int(math.sin((fi + idx) / 2.5) * 5)
            draw.ellipse((bx - br, by - br + off, bx + br, by + br + off),
                         fill=(255, 218, 232, 140))
        _draw_sparkles(draw, fi)

        # Title
        _centered_text(draw, "A YSL love story", 24, title_font, PURPLE)

        # ── Resolve phase + per-character values ──────────────────────────
        lcx = EX_L
        rcx = EX_R
        phase      = 'stop'
        phase_t    = 0.0
        walk_step  = 0.0
        head_lean  = 0

        if fi < WALK_F:
            raw_t   = fi / (WALK_F - 1)
            t_ease  = _ease_out(raw_t)
            lcx     = int(_lerp(SX_L, EX_L, t_ease))
            rcx     = int(_lerp(SX_R, EX_R, t_ease))
            # ~3 complete stride cycles over the walk
            walk_step = raw_t * 3 * 2 * math.pi
            phase   = 'walk'
            phase_t = raw_t

        elif fi < WALK_F + STOP_F:
            phase   = 'stop'
            phase_t = (fi - WALK_F) / max(STOP_F - 1, 1)

        elif fi < WALK_F + STOP_F + HUG_F:
            ht      = _ease_out((fi - WALK_F - STOP_F) / (HUG_F - 1))
            phase   = 'hug'
            phase_t = ht
            # Step slightly closer during hug
            lcx     = int(_lerp(EX_L, KX_L, ht))
            rcx     = int(_lerp(EX_R, KX_R, ht))

        else:
            raw_k   = (fi - WALK_F - STOP_F - HUG_F) / (KISS_F - 1)
            kiss_t  = math.sin(math.pi * raw_k * 0.88)
            phase   = 'kiss'
            phase_t = max(0.0, min(1.0, kiss_t))
            lcx     = KX_L
            rcx     = KX_R
            head_lean = int(phase_t * 22)

        # ── Draw both characters ──────────────────────────────────────────
        _draw_person(canvas, first_avatar,
                     cx=lcx, name=first_name[:18],
                     facing_right=True,
                     phase=phase, phase_t=phase_t,
                     walk_step=walk_step, other_cx=rcx,
                     head_lean=head_lean)

        _draw_person(canvas, second_avatar,
                     cx=rcx, name=second_name[:18],
                     facing_right=False,
                     phase=phase, phase_t=phase_t,
                     walk_step=walk_step + math.pi,   # opposite stride phase
                     other_cx=lcx,
                     head_lean=-head_lean)

        # ── Hearts at kiss peak ───────────────────────────────────────────
        if phase == 'kiss' and phase_t > 0.52:
            hp  = (phase_t - 0.52) / 0.48
            mid = (lcx + rcx) // 2
            _draw_heart(draw, mid,       int(88 - hp * 22), 1.2, int(hp * 255))
            _draw_heart(draw, mid - 56,  118,               0.70, int(hp * 210))
            _draw_heart(draw, mid + 56,  118,               0.70, int(hp * 210))

        # Ground line
        draw.line([(30, GY + 2), (CW - 30, GY + 2)],
                  fill=(200, 185, 210, 160), width=2)

        frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE,
                                     dither=Image.Dither.NONE))

    buf = io.BytesIO()
    frames[0].save(
        buf, format="GIF", save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS, loop=0, optimize=False,
    )
    buf.seek(0)
    return buf
