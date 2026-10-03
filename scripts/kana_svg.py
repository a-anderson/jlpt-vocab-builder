"""
kana_svg.py
===========
Generates pitch accent SVGs with the kana of each mora written under its dot, from
a compact kana notation — for conjugated forms and phrases copied from a lesson
(e.g. たべま＼した, た＼べて, はし＼[が]), not just dictionary forms.

Same dots, colours and line weights as generate_svgs.py and phrase_svg.py.

Notation:

  ＼ or \\    pitch falls after the preceding mora
  ／ or /    pitch rises after the preceding mora; at the very start = starts high
  [...]      particle mora, drawn as hollow dots
  space      ignored — for readability only

The line starts low and rises after the first mora, unless the first mora is
followed by ＼ (atamadaka — starts high). If the first marker in the line is a ／,
that is the first rise instead and nothing is added. Nothing else is inferred:
Japanese has no word spaces, and the contour across a word boundary depends on the
neighbouring words (heiban + heiban stays flat), so later rises are always written.

Compound kana (きょ, しゃ, ティ, ファ …) are one mora — one dot, one label.

  たべま＼した                    LHHLL
  た＼べて                        HLL
  はし＼[が]                      LHL
  あたま[が]あがらない             LHHHHHHHH
  よろし＼く お／ねがいしま＼す     LHHLLHHHHHL

Output directory: output/pitch_svgs/
Filenames:        {kana}_r{rises}_d{drops}_p{particles}.svg  (empty sections omitted)
                  e.g. たべました_r1_d3.svg, はしが_r1_d2_p3.svg

Usage (quote each notation — [ and \\ are special to the shell):
  python scripts/kana_svg.py 'たべま＼した' 'はし＼[が]'
  python scripts/kana_svg.py --file examples.txt --background white

Example file format — one notation per line, blank lines and # comments skipped:

  # 食べる
  たべ＼る
  たべま＼した
"""

import argparse
import unicodedata
from pathlib import Path

from jlpt_vocab.pitch_accent import split_mora
from jlpt_vocab.svg import (
    COLOR_HIGH, COLOR_LOW, MORA_W, LABELLED_PADDING_X, Y_HIGH, Y_LOW, pitch_levels, render_dots,
)

DROP, RISE = '＼', '／'
SMALL_KANA = set('ぁぃぅぇぉゃゅょァィゥェォャュョ')


def _is_kana(ch: str) -> bool:
    return 'ぁ' <= ch <= 'ゖ' or 'ァ' <= ch <= 'ヺ' or ch == 'ー'


def parse_notation(line: str) -> tuple[list[str], list[str], set[int]]:
    """Parse a notation line into (mora, levels, 1-indexed particle positions)."""
    line = unicodedata.normalize('NFC', line).replace('\\', DROP).replace('/', RISE)
    mora, particles, rises, drops = [], set(), set(), set()
    run, in_particle, first_marker = '', False, None

    def flush():
        nonlocal run
        if run and run[0] in SMALL_KANA and mora:
            raise ValueError(f'{run[0]!r} is split from its mora by a marker in {line!r}')
        for m in split_mora(run):
            mora.append(m)
            if in_particle:
                particles.add(len(mora))
        run = ''

    for ch in line:
        if ch in ' 　':
            continue
        if _is_kana(ch):
            run += ch
            continue
        flush()
        if ch in (DROP, RISE) and first_marker is None:
            first_marker = ch
        if ch == DROP:
            drops.add(len(mora))
        elif ch == RISE:
            rises.add(len(mora))
        elif ch == '[' and not in_particle:
            in_particle = True
        elif ch == ']' and in_particle:
            in_particle = False
        elif ch in '[]':
            raise ValueError(f'unbalanced [ ] in {line!r}')
        else:
            raise ValueError(f'unexpected character {ch!r} in {line!r}')
    flush()

    if in_particle:
        raise ValueError(f'unbalanced [ ] in {line!r}')
    if not mora:
        raise ValueError(f'no kana in {line!r}')
    if first_marker != RISE:
        if 1 in drops:
            rises.add(0)
        elif len(mora) > 1:
            rises.add(1)

    return mora, pitch_levels(len(mora), rises, drops), particles


def svg_name(line: str) -> str:
    """Return the filename for a notation, e.g. 'たべました_r1_d3.svg'."""
    mora, levels, particles = parse_notation(line)
    prev = ['L'] + levels
    rises = [i for i, level in enumerate(levels) if prev[i] == 'L' and level == 'H']
    drops = [i for i, level in enumerate(levels) if prev[i] == 'H' and level == 'L']

    parts = [''.join(mora)]
    for prefix, positions in (('r', rises), ('d', drops), ('p', sorted(particles))):
        if positions:
            parts.append(prefix + '-'.join(str(p) for p in positions))
    return '_'.join(parts) + '.svg'


def render_kana_svg(line: str, background: str | None = None) -> str:
    """Generate an SVG string with kana labels for a notation line."""
    mora, levels, particles = parse_notation(line)
    width = LABELLED_PADDING_X * 2 + len(mora) * MORA_W
    dots = []
    for i, level in enumerate(levels):
        cx = LABELLED_PADDING_X + i * MORA_W + MORA_W // 2
        cy = Y_HIGH if level == 'H' else Y_LOW
        colour = COLOR_HIGH if level == 'H' else COLOR_LOW
        dots.append((cx, cy, colour, i + 1 in particles))
    return render_dots(dots, width, background, labels=mora)


def read_lines(path: Path) -> list[str]:
    """Read one notation per line, skipping blank lines and # comments."""
    with path.open(encoding='utf-8') as f:
        return [s for s in (line.strip() for line in f) if s and not s.startswith('#')]


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate pitch accent SVGs with kana labels')
    parser.add_argument('notations', nargs='*', help="Kana notation, e.g. 'たべま＼した'")
    parser.add_argument('--file', default=None,
                        help='Text file with one notation per line; # comments ignored')
    parser.add_argument('--out_dir', default='output/pitch_svgs', help='Output directory for SVGs')
    parser.add_argument('--background', default=None,
                        help='Background colour, e.g. white (default: transparent); rounds the corners')
    args = parser.parse_args()

    lines = (read_lines(Path(args.file)) if args.file else []) + args.notations
    if not lines:
        raise SystemExit('Pass at least one notation, or --file')

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for line in lines:
        name = svg_name(line)
        (out_dir / name).write_text(render_kana_svg(line, args.background), encoding='utf-8')
        print(f'{name}  {"".join(parse_notation(line)[1])}')

    print(f'\nWrote {len(lines)} SVG(s) to {out_dir}/')


if __name__ == '__main__':
    main()
