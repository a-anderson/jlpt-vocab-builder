"""Tests for scripts/correct_pos.py."""

import csv
from pathlib import Path
from unittest.mock import patch

from scripts.correct_pos import correct_pos

COLUMNS = ['単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
           '英語訳', '例文', '例文振り仮名', '英語例文', '日本語ターゲット', 'レベル']

_INDEX_PATCH = 'scripts.correct_pos.build_jitendex_index'


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _blank(overrides: dict) -> dict:
    return {c: '' for c in COLUMNS} | overrides


class TestCorrectPos:
    def test_verbal_noun_corrected_to_meishi(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '挨拶', '品詞': '自動詞'})])
        index = {'挨拶': {'品詞': '名詞'}}
        with patch(_INDEX_PATCH, return_value=index):
            correct_pos(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '名詞'

    def test_verbal_noun_corrected_to_na_adjective(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '妥当', '品詞': '自動詞'})])
        index = {'妥当': {'品詞': 'な形容詞'}}
        with patch(_INDEX_PATCH, return_value=index):
            correct_pos(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == 'な形容詞'

    def test_typo_corrected(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '開く', '品詞': '自動し'})])
        with patch(_INDEX_PATCH, return_value={}):
            correct_pos(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '自動詞'

    def test_true_verb_not_modified(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '食べる', '品詞': '他動詞'})])
        index = {'食べる': {'品詞': '他動詞'}}
        with patch(_INDEX_PATCH, return_value=index):
            correct_pos(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '他動詞'

    def test_word_not_in_index_not_modified(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '挨拶', '品詞': '自動詞'})])
        with patch(_INDEX_PATCH, return_value={}):
            correct_pos(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '自動詞'

    def test_dry_run_makes_no_changes(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '挨拶', '品詞': '自動詞'})])
        index = {'挨拶': {'品詞': '名詞'}}
        before = csv_path.read_text(encoding='utf-8')
        with patch(_INDEX_PATCH, return_value=index):
            correct_pos(csv_path, dry_run=True)
        assert csv_path.read_text(encoding='utf-8') == before

    def test_preserves_other_columns(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '挨拶', '品詞': '自動詞', '英語訳': 'greeting', 'レベル': 'N4'})])
        index = {'挨拶': {'品詞': '名詞'}}
        with patch(_INDEX_PATCH, return_value=index):
            correct_pos(csv_path)
        row = _read_csv(csv_path)[0]
        assert row['英語訳'] == 'greeting'
        assert row['レベル'] == 'N4'

    def test_mixed_rows(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            _blank({'単語': '挨拶', '品詞': '自動詞'}),
            _blank({'単語': '食べる', '品詞': '他動詞'}),
            _blank({'単語': '開く', '品詞': '自動し'}),
        ])
        index = {
            '挨拶': {'品詞': '名詞'},
            '食べる': {'品詞': '他動詞'},
        }
        with patch(_INDEX_PATCH, return_value=index):
            correct_pos(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['品詞'] == '名詞'
        assert rows[1]['品詞'] == '他動詞'
        assert rows[2]['品詞'] == '自動詞'

    def test_preserves_csv_columns(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '挨拶', '品詞': '自動詞'})])
        with patch(_INDEX_PATCH, return_value={}):
            correct_pos(csv_path)
        with open(csv_path, newline='', encoding='utf-8') as f:
            assert csv.DictReader(f).fieldnames == COLUMNS
