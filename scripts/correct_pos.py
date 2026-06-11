"""Correct misclassified 品詞 values in an existing CSV output file.

Re-looks up each verb-tagged word in Jitendex using the corrected POS logic
and updates rows where the word is actually a verbal noun. Also fixes the
typo '自動し' on 開く.
"""

import argparse
import csv
from pathlib import Path

from jlpt_vocab.dictionary import build_jitendex_index
from jlpt_vocab.download import DATA_DIR
from jlpt_vocab.normalise import normalise_word


VERB_POS = {
    '他動詞', '自動詞', '一段動詞', 'カ変動詞', 'サ変動詞（する）',
    '五段動詞（う）', '五段動詞（く）', '五段動詞（ぐ）', '五段動詞（す）',
    '五段動詞（つ）', '五段動詞（ぬ）', '五段動詞（ぶ）', '五段動詞（む）', '五段動詞（る）',
}


def correct_pos(csv_path: Path, dry_run: bool = False) -> None:
    jitendex = build_jitendex_index(DATA_DIR / 'jitendex-yomitan')

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    updated = typos = 0
    for row in rows:
        word, pos = row['単語'], row['品詞']

        if pos == '自動し':
            if not dry_run:
                row['品詞'] = '自動詞'
            typos += 1
            continue

        if pos not in VERB_POS:
            continue

        lookup_forms = normalise_word(word)['lookup_forms']
        for form in lookup_forms:
            if form in jitendex:
                new_pos = jitendex[form].get('品詞', '')
                if new_pos and new_pos not in VERB_POS and new_pos != pos:
                    if not dry_run:
                        row['品詞'] = new_pos
                    updated += 1
                break

    if not dry_run:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    total = updated + typos
    prefix = 'Would correct' if dry_run else 'Corrected'
    print(f'{prefix} {total} rows in {csv_path.name}:')
    print(f'  {updated} verbal nouns reclassified')
    print(f'  {typos} typos fixed')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Correct misclassified 品詞 (verbal nouns tagged as verbs) in a CSV.'
    )
    parser.add_argument('--output', required=True, help='CSV file to correct in place')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying the file')
    args = parser.parse_args()
    correct_pos(Path(args.output), dry_run=args.dry_run)


if __name__ == '__main__':
    main()
