"""Generates an animated GIF of a horse race from pre-simulated position data."""

import io

from PIL import Image, ImageDraw, ImageFont

from config import HORSE_NAMES, HORSE_COLORS

WIDTH = 520
TRACK_TOP = 30
LANE_HEIGHT = 40
TRACK_LEFT = 90
TRACK_RIGHT = WIDTH - 40
FRAME_MS = 250
LAST_FRAME_MS = 2500


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _draw_frame(positions: list[int], distance: int, winner_idx: int | None) -> Image.Image:
    height = TRACK_TOP + LANE_HEIGHT * len(positions) + 20
    img = Image.new("RGB", (WIDTH, height), (34, 40, 49))
    draw = ImageDraw.Draw(img)
    label_font = _font(16)
    small_font = _font(14)

    for i, name in enumerate(HORSE_NAMES):
        lane_y = TRACK_TOP + i * LANE_HEIGHT
        # lane separator
        draw.line([(0, lane_y), (WIDTH, lane_y)], fill=(55, 62, 74), width=1)
        # lane label
        draw.text((10, lane_y + LANE_HEIGHT // 2 - 8), str(i + 1), font=label_font, fill=(220, 220, 220))

    bottom_y = TRACK_TOP + LANE_HEIGHT * len(positions)
    draw.line([(0, bottom_y), (WIDTH, bottom_y)], fill=(55, 62, 74), width=1)

    # finish line
    draw.line(
        [(TRACK_RIGHT, TRACK_TOP), (TRACK_RIGHT, bottom_y)],
        fill=(255, 255, 255),
        width=3,
    )
    for y in range(TRACK_TOP, bottom_y, 12):
        draw.rectangle([TRACK_RIGHT - 4, y, TRACK_RIGHT + 4, y + 6], fill=(0, 0, 0))
    draw.text((TRACK_RIGHT - 18, 6), "FINISH", font=small_font, fill=(255, 255, 255))

    track_width = TRACK_RIGHT - TRACK_LEFT
    for i, pos in enumerate(positions):
        lane_y = TRACK_TOP + i * LANE_HEIGHT
        frac = min(pos / distance, 1.0)
        x = TRACK_LEFT + int(frac * track_width)
        cy = lane_y + LANE_HEIGHT // 2
        color = HORSE_COLORS[i % len(HORSE_COLORS)]

        # simple stylized horse: body + head + legs
        draw.ellipse([x - 14, cy - 8, x + 10, cy + 8], fill=color)
        draw.polygon([(x + 8, cy - 10), (x + 20, cy - 4), (x + 8, cy + 2)], fill=color)
        draw.line([(x - 8, cy + 8), (x - 10, cy + 16)], fill=color, width=3)
        draw.line([(x + 2, cy + 8), (x, cy + 16)], fill=color, width=3)

        if winner_idx == i:
            draw.text((x - 6, cy - 26), "🏆", font=small_font, fill=(255, 215, 0))

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
        frames.append(_draw_frame(positions, distance, winner_idx if is_last else None))

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
