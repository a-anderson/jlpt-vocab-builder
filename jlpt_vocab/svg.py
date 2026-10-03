"""Shared pitch accent diagram primitives — visual constants and the SVG emitter."""

MORA_W = 36          # horizontal spacing per mora (px)
PARTICLE_GAP = 12    # extra gap before particle dot (visual separator)
PADDING_X = 20       # left/right padding
DOT_R = 8            # dot radius
Y_HIGH = 16          # y centre for high dots
Y_LOW = 52           # y centre for low dots
SVG_HEIGHT = 72      # total SVG height
LINE_W = 4           # connecting line stroke width
CORNER_R = 8         # background corner radius
LABEL_Y = 84         # text baseline for kana labels under the dots
LABEL_SIZE = 17      # kana label font size — largest where two-char mora (きょきょ) don't touch
# Thin outline for a slightly heavier label; font-weight jumps Hiragino from W3 straight to W6
LABEL_STROKE = 0.4
LABEL_FONT = "'Hiragino Sans', 'Noto Sans JP', sans-serif"
SVG_HEIGHT_LABELLED = 94  # total SVG height with a kana label row
LABELLED_PADDING_X = 10   # tighter sides for labelled diagrams, closer to their top/bottom margin

COLOR_HIGH = "#E05A6A"
COLOR_LOW = "#4EC3E0"
COLOR_LINE = "#1A1A1A"


def pitch_levels(mora_count: int, rises: set[int], drops: set[int]) -> list[str]:
    """Walk the contour forward, returning one 'H'/'L' per mora."""
    for pos in rises | drops:
        if not 0 <= pos <= mora_count:
            raise ValueError(f'position {pos} is outside 0..{mora_count}')
    for pos in rises & drops:
        raise ValueError(f'rise and drop both given after mora {pos}')

    levels, level = [], 'L'
    for i in range(mora_count + 1):
        if i in rises:
            if level == 'H':
                raise ValueError(f'rise after mora {i} but the pitch is already high')
            level = 'H'
        if i in drops:
            if level == 'L':
                raise ValueError(f'drop after mora {i} but the pitch is already low')
            level = 'L'
        if i < mora_count:
            levels.append(level)
    return levels


def _trim_line(x1, y1, x2, y2, hollow1: bool, hollow2: bool) -> tuple:
    """Pull line ends back to the rim of hollow dots."""
    # A hollow dot has a transparent middle, so a centre-to-centre line would show
    # through it. DOT_R + 1 keeps the round cap inside the ring's stroke.
    trim = DOT_R + 1
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / length, dy / length
    if hollow1:
        x1, y1 = round(x1 + ux * trim, 2), round(y1 + uy * trim, 2)
    if hollow2:
        x2, y2 = round(x2 - ux * trim, 2), round(y2 - uy * trim, 2)
    return x1, y1, x2, y2


def background_rect(width: int, height: int, background: str | None) -> list[str]:
    """Return a rounded background rect element, or nothing when transparent."""
    if background is None:
        return []
    return [f'  <rect width="{width}" height="{height}" rx="{CORNER_R}" fill="{background}"/>']


def render_dots(
    dots: list[tuple[int, int, str, bool]], width: int, background: str | None = None,
    labels: list[str] | None = None,
) -> str:
    """Emit an SVG from (cx, cy, colour, hollow) dots, optionally labelled underneath."""
    lines = []
    for i in range(1, len(dots)):
        x1, y1, _, hollow1 = dots[i - 1]
        x2, y2, _, hollow2 = dots[i]
        lines.append(_trim_line(x1, y1, x2, y2, hollow1, hollow2))

    height = SVG_HEIGHT if labels is None else SVG_HEIGHT_LABELLED
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg"',
        f'     width="{width}" height="{height}"',
        f'     viewBox="0 0 {width} {height}">',
        *background_rect(width, height, background),
    ]

    # Lines behind dots
    for x1, y1, x2, y2 in lines:
        parts.append(
            f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
            f' stroke="{COLOR_LINE}" stroke-width="{LINE_W}"'
            f' stroke-linecap="round"/>'
        )

    # Dots — solid for word mora, hollow (background-filled) for particles
    hollow_fill = background or "none"
    for cx, cy, colour, hollow in dots:
        if hollow:
            parts.append(
                f'  <circle cx="{cx}" cy="{cy}" r="{DOT_R}"'
                f' fill="{hollow_fill}" stroke="{colour}" stroke-width="3"/>'
            )
        else:
            parts.append(
                f'  <circle cx="{cx}" cy="{cy}" r="{DOT_R}"'
                f' fill="{colour}" stroke="{COLOR_LINE}" stroke-width="2"/>'
            )

    for (cx, _, _, _), label in zip(dots, labels or []):
        parts.append(
            f'  <text x="{cx}" y="{LABEL_Y}" text-anchor="middle"'
            f' font-size="{LABEL_SIZE}" font-family="{LABEL_FONT}"'
            f' fill="{COLOR_LINE}" stroke="{COLOR_LINE}" stroke-width="{LABEL_STROKE}">'
            f'{label}</text>'
        )

    parts.append('</svg>')
    return "\n".join(parts)
