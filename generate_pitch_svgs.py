"""
generate_pitch_svgs.py
======================
Reads the completed jlpt_vocab.csv and generates one SVG file per unique
(mora_count, pattern) combination found in it.

Output directory: ./pitch_svgs/
Filenames:        {mora_count}_{pattern}.svg   e.g. 4_2.svg
Special case:     unknown.svg  (no pattern found — empty placeholder)

The SVG contains dots and connecting lines — no text.
A hollow (outline-only) dot on the right represents the following particle (は/が),
distinguishing it from the solid word mora dots.

Colours follow the standard OJAD/NHK convention:
  High mora     → solid red dot   (#E05A6A)
  Low mora      → solid cyan dot  (#4EC3E0)
  Particle high → hollow red dot
  Particle low  → hollow cyan dot

Particle pitch rule:
  Heiban (pattern 0)            → particle is HIGH (pitch stays up)
  Atamadaka / nakadaka (1..N-1) → particle is LOW  (already dropped)
  Odaka (pattern == mora_count) → particle is LOW  (drops ON the particle)

Usage:
  python generate_pitch_svgs.py
  python generate_pitch_svgs.py --input my_vocab.csv --out_dir my_svgs/

For Anki:
  Copy all SVGs into your Anki media folder:
    ~/.local/share/Anki2/<profile>/collection.media/   (Linux)
    ~/Library/Application Support/Anki2/<profile>/collection.media/  (macOS)
  Reference in card template as: <img src="{{ピッチアクセント図}}">
"""

import argparse
import csv
from pathlib import Path


# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

MORA_W = 36          # horizontal spacing per mora (px)
PARTICLE_GAP = 12    # extra gap before particle dot (visual separator)
PADDING_X = 20       # left/right padding
DOT_R = 8            # dot radius
Y_HIGH = 16          # y centre for high dots
Y_LOW = 52           # y centre for low dots
SVG_HEIGHT = 72      # total SVG height
LINE_W = 3           # connecting line stroke width

COLOR_HIGH = "#E05A6A"
COLOR_LOW  = "#4EC3E0"
COLOR_LINE = "#1A1A1A"


# ---------------------------------------------------------------------------
# Pitch pattern logic
# ---------------------------------------------------------------------------

def pitch_sequence(mora_count: int, pattern: int) -> list[str]:
    """
    Convert mora count + numeric pattern to a H/L sequence for the word mora.

    pattern 0 (heiban):              L H H H ...
    pattern 1 (atamadaka):           H L L L ...
    pattern N, 2 <= N < mora_count:  L H...H L...   (nakadaka, drops after N)
    pattern N == mora_count (odaka): L H H...H       (drops on particle)
    """
    if mora_count == 0:
        return []
    if pattern == 0:
        return ["L"] + ["H"] * (mora_count - 1)
    elif pattern == 1:
        return ["H"] + ["L"] * (mora_count - 1)
    else:
        seq = []
        for i in range(mora_count):
            if i == 0:
                seq.append("L")
            elif i < pattern:
                seq.append("H")
            else:
                seq.append("L")
        return seq


def particle_level(mora_count: int, pattern: int) -> str:
    """
    Return H or L for the particle that follows the word.

    Heiban (0): particle stays HIGH.
    Everything else: particle is LOW.
    This correctly handles odaka (pattern == mora_count): the last word mora
    is high but the particle drops, so particle = LOW.
    """
    return "H" if pattern == 0 else "L"


# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------

def render_svg(mora_count: int, pattern: int) -> str:
    """Generate SVG string for a given mora count and drop pattern."""
    seq = pitch_sequence(mora_count, pattern)
    p_level = particle_level(mora_count, pattern)

    # Total width: word mora + gap + one particle mora
    width = PADDING_X * 2 + mora_count * MORA_W + PARTICLE_GAP + MORA_W

    # --- Word mora dots (solid) ---
    dots = []  # (cx, cy, colour, hollow)
    for i, level in enumerate(seq):
        cx = PADDING_X + i * MORA_W + MORA_W // 2
        cy = Y_HIGH if level == "H" else Y_LOW
        colour = COLOR_HIGH if level == "H" else COLOR_LOW
        dots.append((cx, cy, colour, False))

    # --- Particle dot (hollow) ---
    p_cx = PADDING_X + mora_count * MORA_W + PARTICLE_GAP + MORA_W // 2
    p_cy = Y_HIGH if p_level == "H" else Y_LOW
    p_colour = COLOR_HIGH if p_level == "H" else COLOR_LOW
    dots.append((p_cx, p_cy, p_colour, True))

    # --- Connecting lines between consecutive dots ---
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

    # Dots — solid for word mora, hollow (fill=white/transparent) for particle
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


def render_unknown_svg() -> str:
    """Minimal placeholder SVG for words with no pitch data."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="72"'
        ' viewBox="0 0 40 72">'
        '<text x="20" y="40" text-anchor="middle" font-size="24"'
        ' font-family="sans-serif" fill="#999">?</text>'
        '</svg>'
    )


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def collect_pairs(csv_path: Path) -> tuple[set[tuple[int, int]], bool]:
    """
    Read the CSV and collect all unique (mora_count, pattern) pairs.
    Inferred from the ピッチアクセント図 filename: "4_2.svg" → (4, 2).
    """
    pairs = set()
    has_unknown = False

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row.get("ピッチアクセント図", "").strip()
            if not fname or fname == "unknown.svg":
                has_unknown = True
                continue
            stem = fname.replace(".svg", "")
            parts = stem.split("_")
            if len(parts) == 2:
                try:
                    pairs.add((int(parts[0]), int(parts[1])))
                except ValueError:
                    has_unknown = True

    return pairs, has_unknown


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate pitch accent SVG files")
    parser.add_argument("--input", default="jlpt_vocab.csv", help="Input CSV path")
    parser.add_argument("--out_dir", default="pitch_svgs", help="Output directory for SVGs")
    args = parser.parse_args()

    csv_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        print("Run build_jlpt_csv.py first, then run this script.")
        return

    print(f"Reading {csv_path}...")
    pairs, has_unknown = collect_pairs(csv_path)
    print(f"Found {len(pairs)} unique (mora_count, pattern) combinations.")

    generated = 0
    skipped = 0
    for mora_count, pattern in sorted(pairs):
        if pattern > mora_count:
            print(f"  Warning: skipping invalid pattern {mora_count}_{pattern} "
                  f"(pattern > mora_count)")
            skipped += 1
            continue
        svg = render_svg(mora_count, pattern)
        out_path = out_dir / f"{mora_count}_{pattern}.svg"
        out_path.write_text(svg, encoding="utf-8")
        generated += 1

    if has_unknown:
        out_path = out_dir / "unknown.svg"
        out_path.write_text(render_unknown_svg(), encoding="utf-8")
        print("  Generated unknown.svg (placeholder for missing pitch data)")

    if skipped:
        print(f"  Skipped {skipped} invalid combinations.")

    print(f"Done. {generated} SVG files written to {out_dir}/")
    print()
    print("Next steps:")
    print(f"  1. Copy all SVGs from {out_dir}/ into your Anki media folder")
    print("  2. In your Anki card template, add: <img src=\"{{{{ピッチアクセント図}}}}\">")


if __name__ == "__main__":
    main()
