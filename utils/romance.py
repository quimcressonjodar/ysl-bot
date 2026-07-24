"""Small, self-contained helpers for the bot's romance commands."""

from __future__ import annotations

import hashlib
import io
import math

from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS_SIZE = (720, 480)
AVATAR_SIZE = 150
FRAME_COUNT = 22
FRAME_DURATION_MS = 80

# Vertical positions
HEAD_Y = 235
_SHOULDER_OFFSET = AVATAR_SIZE // 2 + 8   # below avatar bottom edge
_BODY_HEIGHT = 90
_LEG_HEIGHT = 80


def love_score(first_id: int, second_id: int) -> int:
    """Return a stable, playful compatibility score for a pair of users."""
    pair = ":".join(str(value) for value in sorted((first_id, second_id)))
    digest = hashlib.sha256(pair.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % 101


def love_verdict(score: int) -> str:
    if score >= 95:
        return "The stars are screaming yes."
    if score >= 80:
        return "There is definitely something special here."
    if score >= 60:
        return "The chemistry is looking promising."
    if score >= 40:
        return "There is potential, but someone has to make the first move."
    if score >= 20:
        return "The spark is shy today."
    return "The cosmic timing is not on your side yet."


def decode_avatar(data: bytes) -> Image.Image:
    """Decode avatar bytes returned by discord.py's Asset.read()."""
    if len(data) > 5_000_000:
        raise ValueError("avatar is too large")
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGBA")


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    try:
        filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(filename, size)
    except OSError:
        return ImageFont.load_default()


def _avatar_circle(avatar: Image.Image) -> Image.Image:
    avatar = ImageOps.fit(avatar, (AVATAR_SIZE, AVATAR_SIZE), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=255)
    avatar.putalpha(mask)
    return avatar


def _centered_text(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont, fill):
    bounds = draw.textbbox((0, 0), text, font=font)
    x = (CANVAS_SIZE[0] - (bounds[2] - bounds[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _draw_heart(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, scale: float, fill):
    radius = int(17 * scale)
    top = center_y - radius // 2
    draw.ellipse((center_x - radius, top, center_x, top + radius), fill=fill)
    draw.ellipse((center_x, top, center_x + radius, top + radius), fill=fill)
    draw.polygon(
        [
            (center_x - radius, top + radius // 2),
            (center_x + radius, top + radius // 2),
            (center_x, top + radius * 2),
        ],
        fill=fill,
    )


def _draw_sparkles(draw: ImageDraw.ImageDraw, tick: int):
    sparkle_color = (255, 232, 145, 230)
    for index, (x, y) in enumerate(((112, 118), (604, 128), (90, 310), (638, 326))):
        size = 7 + ((tick + index * 3) % 4)
        draw.line((x - size, y, x + size, y), fill=sparkle_color, width=3)
        draw.line((x, y - size, x, y + size), fill=sparkle_color, width=3)


def _draw_lips(draw: ImageDraw.ImageDraw, head_x: int, head_y: int, kiss_progress: float):
    """Draw visible lips near the chin of the avatar.

    They puff and glow as the characters lean in for the kiss.
    """
    lip_color = (220, 48, 78, 255)
    # Highlight: lighter pink for the lower lip shine
    shine_color = (255, 150, 175, 200)

    # Lips sit at the bottom quarter of the face circle
    cx = head_x
    cy = head_y + int(AVATAR_SIZE * 0.34)

    # Swell slightly as kiss approaches
    w = int(19 + kiss_progress * 5)
    h_upper = int(7 + kiss_progress * 2)
    h_lower = int(9 + kiss_progress * 3)

    # Upper lip: two lobes (cupid's bow)
    draw.ellipse((cx - w, cy - h_upper, cx - 2, cy + 2), fill=lip_color)
    draw.ellipse((cx + 2, cy - h_upper, cx + w, cy + 2), fill=lip_color)
    # Thin central dip (cupid's bow peak) — draw a white triangle to carve the middle
    draw.polygon(
        [(cx - 5, cy - h_upper + 1), (cx + 5, cy - h_upper + 1), (cx, cy - 1)],
        fill=(255, 247, 251, 255),
    )

    # Lower lip
    draw.ellipse((cx - w + 2, cy, cx + w - 2, cy + h_lower * 2), fill=lip_color)
    # Shine on lower lip
    draw.ellipse((cx - w // 3, cy + 2, cx + w // 3, cy + h_lower), fill=shine_color)


def _draw_stick_person(
    canvas: Image.Image,
    avatar: Image.Image,
    center_x: int,
    name: str,
    lean: int,
    flip_avatar: bool = False,
    kiss_progress: float = 0.0,
):
    """Draw a stick person with avatar head, lips, and body."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    head_x = center_x + lean
    head_y = HEAD_Y

    if flip_avatar:
        avatar = ImageOps.mirror(avatar)
    canvas.alpha_composite(_avatar_circle(avatar), (head_x - AVATAR_SIZE // 2, head_y - AVATAR_SIZE // 2))

    # Draw lips on top of the avatar (overlaid on the face)
    _draw_lips(draw, head_x, head_y, kiss_progress)

    ink = (36, 29, 60, 255)

    # Avatar ring
    draw.ellipse(
        (
            head_x - AVATAR_SIZE // 2 - 5,
            head_y - AVATAR_SIZE // 2 - 5,
            head_x + AVATAR_SIZE // 2 + 5,
            head_y + AVATAR_SIZE // 2 + 5,
        ),
        outline=ink,
        width=5,
    )

    shoulder_y = head_y + _SHOULDER_OFFSET
    hip_y = shoulder_y + _BODY_HEIGHT

    # Torso
    draw.line((head_x, shoulder_y, head_x, hip_y), fill=ink, width=7)

    # Legs (always the same)
    draw.line((head_x, hip_y, head_x - 44, hip_y + _LEG_HEIGHT), fill=ink, width=7)
    draw.line((head_x, hip_y, head_x + 44, hip_y + _LEG_HEIGHT), fill=ink, width=7)

    # Outer arm: points away from the partner (static)
    outer_dir = 1 if flip_avatar else -1
    draw.line(
        (head_x, shoulder_y + 16, head_x + outer_dir * 67, shoulder_y + 54),
        fill=ink,
        width=7,
    )

    # Name label
    label_font = _font(21, bold=True)
    bounds = draw.textbbox((0, 0), name, font=label_font)
    label_width = bounds[2] - bounds[0]
    draw.text((head_x - label_width // 2, hip_y + _LEG_HEIGHT + 4), name, font=label_font, fill=ink)


def _draw_hug_arms(
    canvas: Image.Image,
    left_center_x: int,
    right_center_x: int,
    left_lean: int,
    right_lean: int,
    hug_progress: float,
):
    """Draw the inner hugging arms that wrap around the partner.

    Called after both stick persons are rendered so the hug arms sit on top.
    hug_progress goes 0 → 1 as the characters lean in.
    """
    if hug_progress <= 0:
        return

    draw = ImageDraw.Draw(canvas, "RGBA")
    ink = (36, 29, 60, 255)

    shoulder_y = HEAD_Y + _SHOULDER_OFFSET
    hip_y = shoulder_y + _BODY_HEIGHT

    lx = left_center_x + left_lean    # left person head X
    rx = right_center_x + right_lean  # right person head X

    # Shoulder attachment point (slightly inward from each torso)
    l_shoulder = (lx, shoulder_y + 16)
    r_shoulder = (rx, shoulder_y + 16)

    # Target: each arm wraps to the other's back (mid-torso, opposite side)
    l_arm_wrap_target = (rx + 18, shoulder_y + 40)   # left arm reaches right person's back
    r_arm_wrap_target = (lx - 18, shoulder_y + 40)   # right arm reaches left person's back

    # Normal (non-hug) arm endpoint — pointing inward/down
    l_arm_normal = (lx + 67, shoulder_y + 54)
    r_arm_normal = (rx - 67, shoulder_y + 54)

    # Interpolate between normal and hug position
    def lerp(a, b, t):
        return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t))

    l_arm_end = lerp(l_arm_normal, l_arm_wrap_target, hug_progress)
    r_arm_end = lerp(r_arm_normal, r_arm_wrap_target, hug_progress)

    # Draw the hugging arm for the left person (right arm, facing right)
    # We draw two segments: shoulder → elbow → wrap endpoint for a bent look
    l_elbow = lerp(
        (lx + 35, shoulder_y + 30),       # normal elbow
        (lx + (rx - lx) // 2, shoulder_y + 10),  # elbow arcing up for hug
        hug_progress,
    )
    draw.line((l_shoulder[0], l_shoulder[1], l_elbow[0], l_elbow[1]), fill=ink, width=7)
    draw.line((l_elbow[0], l_elbow[1], l_arm_end[0], l_arm_end[1]), fill=ink, width=7)

    # Draw the hugging arm for the right person (left arm, facing left)
    r_elbow = lerp(
        (rx - 35, shoulder_y + 30),
        (rx - (rx - lx) // 2, shoulder_y + 10),
        hug_progress,
    )
    draw.line((r_shoulder[0], r_shoulder[1], r_elbow[0], r_elbow[1]), fill=ink, width=7)
    draw.line((r_elbow[0], r_elbow[1], r_arm_end[0], r_arm_end[1]), fill=ink, width=7)

    # Optional: small hand dots at wrap endpoints
    hand_r = 6
    for pt in (l_arm_end, r_arm_end):
        draw.ellipse(
            (pt[0] - hand_r, pt[1] - hand_r, pt[0] + hand_r, pt[1] + hand_r),
            fill=ink,
        )


def render_kiss_gif(
    first_avatar: Image.Image,
    second_avatar: Image.Image,
    first_name: str,
    second_name: str,
) -> io.BytesIO:
    """Render a short illustrated kiss animation using two Discord avatars.

    Characters approach each other, show lips, and hug with crossed arms.
    """
    frames: list[Image.Image] = []
    center = CANVAS_SIZE[0] // 2

    for tick in range(FRAME_COUNT):
        canvas = Image.new("RGBA", CANVAS_SIZE, (255, 247, 251, 255))
        draw = ImageDraw.Draw(canvas, "RGBA")

        # Soft background bubbles
        for index, (x, y, radius) in enumerate(((80, 72, 35), (645, 76, 40), (68, 414, 28), (654, 407, 31))):
            offset = int(math.sin((tick + index) / 2) * 5)
            draw.ellipse(
                (x - radius, y - radius + offset, x + radius, y + radius + offset),
                fill=(255, 220, 235, 150),
            )
        _draw_sparkles(draw, tick)
        _centered_text(draw, "A YSL love story", 26, _font(30, bold=True), (91, 44, 102, 255))

        # Smooth sine approach: characters close in, hold, then ease back slightly
        raw_t = tick / (FRAME_COUNT - 1)          # 0 → 1
        # Ease-in-out: spend more frames near the peak
        kiss_progress = math.sin(math.pi * raw_t)  # 0 → 1 → 0

        # Gap shrinks from 168 px to 60 px at peak
        gap = int(168 - kiss_progress * 108)

        left_center = center - gap
        right_center = center + gap

        left_lean = int(kiss_progress * 12)    # leans right
        right_lean = -int(kiss_progress * 12)  # leans left

        # Hug arms kick in past 40 % progress
        hug_progress = max(0.0, (kiss_progress - 0.4) / 0.6)

        # Draw bodies (outer arms included inside)
        _draw_stick_person(canvas, first_avatar, left_center, first_name[:18], left_lean, kiss_progress=kiss_progress)
        _draw_stick_person(canvas, second_avatar, right_center, second_name[:18], right_lean, flip_avatar=True, kiss_progress=kiss_progress)

        # Draw hugging arms on top
        _draw_hug_arms(canvas, left_center, right_center, left_lean, right_lean, hug_progress)

        # Hearts appear near the peak
        if kiss_progress > 0.65:
            intensity = (kiss_progress - 0.65) / 0.35
            _draw_heart(draw, center, int(125 - intensity * 14), 1.1 + intensity * 0.2, (236, 73, 123, 255))
            _draw_heart(draw, center - 52, 162, 0.55 + intensity * 0.1, (255, 132, 169, 230))
            _draw_heart(draw, center + 52, 162, 0.55 + intensity * 0.1, (255, 132, 169, 230))

        frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
    )
    output.seek(0)
    return output
