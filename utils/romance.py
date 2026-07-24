"""Small, self-contained helpers for the bot's romance commands."""

from __future__ import annotations

import hashlib
import io
import math

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS_SIZE = (720, 480)
AVATAR_SIZE = 150
FRAME_COUNT = 14
FRAME_DURATION_MS = 120


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


async def download_avatar(session: aiohttp.ClientSession, url: str) -> Image.Image:
    """Download and decode an avatar, rejecting oversized responses."""
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > 5_000_000:
            raise ValueError("avatar is too large")
        data = await response.content.read(5_000_000)
        if len(data) >= 5_000_000:
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


def _draw_stick_person(
    canvas: Image.Image,
    avatar: Image.Image,
    center_x: int,
    name: str,
    lean: int,
    flip_avatar: bool = False,
):
    draw = ImageDraw.Draw(canvas, "RGBA")
    head_x = center_x + lean
    head_y = 245
    if flip_avatar:
        avatar = ImageOps.mirror(avatar)
    canvas.alpha_composite(_avatar_circle(avatar), (head_x - AVATAR_SIZE // 2, head_y - AVATAR_SIZE // 2))

    # A simple illustrated body keeps the avatars as the focus.
    ink = (36, 29, 60, 255)
    draw.ellipse(
        (head_x - AVATAR_SIZE // 2 - 5, head_y - AVATAR_SIZE // 2 - 5,
         head_x + AVATAR_SIZE // 2 + 5, head_y + AVATAR_SIZE // 2 + 5),
        outline=ink,
        width=5,
    )
    shoulder_y = head_y + AVATAR_SIZE // 2 + 7
    hip_y = shoulder_y + 94
    draw.line((head_x, shoulder_y, head_x, hip_y), fill=ink, width=7)
    draw.line((head_x, shoulder_y + 16, head_x - 67, shoulder_y + 54), fill=ink, width=7)
    draw.line((head_x, shoulder_y + 16, head_x + 67, shoulder_y + 54), fill=ink, width=7)
    draw.line((head_x, hip_y, head_x - 44, hip_y + 79), fill=ink, width=7)
    draw.line((head_x, hip_y, head_x + 44, hip_y + 79), fill=ink, width=7)

    label_font = _font(21, bold=True)
    bounds = draw.textbbox((0, 0), name, font=label_font)
    label_width = bounds[2] - bounds[0]
    draw.text((head_x - label_width // 2, hip_y + 86), name, font=label_font, fill=ink)


def render_kiss_gif(first_avatar: Image.Image, second_avatar: Image.Image, first_name: str, second_name: str) -> io.BytesIO:
    """Render a short illustrated kiss animation using two Discord avatars."""
    frames: list[Image.Image] = []
    for tick in range(FRAME_COUNT):
        canvas = Image.new("RGBA", CANVAS_SIZE, (255, 247, 251, 255))
        draw = ImageDraw.Draw(canvas, "RGBA")

        # Soft background bubbles add motion without requiring generated assets.
        for index, (x, y, radius) in enumerate(((80, 72, 35), (645, 76, 40), (68, 414, 28), (654, 407, 31))):
            offset = int(math.sin((tick + index) / 2) * 5)
            draw.ellipse((x - radius, y - radius + offset, x + radius, y + radius + offset), fill=(255, 220, 235, 150))
        _draw_sparkles(draw, tick)
        _centered_text(draw, "A YSL love story", 26, _font(30, bold=True), (91, 44, 102, 255))

        # The characters move together for the kiss, then bounce apart slightly.
        kiss_progress = math.sin(math.pi * tick / (FRAME_COUNT - 1))
        gap = int(168 - kiss_progress * 56)
        _draw_stick_person(canvas, first_avatar, CANVAS_SIZE[0] // 2 - gap, first_name[:18], int(kiss_progress * 10))
        _draw_stick_person(canvas, second_avatar, CANVAS_SIZE[0] // 2 + gap, second_name[:18], -int(kiss_progress * 10), flip_avatar=True)

        if kiss_progress > 0.72:
            _draw_heart(draw, CANVAS_SIZE[0] // 2, 137 - int(kiss_progress * 10), 1.1, (236, 73, 123, 255))
            _draw_heart(draw, CANVAS_SIZE[0] // 2 - 48, 165, 0.55, (255, 132, 169, 230))
            _draw_heart(draw, CANVAS_SIZE[0] // 2 + 48, 165, 0.55, (255, 132, 169, 230))

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