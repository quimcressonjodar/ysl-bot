from typing import Any

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
