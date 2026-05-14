"""Remove duplicate 単語 rows from a CSV output file."""

import argparse
from pathlib import Path

from jlpt_vocab.csv_utils import count_duplicates, dedup_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Remove duplicate 単語 rows from a CSV output file.',
        epilog='Example: python scripts/dedup_words.py --output output/jlpt_vocab.csv',
    )
    parser.add_argument('--output', required=True, help='CSV file, e.g. output/jlpt_vocab.csv')
    parser.add_argument('--dry-run', action='store_true', help='Print duplicate count without modifying files')
    args = parser.parse_args()

    csv_path = Path(args.output)

    if args.dry_run:
        count = count_duplicates(csv_path)
        if count:
            print(f'Would remove {count} duplicate row{"s" if count != 1 else ""}. (dry run — no changes made)')
        else:
            print('No duplicates found.')
        return

    removed = dedup_csv(csv_path)
    if removed == 0:
        print('No duplicates found.')
    else:
        print(f'Removed {removed} duplicate row{"s" if removed != 1 else ""}.')


if __name__ == '__main__':
    main()
