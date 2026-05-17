"""Checkpoint and CSV row-removal utilities shared across pipeline scripts."""

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


def dedup_csv(csv_path: Path) -> int:
    """Keep first occurrence of each (単語, 振り仮名) pair; rewrite in-place. Returns duplicate row count."""
    rows, seen = [], set()
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        all_rows = list(reader)
    for row in all_rows:
        key = (row['単語'], row['振り仮名'])
        if key not in seen:
            seen.add(key)
            rows.append(row)
    removed = len(all_rows) - len(rows)
    if removed == 0:
        return 0
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return removed


def count_duplicates(csv_path: Path) -> int:
    """Return the number of duplicate (単語, 振り仮名) rows without modifying the file."""
    seen: set[tuple[str, str]] = set()
    count = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (row['単語'], row['振り仮名'])
            if key in seen:
                count += 1
            else:
                seen.add(key)
    return count


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
