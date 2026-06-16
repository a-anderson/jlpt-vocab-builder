"""Append a pitch-accent citation particle to 単語 and 振り仮名 columns in a vocabulary CSV.

Nouns/na-adj/no-adj/pronouns get が; verbs/i-adj get よ; everything else is unchanged.
Rows where 単語 already ends with the particle are skipped (idempotent).

Usage:
  python scripts/add_particle.py --input output/n4.csv
  python scripts/add_particle.py --input output/n4.csv --output output/n4_particle.csv
  python scripts/add_particle.py --input output/n4.csv --dry-run
"""

import argparse
import csv
import os
import shutil
import tempfile
from pathlib import Path

from jlpt_vocab.pipeline import apply_particles, get_particle


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Append pitch-accent citation particle to CSV words')
    parser.add_argument('--input', required=True, help='Input CSV (build.py output format)')
    parser.add_argument('--output', default=None, help='Output CSV (default: overwrite input)')
    parser.add_argument('--dry-run', action='store_true', help='Preview first few changes, do not write')
    parser.add_argument('--dry-run-count', type=int, default=5, help='Number of rows to preview (default: 5)')
    return parser


def main() -> None:
    args = _make_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    with open(input_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if args.dry_run:
        shown = 0
        for row in rows:
            if shown >= args.dry_run_count:
                break
            pos = row.get('品詞', '')
            particle = get_particle(pos)
            if particle and not row['単語'].endswith(particle):
                print(f"  {row['単語']} → {row['単語']}{particle} | {row['振り仮名']} → {row['振り仮名']}{particle}  [{pos}]")
                shown += 1
        updated, skipped, unchanged = apply_particles([dict(r) for r in rows])
        print(f"\nDry run: {updated} would be updated, {skipped} already have particle, {unchanged} have no particle")
        return

    updated, skipped, unchanged = apply_particles(rows)

    if output_path == input_path:
        shutil.copy2(input_path, input_path.with_suffix('.bak'))

    fd, tmp_str = tempfile.mkstemp(dir=output_path.parent, suffix='.csv')
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        shutil.move(str(tmp), output_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    print(f"Done. {updated} updated, {skipped} already had particle, {unchanged} had no particle → {output_path}")


if __name__ == '__main__':
    main()
