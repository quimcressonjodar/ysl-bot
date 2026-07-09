"""Generates an animated GIF of a horse race from pre-simulated position data,
plus a static final-results image."""

import io

from PIL import Image, ImageDraw, ImageFont

from config import HORSE_NAMES, HORSE_COLORS

WIDTH = 520
TRACK_TOP = 30
LANE_HEIGHT = 42
TRACK_LEFT = 90
TRACK_RIGHT = WIDTH - 40
FRAME_MS = 180
LAST_FRAME_MS = 2800


def _font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(name, size)
    except Exception:
        return ImageFont.load_default()


def _lighten(color, amount=40):
    return tuple(min(255, c + amount) for c in color)


def _darken(color, amount=40):
    return tuple(max(0, c - amount) for c in color)


def _draw_crown(draw: ImageDraw.ImageDraw, cx: int, top_y: int):
    """Hand-drawn gold crown icon (emoji glyphs render as tofu boxes with PIL fonts)."""
    gold = (255, 215, 0)
    w, h = 16, 10
    base = [(cx - w // 2, top_y + h), (cx + w // 2, top_y + h), (cx + w // 2, top_y + h + 4), (cx - w // 2, top_y + h + 4)]
    draw.polygon(base, fill=gold)
    points = [
        (cx - w // 2, top_y + h),
        (cx - w // 2, top_y + 2),
        (cx - w // 4, top_y + h - 2),
        (cx, top_y),
        (cx + w // 4, top_y + h - 2),
        (cx + w // 2, top_y + 2),
        (cx + w // 2, top_y + h),
    ]
    draw.polygon(points, fill=gold)
    for px, py in [(cx - w // 2, top_y + 2), (cx, top_y), (cx + w // 2, top_y + 2)]:
        draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(220, 30, 40))


def _draw_trophy(draw: ImageDraw.ImageDraw, cx: int, top_y: int):
    """Hand-drawn gold trophy icon for the winning horse."""
    gold = (255, 215, 0)
    cup_w = 14
    draw.rectangle([cx - 2, top_y + 10, cx + 2, top_y + 14], fill=gold)
    draw.rectangle([cx - 6, top_y + 14, cx + 6, top_y + 17], fill=gold)
    draw.pieslice([cx - cup_w // 2, top_y, cx + cup_w // 2, top_y + 14], 0, 180, fill=gold)
    draw.arc([cx - cup_w // 2 - 5, top_y, cx - cup_w // 2 + 3, top_y + 10], 90, 270, fill=gold, width=2)
    draw.arc([cx + cup_w // 2 - 3, top_y, cx + cup_w // 2 + 5, top_y + 10], -90, 90, fill=gold, width=2)


def _draw_medal(draw: ImageDraw.ImageDraw, cx: int, cy: int, rank: int, font):
    """Hand-drawn ranking medal (gold/silver/bronze) with its position number."""
    colors = {0: (255, 215, 0), 1: (192, 192, 192), 2: (205, 127, 50)}
    color = colors.get(rank, (120, 126, 136))
    r = 13
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=_darken(color, 60), width=2)
    text = str(rank + 1)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - bbox[1]), text, font=font, fill=(30, 30, 30))


def _draw_horse(draw: ImageDraw.ImageDraw, x: int, cy: int, color, tick: int, speed: int, leading: bool):
    """Draws a galloping horse (body/neck/head/mane/legs/tail), facing right."""
    stride = tick % 4
    leg_offsets = {
        0: (6, -6, 4, -4),
        1: (2, -2, 8, -8),
        2: (-6, 6, -4, 4),
        3: (-2, 2, -8, 8),
    }[stride]
    fl, bl, fr, br = leg_offsets

    body_top = cy - 8
    body_bottom = cy + 6
    body_left = x - 16
    body_right = x + 6

    # legs (drawn first, behind body)
    leg_color = _darken(color, 60)
    draw.line([(x - 10, body_bottom), (x - 10 + fl, body_bottom + 10)], fill=leg_color, width=3)
    draw.line([(x - 2, body_bottom), (x - 2 + bl, body_bottom + 10)], fill=leg_color, width=3)
    draw.line([(x + 2, body_bottom), (x + 2 + fr, body_bottom + 10)], fill=leg_color, width=3)
    draw.line([(x - 6, body_bottom), (x - 6 + br, body_bottom + 10)], fill=leg_color, width=3)

    # speed streaks behind a fast-moving horse
    if speed > 5:
        streak_color = _lighten(color, 60)
        for i, dy in enumerate((-6, 0, 6)):
            length = min(18, speed)
            draw.line(
                [(body_left - 4 - i * 5, cy + dy), (body_left - 4 - i * 5 - length, cy + dy)],
                fill=streak_color,
                width=2,
            )

    # tail
    draw.line([(body_left, cy - 4), (body_left - 10, cy - 10)], fill=color, width=4)
    draw.line([(body_left, cy - 2), (body_left - 9, cy + 2)], fill=color, width=3)

    # body
    draw.ellipse([body_left, body_top, body_right, body_bottom], fill=color)

    # neck + head (angled up-forward, galloping look)
    draw.polygon(
        [(body_right - 4, body_top + 2), (body_right + 10, body_top - 12), (body_right + 2, body_top + 6)],
        fill=color,
    )
    head_cx, head_cy = body_right + 12, body_top - 12
    draw.ellipse([head_cx - 6, head_cy - 5, head_cx + 6, head_cy + 5], fill=color)
    # ear + muzzle accent
    draw.polygon([(head_cx - 2, head_cy - 5), (head_cx + 1, head_cy - 11), (head_cx + 3, head_cy - 4)], fill=color)
    draw.ellipse([head_cx + 3, head_cy - 2, head_cx + 9, head_cy + 3], fill=_darken(color, 20))

    # mane
    draw.line([(body_right - 6, body_top - 2), (head_cx - 4, head_cy - 2)], fill=_darken(color, 50), width=3)

    if leading:
        _draw_crown(draw, head_cx, head_cy - 24)


def _draw_frame(positions: list[int], prev_positions: list[int] | None, distance: int, winner_idx: int | None) -> Image.Image:
    height = TRACK_TOP + LANE_HEIGHT * len(positions) + 24
    img = Image.new("RGB", (WIDTH, height), (24, 28, 35))
    draw = ImageDraw.Draw(img)
    label_font = _font(16)
    small_font = _font(13)

    # subtle diagonal track texture
    for stripe_x in range(TRACK_LEFT, TRACK_RIGHT, 24):
        draw.line([(stripe_x, TRACK_TOP), (stripe_x, height - 24)], fill=(29, 34, 42), width=10)

    for i in range(len(HORSE_NAMES)):
        lane_y = TRACK_TOP + i * LANE_HEIGHT
        draw.line([(0, lane_y), (WIDTH, lane_y)], fill=(55, 62, 74), width=1)
        draw.text((10, lane_y + LANE_HEIGHT // 2 - 8), str(i + 1), font=label_font, fill=(220, 220, 220))

    bottom_y = TRACK_TOP + LANE_HEIGHT * len(positions)
    draw.line([(0, bottom_y), (WIDTH, bottom_y)], fill=(55, 62, 74), width=1)

    # finish line (checkered)
    draw.rectangle([TRACK_RIGHT - 5, TRACK_TOP, TRACK_RIGHT + 5, bottom_y], fill=(255, 255, 255))
    for y in range(TRACK_TOP, bottom_y, 12):
        draw.rectangle([TRACK_RIGHT - 5, y, TRACK_RIGHT, y + 6], fill=(20, 20, 20))
    draw.text((TRACK_RIGHT - 20, 6), "FINISH", font=small_font, fill=(255, 255, 255))

    track_width = TRACK_RIGHT - TRACK_LEFT
    lead_pos = max(positions)
    for i, pos in enumerate(positions):
        lane_y = TRACK_TOP + i * LANE_HEIGHT
        frac = min(pos / distance, 1.0)
        x = TRACK_LEFT + int(frac * track_width)
        cy = lane_y + LANE_HEIGHT // 2 + 4
        color = HORSE_COLORS[i % len(HORSE_COLORS)]
        prev = prev_positions[i] if prev_positions else pos
        speed = pos - prev
        leading = pos == lead_pos and winner_idx is None

        _draw_horse(draw, min(x, TRACK_RIGHT - 4), cy, color, pos, speed, leading)

        if winner_idx == i:
            _draw_trophy(draw, min(x, TRACK_RIGHT - 4) + 10, cy - 34)

    return img


def generate_race_gif(positions_history: list[list[int]], distance: int, winner_idx: int) -> io.BytesIO:
    """Build an animated GIF from a list of per-tick horse positions.

    `positions_history` is a list of frames; each frame is a list with one
    position (0..distance) per horse. The final frame is held longer and
    marks the winning horse.
    """
    frames = []
    for tick, positions in enumerate(positions_history):
        is_last = tick == len(positions_history) - 1
        prev = positions_history[tick - 1] if tick > 0 else None
        frames.append(_draw_frame(positions, prev, distance, winner_idx if is_last else None))

    buffer = io.BytesIO()
    durations = [FRAME_MS] * (len(frames) - 1) + [LAST_FRAME_MS]
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
    )
    buffer.seek(0)
    return buffer


def generate_result_image(final_positions: list[int], distance: int, winner_idx: int) -> io.BytesIO:
    """Static podium-style image showing the final standings."""
    ranking = sorted(range(len(final_positions)), key=lambda i: final_positions[i], reverse=True)

    row_h = 46
    height = 60 + row_h * len(ranking) + 20
    img = Image.new("RGB", (WIDTH, height), (24, 28, 35))
    draw = ImageDraw.Draw(img)
    title_font = _font(22)
    row_font = _font(16)

    draw.text((WIDTH // 2 - 100, 16), "FINAL RESULTS", font=title_font, fill=(255, 215, 0))

    track_width = WIDTH - 220
    for rank, idx in enumerate(ranking):
        y = 60 + rank * row_h
        color = HORSE_COLORS[idx % len(HORSE_COLORS)]
        if rank < 3:
            _draw_medal(draw, 26, y + 20, rank, row_font)
        else:
            draw.text((16, y + 8), f"{rank + 1}.", font=row_font, fill=(230, 230, 230))
        name_color = (255, 215, 0) if idx == winner_idx else color
        draw.text((60, y + 8), HORSE_NAMES[idx], font=row_font, fill=name_color)

        bar_x = 190
        frac = min(final_positions[idx] / distance, 1.0)
        draw.rounded_rectangle([bar_x, y + 6, bar_x + track_width, y + 30], radius=6, fill=(40, 46, 56))
        draw.rounded_rectangle(
            [bar_x, y + 6, bar_x + max(10, int(track_width * frac)), y + 30], radius=6, fill=color
        )

        if rank == 0:
            draw.rectangle([bar_x - 6, y, bar_x - 2, y + 36], fill=(255, 215, 0))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
