"""Pitch accent lookup: Kanjium (primary) → NHK CSV → OJAD API (last resort)."""

import csv
import re
import time
from functools import lru_cache
from pathlib import Path

import requests

KANJIUM_LOCAL = Path('data/accents.txt')
NHK_CSV_LOCAL = Path('data/nhk_data/ACCDB_unicode.csv')
OJAD_URL = 'https://www.ojad.jp/api/v0/words'
OJAD_DELAY = 1.5

_kanjium_index: dict[str, int] | None = None
_nhk_index: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# Mora splitting
# ---------------------------------------------------------------------------

def split_mora(reading: str) -> list[str]:
    """Split a plain kana string into mora, treating compound kana as one unit.

    'きょうと' → ['きょ', 'う', 'と']
    """
    if not reading:
        return []
    small = set('ぁぃぅぇぉゃゅょァィゥェォャュョ')
    mora, i, chars = [], 0, list(reading)
    while i < len(chars):
        if i + 1 < len(chars) and chars[i + 1] in small:
            mora.append(chars[i] + chars[i + 1])
            i += 2
        else:
            mora.append(chars[i])
            i += 1
    return mora


# ---------------------------------------------------------------------------
# Kanjium (primary, local)
# ---------------------------------------------------------------------------

def _load_kanjium_index() -> dict[str, int]:
    """Parse accents.txt into expression/reading → first pitch pattern."""
    index: dict[str, int] = {}
    with open(KANJIUM_LOCAL, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            expression, reading, pattern_str = parts[0], parts[1], parts[2]
            try:
                pattern = int(pattern_str.split(',')[0].strip())
            except ValueError:
                continue
            # Keep only the first entry per key (most common)
            if expression not in index:
                index[expression] = pattern
            if reading and reading not in index:
                index[reading] = pattern
    return index


def _get_kanjium_index() -> dict[str, int]:
    global _kanjium_index
    if _kanjium_index is None:
        _kanjium_index = _load_kanjium_index()
    return _kanjium_index


def _fetch_kanjium(word: str, reading: str, mora_count: int) -> dict:
    index = _get_kanjium_index()
    for key in (word, reading):
        if key and key in index:
            return {'pattern': index[key], 'mora_count': mora_count, 'source': 'kanjium'}
    return {'pattern': None, 'mora_count': mora_count, 'source': 'kanjium'}


# ---------------------------------------------------------------------------
# NHK CSV (fallback, local)
# ---------------------------------------------------------------------------

def _decode_nhk_ac(ac_str: str, mora_count: int) -> int:
    """Convert NHK per-mora ac string to a Kanjium-compatible drop pattern.

    NHK encodes each mora as '1' (H), '2' (H then drop), or '0' (L), with
    leading '0's omitted. Pad back to mora_count, then find the '2' position.
    """
    full = '0' * max(0, mora_count - len(ac_str)) + ac_str
    if '2' not in full:
        return 0
    return full.index('2') + 1


def _load_nhk_index() -> dict[str, int]:
    """Parse ACCDB_unicode.csv, indexing by midashigo, kanjiexpr, and nhk reading.

    Columns: NID, ID, WAVname, K_FLD, ACT, midashigo(5), nhk(6), kanjiexpr(7), ..., ac(18)
    Keeps the first pattern found per key.
    """
    index: dict[str, int] = {}
    with open(NHK_CSV_LOCAL, encoding='utf-8', newline='') as f:
        for row in csv.reader(f):
            if len(row) < 19:
                continue
            ac_str = row[18].strip()
            if not ac_str or not all(c in '012' for c in ac_str):
                continue
            midashigo = row[5].strip()
            mora_count = len(split_mora(midashigo))
            if mora_count == 0:
                continue
            pattern = _decode_nhk_ac(ac_str, mora_count)
            for col in (row[5], row[7], row[6]):
                key = col.strip()
                if key and key not in index:
                    index[key] = pattern
    return index


def _get_nhk_index() -> dict[str, int]:
    global _nhk_index
    if _nhk_index is None:
        _nhk_index = _load_nhk_index()
    return _nhk_index


def _fetch_nhk(word: str, reading: str, mora_count: int) -> dict:
    index = _get_nhk_index()
    for key in (word, reading):
        if key and key in index:
            return {'pattern': index[key], 'mora_count': mora_count, 'source': 'nhk'}
    return {'pattern': None, 'mora_count': mora_count, 'source': 'nhk'}


# ---------------------------------------------------------------------------
# OJAD API (last resort, online)
# ---------------------------------------------------------------------------

def _fetch_ojad(word: str, reading: str, mora_count: int) -> dict:
    """Query OJAD API — undocumented, unofficial. Failures are silent."""
    empty = {'pattern': None, 'mora_count': mora_count, 'source': 'ojad'}
    try:
        resp = requests.get(OJAD_URL, params={'limit': 5, 'word': word}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        time.sleep(OJAD_DELAY)
    except Exception:
        return empty
    for entry in data.get('words', []):
        for accent in entry.get('accents', []):
            pattern = accent.get('accent')
            if pattern is not None:
                try:
                    return {'pattern': int(pattern), 'mora_count': mora_count, 'source': 'ojad'}
                except (ValueError, TypeError):
                    pass
            mora_str = accent.get('mora', '')
            if mora_str and '↓' in mora_str:
                before = mora_str[: mora_str.index('↓')]
                return {'pattern': len(split_mora(before)), 'mora_count': mora_count, 'source': 'ojad'}
    return empty


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def get_pitch_accent(word: str, reading: str) -> dict:
    """Return pitch accent data, trying Kanjium → NHK → OJAD.

    Returns {'pattern': int | None, 'mora_count': int, 'source': str}
    """
    mora_count = len(split_mora(reading))
    for fetch in (_fetch_kanjium, _fetch_nhk, _fetch_ojad):
        result = fetch(word, reading, mora_count)
        if result['pattern'] is not None:
            return result
    return {'pattern': None, 'mora_count': mora_count, 'source': 'unknown'}


def plain_kana(furigana_raw: str) -> str:
    """Strip chadmuro bracket-notation furigana to a plain kana reading."""
    reading = re.sub(r'[^\[\]぀-ゟ゠-ヿ]+\[([^\]]+)\]', r'\1', furigana_raw)
    reading = re.sub(r'[^぀-ゟ゠-ヿ]', '', reading)
    return reading


def svg_filename(mora_count: int, pattern: int | None) -> str:
    """Return SVG filename for a pitch pattern, e.g. '3_2.svg'."""
    if pattern is None:
        return 'unknown.svg'
    return f'{mora_count}_{pattern}.svg'


def get_pitch_columns(word: str, reading: str) -> dict:
    """Return the two CSV pitch columns for a word."""
    data = get_pitch_accent(word, reading)
    return {
        'ピッチアクセント': '' if data['pattern'] is None else str(data['pattern']),
        'ピッチアクセント図': svg_filename(data['mora_count'], data['pattern']),
    }
