"""Tests for dedup_words.py."""

import csv
import sys
import pytest
from pathlib import Path

from jlpt_vocab.csv_utils import count_duplicates, dedup_csv
from scripts.dedup_words import main

_COLS = ['単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
         '英語訳', '仏語訳', '例文', '例文振り仮名', '英語例文', '仏語例文',
         '日本語ターゲット', 'レベル']


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=_COLS)
        writer.writeheader()
        writer.writerows(rows)


def _read_words(path: Path) -> list[str]:
    with open(path, encoding='utf-8') as f:
        return [r['単語'] for r in csv.DictReader(f)]


def _blank(word: str, level: str = 'N4', furigana: str = '') -> dict:
    return {c: '' for c in _COLS} | {'単語': word, '振り仮名': furigana, 'レベル': level}


class TestDedupCsv:
    def test_no_duplicates_returns_zero(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('飛ぶ')])
        assert dedup_csv(path) == 0

    def test_no_duplicates_leaves_file_unchanged(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る')])
        mtime_before = path.stat().st_mtime
        dedup_csv(path)
        assert path.stat().st_mtime == mtime_before

    def test_one_duplicate_returns_one(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる')])
        assert dedup_csv(path) == 1

    def test_one_duplicate_removes_last_occurrence(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる')])
        dedup_csv(path)
        assert _read_words(path) == ['食べる', '走る']

    def test_same_word_different_levels_keeps_first(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる', 'N4'), _blank('走る', 'N4'), _blank('食べる', 'N3')])
        dedup_csv(path)
        with open(path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]['単語'] == '食べる'
        assert rows[0]['レベル'] == 'N4'

    def test_multiple_duplicates_returns_count(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [
            _blank('食べる'), _blank('走る'), _blank('食べる'),
            _blank('飛ぶ'), _blank('走る'), _blank('飛ぶ'),
        ])
        assert dedup_csv(path) == 3

    def test_same_word_different_furigana_not_deduplicated(self, tmp_path):
        path = tmp_path / 'test.csv'
        hito = _blank('人', furigana='<ruby>人<rt>ひと</rt></ruby>')
        nin = _blank('人', furigana='<ruby>人<rt>にん</rt></ruby>')
        _write_csv(path, [hito, nin])
        assert dedup_csv(path) == 0
        assert _read_words(path) == ['人', '人']

    def test_word_appearing_three_times_keeps_first(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [
            _blank('食べる', 'N4'), _blank('走る', 'N4'),
            _blank('食べる', 'N3'), _blank('食べる', 'N2'),
        ])
        dedup_csv(path)
        with open(path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]['単語'] == '食べる'
        assert rows[0]['レベル'] == 'N4'

    def test_empty_csv_returns_zero(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [])
        assert dedup_csv(path) == 0

    def test_empty_csv_leaves_file_unchanged(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [])
        mtime_before = path.stat().st_mtime
        dedup_csv(path)
        assert path.stat().st_mtime == mtime_before

    def test_preserves_header(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('食べる')])
        dedup_csv(path)
        with open(path, encoding='utf-8') as f:
            assert csv.DictReader(f).fieldnames == _COLS

    def test_preserves_order_of_unique_words(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('飛ぶ'), _blank('走る'), _blank('食べる'), _blank('走る')])
        dedup_csv(path)
        assert _read_words(path) == ['飛ぶ', '走る', '食べる']


class TestCountDuplicates:
    def test_no_duplicates_returns_zero(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る')])
        assert count_duplicates(path) == 0

    def test_one_duplicate_returns_one(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる')])
        assert count_duplicates(path) == 1

    def test_multiple_duplicates_returns_count(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる'), _blank('走る')])
        assert count_duplicates(path) == 2

    def test_same_word_different_furigana_not_counted(self, tmp_path):
        path = tmp_path / 'test.csv'
        hito = _blank('人', furigana='<ruby>人<rt>ひと</rt></ruby>')
        nin = _blank('人', furigana='<ruby>人<rt>にん</rt></ruby>')
        _write_csv(path, [hito, nin])
        assert count_duplicates(path) == 0

    def test_does_not_modify_file(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('食べる')])
        mtime_before = path.stat().st_mtime
        count_duplicates(path)
        assert path.stat().st_mtime == mtime_before

    def test_empty_csv_returns_zero(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [])
        assert count_duplicates(path) == 0


class TestDedupScript:
    def _run(self, args: list[str], monkeypatch) -> None:
        monkeypatch.setattr(sys, 'argv', ['dedup_words.py'] + args)
        main()

    def test_removes_duplicates_and_prints_summary(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる')])
        self._run(['--output', str(path)], monkeypatch)
        assert _read_words(path) == ['食べる', '走る']
        assert capsys.readouterr().out.strip() == 'Removed 1 duplicate row.'

    def test_removes_multiple_and_prints_plural(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる'), _blank('走る')])
        self._run(['--output', str(path)], monkeypatch)
        assert capsys.readouterr().out.strip() == 'Removed 2 duplicate rows.'

    def test_no_duplicates_prints_no_op_message(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る')])
        self._run(['--output', str(path)], monkeypatch)
        assert capsys.readouterr().out.strip() == 'No duplicates found.'

    def test_dry_run_singular(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる')])
        mtime_before = path.stat().st_mtime
        self._run(['--output', str(path), '--dry-run'], monkeypatch)
        assert path.stat().st_mtime == mtime_before
        assert capsys.readouterr().out.strip() == 'Would remove 1 duplicate row. (dry run — no changes made)'

    def test_dry_run_plural(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る'), _blank('食べる'), _blank('走る')])
        mtime_before = path.stat().st_mtime
        self._run(['--output', str(path), '--dry-run'], monkeypatch)
        assert path.stat().st_mtime == mtime_before
        assert capsys.readouterr().out.strip() == 'Would remove 2 duplicate rows. (dry run — no changes made)'

    def test_dry_run_no_duplicates(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / 'test.csv'
        _write_csv(path, [_blank('食べる'), _blank('走る')])
        mtime_before = path.stat().st_mtime
        self._run(['--output', str(path), '--dry-run'], monkeypatch)
        assert path.stat().st_mtime == mtime_before
        assert capsys.readouterr().out.strip() == 'No duplicates found.'

    def test_missing_csv_raises(self, tmp_path, monkeypatch):
        with pytest.raises(FileNotFoundError):
            self._run(['--output', str(tmp_path / 'missing.csv')], monkeypatch)
