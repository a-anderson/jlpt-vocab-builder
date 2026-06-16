"""Checkpoint and CSV row-removal utilities shared across pipeline scripts."""

import csv
import json
import os
import shutil
import tempfile
from pathlib import Path

_PARTICLES = frozenset({'が', 'よ'})


def canonical(word: str) -> str:
    """Strip trailing citation particle for identity comparisons."""
    return word[:-1] if len(word) > 1 and word[-1] in _PARTICLES else word


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write rows to path atomically via a temp file, replacing path on success."""
    fd, tmp_str = tempfile.mkstemp(dir=path.parent, suffix='.csv')
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        shutil.move(str(tmp), path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def drop_from_csv(csv_path: Path, words: set[str]) -> set[str]:
    """Rewrite csv_path dropping rows whose canonical word matches; returns found words."""
    rows = []
    found = set()
    canonical_to_original = {canonical(w): w for w in words}
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            row_canonical = canonical(row['単語'])
            if row_canonical in canonical_to_original:
                found.add(canonical_to_original[row_canonical])
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
    """Keep first occurrence of each canonical (単語, 振り仮名) pair; rewrite in-place. Returns removed count."""
    rows, seen = [], set()
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        all_rows = list(reader)
    for row in all_rows:
        key = (canonical(row['単語']), canonical(row['振り仮名']))
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
    """Return the number of duplicate canonical (単語, 振り仮名) rows without modifying the file."""
    seen: set[tuple[str, str]] = set()
    count = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (canonical(row['単語']), canonical(row['振り仮名']))
            if key in seen:
                count += 1
            else:
                seen.add(key)
    return count


def drop_from_checkpoint(checkpoint_path: Path, words: set[str]) -> set[str]:
    """Rewrite checkpoint dropping canonical-matched words; returns found words."""
    if not checkpoint_path.exists():
        return set()
    data = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    canonical_to_original = {canonical(w): w for w in words}
    found_canonical = {canonical(w) for w in data if canonical(w) in canonical_to_original}
    if not found_canonical:
        return set()
    checkpoint_path.write_text(
        json.dumps([w for w in data if canonical(w) not in found_canonical], ensure_ascii=False),
        encoding='utf-8',
    )
    return {canonical_to_original[c] for c in found_canonical}


def load_checkpoint(checkpoint_path: Path) -> set[str]:
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done: set[str], checkpoint_path: Path) -> None:
    with open(checkpoint_path, 'w') as f:
        json.dump(list(done), f, ensure_ascii=False)
