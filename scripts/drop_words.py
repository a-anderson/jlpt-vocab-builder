"""Remove words from a CSV output file and its paired checkpoint."""

import argparse
from pathlib import Path

from jlpt_vocab.csv_utils import drop_from_csv, drop_from_checkpoint


def main():
    parser = argparse.ArgumentParser(
        description='Drop words from a CSV output file and its paired checkpoint.',
        epilog='Example: python scripts/drop_words.py 下りる 招致 --output output/n4.csv',
    )
    parser.add_argument('words', nargs='+', help='Words to remove')
    parser.add_argument('--output', required=True, help='CSV file, e.g. output/n4.csv')
    args = parser.parse_args()

    words = set(args.words)
    csv_path = Path(args.output)
    checkpoint_path = csv_path.with_name(csv_path.stem + '_checkpoint.json')

    csv_found = drop_from_csv(csv_path, words)
    ckpt_found = drop_from_checkpoint(checkpoint_path, words)

    for word in sorted(words):
        in_csv = word in csv_found
        in_ckpt = word in ckpt_found
        if in_csv or in_ckpt:
            print(f'  dropped {word} (csv={in_csv}, checkpoint={in_ckpt})')
        else:
            print(f'  WARNING: {word!r} not found in either file')


if __name__ == '__main__':
    main()
