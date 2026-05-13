"""Tests for drop_words.py."""

import csv
import json
import pytest
from pathlib import Path

from drop_words import drop_from_csv, drop_from_checkpoint, load_checkpoint, save_checkpoint

_COLS = ['単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
         '英語訳', '仏語訳', '例文', '例文振り仮名', '英語例文', '仏語例文',
         '日本語ターゲット', 'レベル']


@pytest.fixture
def sample_csv(tmp_path):
    path = tmp_path / 'test.csv'
    rows = [
        {c: '' for c in _COLS} | {'単語': '下りる', 'レベル': 'N4'},
        {c: '' for c in _COLS} | {'単語': '招致', 'レベル': 'N4'},
        {c: '' for c in _COLS} | {'単語': '食べる', 'レベル': 'N4'},
    ]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=_COLS)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def sample_checkpoint(tmp_path):
    path = tmp_path / 'test_checkpoint.json'
    path.write_text(json.dumps(['下りる', '招致', '食べる'], ensure_ascii=False), encoding='utf-8')
    return path


class TestDropFromCsv:
    def test_removes_matching_rows(self, sample_csv):
        drop_from_csv(sample_csv, {'下りる', '招致'})
        with open(sample_csv, encoding='utf-8') as f:
            words = [r['単語'] for r in csv.DictReader(f)]
        assert words == ['食べる']

    def test_returns_found_words(self, sample_csv):
        found = drop_from_csv(sample_csv, {'下りる', '招致'})
        assert found == {'下りる', '招致'}

    def test_returns_only_found_subset(self, sample_csv):
        found = drop_from_csv(sample_csv, {'下りる', 'タイプミス'})
        assert found == {'下りる'}

    def test_preserves_header(self, sample_csv):
        drop_from_csv(sample_csv, {'下りる'})
        with open(sample_csv, encoding='utf-8') as f:
            assert csv.DictReader(f).fieldnames == _COLS

    def test_no_match_leaves_file_unchanged(self, sample_csv):
        mtime_before = sample_csv.stat().st_mtime
        drop_from_csv(sample_csv, {'タイプミス'})
        assert sample_csv.stat().st_mtime == mtime_before

    def test_empty_words_set_leaves_file_unchanged(self, sample_csv):
        mtime_before = sample_csv.stat().st_mtime
        drop_from_csv(sample_csv, set())
        assert sample_csv.stat().st_mtime == mtime_before


class TestDropFromCheckpoint:
    def test_removes_matching_words(self, sample_checkpoint):
        drop_from_checkpoint(sample_checkpoint, {'下りる', '招致'})
        data = json.loads(sample_checkpoint.read_text(encoding='utf-8'))
        assert data == ['食べる']

    def test_returns_found_words(self, sample_checkpoint):
        found = drop_from_checkpoint(sample_checkpoint, {'下りる', '招致'})
        assert found == {'下りる', '招致'}

    def test_returns_only_found_subset(self, sample_checkpoint):
        found = drop_from_checkpoint(sample_checkpoint, {'下りる', 'タイプミス'})
        assert found == {'下りる'}

    def test_missing_file_returns_empty_set(self, tmp_path):
        found = drop_from_checkpoint(tmp_path / 'missing.json', {'下りる'})
        assert found == set()

    def test_writes_readable_japanese(self, sample_checkpoint):
        drop_from_checkpoint(sample_checkpoint, {'下りる'})
        raw = sample_checkpoint.read_text(encoding='utf-8')
        assert '\\u' not in raw


class TestLoadSaveCheckpoint:
    def test_round_trip(self, tmp_path):
        path = tmp_path / 'ckpt.json'
        save_checkpoint({'食べる', '走る'}, path)
        assert load_checkpoint(path) == {'食べる', '走る'}

    def test_load_missing_returns_empty(self, tmp_path):
        assert load_checkpoint(tmp_path / 'missing.json') == set()

    def test_save_readable_japanese(self, tmp_path):
        path = tmp_path / 'ckpt.json'
        save_checkpoint({'食べる'}, path)
        assert '\\u' not in path.read_text(encoding='utf-8')
