"""Backfill empty 品詞 and 英語訳 from jitendex without reprocessing the pipeline."""

import argparse
import csv
from pathlib import Path

from jlpt_vocab.dictionary import build_jitendex_index
from jlpt_vocab.download import DATA_DIR


def repair_pos(csv_path: Path) -> None:
    jitendex = build_jitendex_index(DATA_DIR / 'jitendex-yomitan')

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    repaired = 0
    for row in rows:
        if row.get('品詞'):
            continue
        jm = jitendex.get(row['単語'], {})
        if not jm:
            continue
        if jm.get('品詞'):
            row['品詞'] = jm['品詞']
        if not row.get('英語訳') and jm.get('英語訳'):
            row['英語訳'] = jm['英語訳']
        repaired += 1

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Repaired {repaired} rows in {csv_path.name}.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Backfill empty 品詞 and 英語訳 from jitendex in place.'
    )
    parser.add_argument('--output', required=True, help='CSV file to repair in place')
    args = parser.parse_args()
    repair_pos(Path(args.output))


if __name__ == '__main__':
    main()
