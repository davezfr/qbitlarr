from __future__ import annotations

from app.domain.quality import parse_quality
from app.models import ManualSearchResult

SEEDERS_EMOJI = "🧲"
SIZE_EMOJI = "💾"
MISSING = "—"
DEFAULT_RESOLUTION = "1080p"


def render_choice_table(results: list[ManualSearchResult]) -> str:
    """Render an aligned monospace choice table for identity-certain result lists.

    Designed for Telegram <pre> blocks: every row places the same emojis at the
    same column, so the rows stay vertically aligned despite emoji width
    varying between platforms. The recommended choice is conveyed by the
    starred clarify button, not by an extra glyph in the table.
    """
    if not results:
        return ""

    rows = []
    for result in results:
        parsed = parse_quality(result.title)
        source = "REMUX" if parsed.is_remux and parsed.source in {None, "BluRay"} else (parsed.source or MISSING)
        rows.append(
            {
                "index": result.index,
                "resolution": parsed.resolution,
                "source": source,
                "codec": parsed.codec or MISSING,
                "seeders": str(result.seeders) if result.seeders is not None else MISSING,
                "size": _compact_size(result.size),
            }
        )

    show_resolution = any(r["resolution"] and r["resolution"] != DEFAULT_RESOLUTION for r in rows)
    source_width = max(len(r["source"]) for r in rows)
    codec_width = max(len(r["codec"]) for r in rows)
    seeders_width = max(len(r["seeders"]) for r in rows)
    size_width = max(len(r["size"]) for r in rows)

    lines = []
    for row in rows:
        parts = [f"{row['index']}."]
        if show_resolution:
            parts.append((row["resolution"] or MISSING).rjust(5))
        parts.append(row["source"].ljust(source_width))
        parts.append(_center(row["codec"], codec_width))
        parts.append(f"{SEEDERS_EMOJI} {row['seeders'].rjust(seeders_width)}")
        parts.append(f"{SIZE_EMOJI} {row['size'].rjust(size_width)}")
        lines.append("  ".join(parts))
    return "\n".join(lines)


def _center(value: str, width: int) -> str:
    return value.center(width)


def _compact_size(size: int | None) -> str:
    if size is None or size <= 0:
        return MISSING
    value = float(size)
    units = ("B", "KB", "MB", "GB", "TB")
    unit_index = 0
    while abs(value) >= 1000 and unit_index < len(units) - 1:
        value /= 1000
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)}B"
    formatted = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}{units[unit_index]}"
