"""Tests for scripts/repair_pos.py."""

import csv
import pytest
from pathlib import Path
from unittest.mock import patch


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


COLUMNS = ['単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
           '英語訳', '例文', '例文振り仮名', '英語例文', '日本語ターゲット', 'レベル']

_JITENDEX_PATCH = 'scripts.repair_pos.build_jitendex_index'


class TestRepairPos:
    def test_fills_empty_pos(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': 'ある', '品詞': '', '英語訳': ''},
        ], COLUMNS)
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['品詞'] == '五段動詞（る）'

    def test_fills_empty_english_gloss(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': 'ある', '品詞': '', '英語訳': ''},
        ], COLUMNS)
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['英語訳'] == 'to be; to exist'

    def test_does_not_overwrite_existing_pos(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': '食べる', '品詞': '一段動詞', '英語訳': 'to eat'},
        ], COLUMNS)
        jitendex = {'食べる': {'品詞': '他動詞', '英語訳': 'to consume'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['品詞'] == '一段動詞'

    def test_does_not_overwrite_existing_english_gloss(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': '食べる', '品詞': '', '英語訳': 'to eat'},
        ], COLUMNS)
        jitendex = {'食べる': {'品詞': '一段動詞', '英語訳': 'to consume'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['英語訳'] == 'to eat'
        assert rows[0]['品詞'] == '一段動詞'

    def test_no_rows_need_repair_is_noop(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': '食べる', '品詞': '一段動詞', '英語訳': 'to eat'},
            {c: '' for c in COLUMNS} | {'単語': '走る', '品詞': '自動詞', '英語訳': 'to run'},
        ], COLUMNS)
        before = csv_path.read_text(encoding='utf-8')
        jitendex = {'食べる': {'品詞': '他動詞', '英語訳': 'to consume'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        assert csv_path.read_text(encoding='utf-8') == before

    def test_existing_pos_empty_gloss_not_repaired(self, tmp_path):
        # rows with existing 品詞 are skipped entirely — 英語訳 is not backfilled
        # even if jitendex has it. this is intentional: the script targets rows
        # where the whole jitendex lookup failed, not partial repairs.
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': '食べる', '品詞': '一段動詞', '英語訳': ''},
        ], COLUMNS)
        jitendex = {'食べる': {'品詞': '一段動詞', '英語訳': 'to eat'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['英語訳'] == ''

    def test_skips_words_not_in_jitendex(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': 'ありがとうございます', '品詞': '', '英語訳': ''},
        ], COLUMNS)
        with patch(_JITENDEX_PATCH, return_value={}):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['品詞'] == ''

    def test_preserves_all_other_columns(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {
                '単語': 'ある', '品詞': '', '英語訳': '',
                '例文': 'ここに本がある。', '英語例文': 'There is a book here.',
                'レベル': 'N4',
            },
        ], COLUMNS)
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['例文'] == 'ここに本がある。'
        assert rows[0]['英語例文'] == 'There is a book here.'
        assert rows[0]['レベル'] == 'N4'

    def test_handles_mixed_rows(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': 'ある', '品詞': '', '英語訳': ''},
            {c: '' for c in COLUMNS} | {'単語': '食べる', '品詞': '一段動詞', '英語訳': 'to eat'},
            {c: '' for c in COLUMNS} | {'単語': 'ありがとうございます', '品詞': '', '英語訳': ''},
        ], COLUMNS)
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['品詞'] == '五段動詞（る）'
        assert rows[1]['品詞'] == '一段動詞'
        assert rows[2]['品詞'] == ''

    def test_preserves_csv_columns(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            {c: '' for c in COLUMNS} | {'単語': 'ある'},
        ], COLUMNS)
        with patch(_JITENDEX_PATCH, return_value={}):
            from scripts.repair_pos import repair_pos
            repair_pos(csv_path)
        with open(csv_path, newline='', encoding='utf-8') as f:
            assert csv.DictReader(f).fieldnames == COLUMNS
