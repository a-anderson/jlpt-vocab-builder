"""Shared pitch accent diagram primitives — visual constants and the SVG emitter."""

MORA_W = 36          # horizontal spacing per mora (px)
PARTICLE_GAP = 12    # extra gap before particle dot (visual separator)
PADDING_X = 20       # left/right padding
DOT_R = 8            # dot radius
Y_HIGH = 16          # y centre for high dots
Y_LOW = 52           # y centre for low dots
SVG_HEIGHT = 72      # total SVG height
LINE_W = 4           # connecting line stroke width

COLOR_HIGH = "#E05A6A"
COLOR_LOW = "#4EC3E0"
COLOR_LINE = "#1A1A1A"


def render_dots(dots: list[tuple[int, int, str, bool]], width: int) -> str:
    """Emit an SVG from (cx, cy, colour, hollow) dots, joined by connecting lines."""
    lines = []
    for i in range(1, len(dots)):
        x1, y1, _, _ = dots[i - 1]
        x2, y2, _, _ = dots[i]
        lines.append((x1, y1, x2, y2))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg"',
        f'     width="{width}" height="{SVG_HEIGHT}"',
        f'     viewBox="0 0 {width} {SVG_HEIGHT}">',
    ]

    # Lines behind dots
    for x1, y1, x2, y2 in lines:
        parts.append(
            f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
            f' stroke="{COLOR_LINE}" stroke-width="{LINE_W}"'
            f' stroke-linecap="round"/>'
        )

    # Dots — solid for word mora, hollow (fill=white/transparent) for particles
    for cx, cy, colour, hollow in dots:
        if hollow:
            parts.append(
                f'  <circle cx="{cx}" cy="{cy}" r="{DOT_R}"'
                f' fill="white" stroke="{colour}" stroke-width="3"/>'
            )
        else:
            parts.append(
                f'  <circle cx="{cx}" cy="{cy}" r="{DOT_R}"'
                f' fill="{colour}" stroke="{COLOR_LINE}" stroke-width="2"/>'
            )

    parts.append('</svg>')
    return "\n".join(parts)
