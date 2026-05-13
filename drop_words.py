"""Remove words from a CSV output file and its paired checkpoint."""

import argparse
import csv
import json
from pathlib import Path


def drop_from_csv(csv_path: Path, words: set[str]) -> set[str]:
    """Rewrite csv_path without rows matching words. Returns words that were found."""
    rows = []
    found = set()
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            if row['単語'] in words:
                found.add(row['単語'])
            else:
                rows.append(row)

    if not found:
        return found

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return found


def drop_from_checkpoint(checkpoint_path: Path, words: set[str]) -> set[str]:
    """Rewrite checkpoint_path without matching words. Returns words that were found."""
    if not checkpoint_path.exists():
        return set()
    data = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    found = {w for w in data if w in words}
    if not found:
        return found
    checkpoint_path.write_text(
        json.dumps([w for w in data if w not in words], ensure_ascii=False),
        encoding='utf-8',
    )
    return found


def load_checkpoint(checkpoint_path: Path) -> set[str]:
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done: set[str], checkpoint_path: Path) -> None:
    with open(checkpoint_path, 'w') as f:
        json.dump(list(done), f, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description='Drop words from a CSV output file and its paired checkpoint.',
        epilog='Example: python drop_words.py 下りる 招致 --output n4.csv',
    )
    parser.add_argument('words', nargs='+', help='Words to remove')
    parser.add_argument('--output', required=True, help='CSV file, e.g. n4.csv')
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
