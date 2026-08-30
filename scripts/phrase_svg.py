"""
phrase_svg.py
=============
Generates a pitch accent SVG from a hand-specified contour, for phrases and
compound words whose pitch rises and falls more than once and so have no single
accent pattern number (e.g. 腹が立つ, 頭が上がらない, よろしくおねがいします).

Visually identical to the diagrams from generate_svgs.py — same colours, dot
radius, line weight and heights — but the contour is stated explicitly instead of
derived from a pattern number, and particles may sit anywhere in the phrase.

--rise and --drop both name the boundary AFTER a mora: `--drop 2` means the pitch
falls after the second mora. This is the same numbering as the accent pattern
used elsewhere in the project, so `--drop N` is exactly pattern N — `--rise 1
--drop 2` on 3 mora draws the same contour as 3_2.svg. `--rise 0` is the boundary
before the first mora, i.e. the phrase starts high (atamadaka).

The phrase starts low unless `--rise 0` is given. On a 4-mora word:

  heiban    LHHH   --rise 1
  atamadaka HLLL   --rise 0 --drop 1
  nakadaka  LHLL   --rise 1 --drop 2
  odaka     LHHH   --rise 1 --drop 4   (drops onto the following particle)

--particles is different: it names the mora themselves, 1-indexed, since a
particle is a mora rather than a boundary between two.

Output directory: output/pitch_svgs/
Filenames:        phrase_{mora}_r{rises}_d{drops}_p{particles}.svg
                  e.g. phrase_5_r1_d4_p3.svg, phrase_8_r1-5_d3_p3-8.svg

Usage:
  # 腹が立つ (はらがたつ) — rises after は, falls after た, が is the 3rd mora
  python scripts/phrase_svg.py --mora 5 --rise 1 --drop 4 --particles 3

  python scripts/phrase_svg.py --file phrases.txt
  python scripts/phrase_svg.py --mora 5 --rise 1 --drop 4 --out_dir output/my_svgs

Spec file format — one set of flags per line, blank lines and # comments skipped:

  # 腹が立つ / はらがたつ
  --mora 5 --rise 1 --drop 4 --particles 3
  --mora 8 --rise 1 5 --drop 3 --particles 3 8

For Anki: copy the generated SVGs into your collection.media folder and point the
row's ピッチアクセント図 field at the filename.
"""

import argparse
import shlex
from pathlib import Path

from jlpt_vocab.svg import (
    COLOR_HIGH, COLOR_LOW, MORA_W, PADDING_X, Y_HIGH, Y_LOW, render_dots,
)


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


def render_phrase_svg(
    mora_count: int, rises: set[int], drops: set[int], particles: set[int]
) -> str:
    """Generate SVG string for an explicitly specified pitch contour."""
    levels = pitch_levels(mora_count, rises, drops)
    for pos in particles:
        if not 1 <= pos <= mora_count:
            raise ValueError(f'particle {pos} is outside 1..{mora_count}')

    width = PADDING_X * 2 + mora_count * MORA_W
    dots = []
    for i, level in enumerate(levels):
        cx = PADDING_X + i * MORA_W + MORA_W // 2
        cy = Y_HIGH if level == 'H' else Y_LOW
        colour = COLOR_HIGH if level == 'H' else COLOR_LOW
        dots.append((cx, cy, colour, i + 1 in particles))

    return render_dots(dots, width)


def svg_name(
    mora_count: int, rises: set[int], drops: set[int], particles: set[int]
) -> str:
    """Return the filename for a contour, e.g. 'phrase_8_r2-6_d4_p3-8.svg'."""
    parts = [f'phrase_{mora_count}']
    for prefix, positions in (('r', rises), ('d', drops), ('p', particles)):
        if positions:
            parts.append(prefix + '-'.join(str(p) for p in sorted(positions)))
    return '_'.join(parts) + '.svg'


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Generate a pitch accent SVG from a stated contour')
    parser.add_argument('--mora', type=int, help='Total mora count in the phrase')
    parser.add_argument('--rise', type=int, nargs='*', default=[],
                        help='Rise after mora N; 0 means the phrase starts high')
    parser.add_argument('--drop', type=int, nargs='*', default=[],
                        help='Fall after mora N; same numbering as the accent pattern')
    parser.add_argument('--particles', type=int, nargs='*', default=[],
                        help='1-indexed mora to draw as hollow circles')
    parser.add_argument('--file', default=None,
                        help='Text file with one set of flags per line; # comments ignored')
    parser.add_argument('--out_dir', default='output/pitch_svgs', help='Output directory for SVGs')
    return parser


def read_specs(path: Path) -> list[argparse.Namespace]:
    """Parse one contour spec per line, skipping blank lines and # comments."""
    parser = _make_parser()
    specs = []
    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                specs.append(parser.parse_args(shlex.split(line)))
    return specs


def write_spec(spec: argparse.Namespace, out_dir: Path) -> None:
    rises, drops, particles = set(spec.rise), set(spec.drop), set(spec.particles)
    svg = render_phrase_svg(spec.mora, rises, drops, particles)
    name = svg_name(spec.mora, rises, drops, particles)
    (out_dir / name).write_text(svg, encoding='utf-8')
    print(f'{name}  {"".join(pitch_levels(spec.mora, rises, drops))}')


def main() -> None:
    args = _make_parser().parse_args()
    if (args.file is None) == (args.mora is None):
        raise SystemExit('Pass either --mora or --file, not both')

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = read_specs(Path(args.file)) if args.file else [args]
    for spec in specs:
        write_spec(spec, out_dir)

    print(f'\nWrote {len(specs)} SVG(s) to {out_dir}/')


if __name__ == '__main__':
    main()
