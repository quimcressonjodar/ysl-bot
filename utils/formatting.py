from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None


def format_table(rows: list[list[Any]], headers: list[str]) -> str:
    if tabulate:
        return tabulate(rows, headers=headers, tablefmt="github")

    widths = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    def fmt_line(values: list[Any]) -> str:
        cells = [str(v).ljust(widths[i]) for i, v in enumerate(values)]
        return "| " + " | ".join(cells) + " |"

    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    lines = [fmt_line(headers), sep]
    lines.extend(fmt_line(row) for row in rows)
    return "\n".join(lines)


def generate_top_clans_image(clans: list[dict], page: int = 0, per_page: int = 10) -> str:
    width, height = 1000, 850
    img = Image.new("RGB", (width, height), (30, 31, 34))
    draw = ImageDraw.Draw(img)

    try:
        font_normal = ImageFont.truetype("arial.ttf", 32)
        font_bold = ImageFont.truetype("arialbd.ttf", 32)
        font_title = ImageFont.truetype("arialbd.ttf", 52)
        font_header = ImageFont.truetype("arialbd.ttf", 34)
    except Exception:
        font_normal = ImageFont.load_default()
        font_bold = font_normal
        font_title = font_normal
        font_header = font_normal

    start = page * per_page
    sliced = clans[start:start + per_page]

    draw.text((40, 40), "🏆 GLOBAL LEADERBOARD", fill=(255, 255, 255), font=font_title)
    page_text = f"PAGE {page + 1} / {max(1, (len(clans) // per_page) + 1)}"
    draw.text((width - 250, 55), page_text, fill=(150, 150, 150), font=font_bold)

    y_offset = 140
    cols = [40, 150, 540, 800]
    headers = ["RANK", "CLAN", "EXPERIENCE", "USERS"]

    draw.rectangle([(20, y_offset), (width - 20, y_offset + 70)], fill=(43, 45, 49))
    for x, text in zip(cols, headers):
        draw.text((x, y_offset + 15), text, fill=(88, 101, 242), font=font_header)

    y_offset += 100
    rank = start + 1

    for c in sliced:
        name = c.get("name", "Unknown")
        scores = c.get("scores", 0)
        members = c.get("membersCount", 0)
        is_my_clan = name.lower() == "ysl!"

        if is_my_clan:
            text_color = (255, 215, 0)
            draw.rectangle(
                [(20, y_offset - 10), (width - 20, y_offset + 55)],
                fill=(49, 51, 56), outline=(255, 215, 0), width=3,
            )
            current_font = font_bold
        else:
            text_color = (220, 221, 222)
            current_font = font_normal

        draw.text((cols[0], y_offset), f"#{rank}", fill=text_color, font=current_font)
        draw.text((cols[1], y_offset), name, fill=text_color, font=current_font)
        draw.text((cols[2], y_offset), f"{scores:,} XP", fill=text_color, font=current_font)
        draw.text((cols[3], y_offset), f"{members}", fill=text_color, font=current_font)

        y_offset += 65
        rank += 1

    draw.rectangle([(20, height - 20), (width - 20, height - 15)], fill=(88, 101, 242))

    path = f"top_clans_page_{page}.png"
    img.save(path)
    return path
