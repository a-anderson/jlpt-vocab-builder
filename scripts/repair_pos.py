"""Backfill empty 品詞, 英語訳, and pitch accent from Jitendex without reprocessing the pipeline."""

import argparse
import csv
from pathlib import Path

from jlpt_vocab.dictionary import build_jitendex_index
from jlpt_vocab.download import DATA_DIR
from jlpt_vocab.normalise import normalise_word
from jlpt_vocab.pitch_accent import get_pitch_accent, svg_filename


def repair_fields(csv_path: Path) -> None:
    jitendex = build_jitendex_index(DATA_DIR / 'jitendex-yomitan')

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    has_pitch_col = 'ピッチアクセント' in fieldnames
    repaired = 0
    for row in rows:
        needs_pos = not row.get('品詞')
        needs_pitch = has_pitch_col and not row.get('ピッチアクセント')
        if not needs_pos and not needs_pitch:
            continue

        lookup_forms = normalise_word(row['単語'])['lookup_forms']
        matched_form = None
        jm: dict[str, str] = {}
        for form in lookup_forms:
            if form in jitendex:
                matched_form = form
                jm = jitendex[form]
                break

        changed = False
        if needs_pos and jm:
            if jm.get('品詞'):
                row['品詞'] = jm['品詞']
                changed = True
            if not row.get('英語訳') and jm.get('英語訳'):
                row['英語訳'] = jm['英語訳']
                changed = True

        if needs_pitch and matched_form:
            reading = jm.get('読み') or matched_form
            pitch = get_pitch_accent(matched_form, reading)
            if pitch['pattern'] is not None:
                row['ピッチアクセント'] = str(pitch['pattern'])
                row['ピッチアクセント図'] = svg_filename(pitch['mora_count'], pitch['pattern'])
                changed = True

        if changed:
            repaired += 1

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Repaired {repaired} rows in {csv_path.name}.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Backfill empty 品詞, 英語訳, and pitch accent from Jitendex in place.'
    )
    parser.add_argument('--output', required=True, help='CSV file to repair in place')
    args = parser.parse_args()
    repair_fields(Path(args.output))


if __name__ == '__main__':
    main()
