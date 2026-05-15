"""Tests for scripts/repair_pos.py."""

import csv
from pathlib import Path
from unittest.mock import patch

from scripts.repair_pos import repair_fields


COLUMNS = ['単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
           '英語訳', '例文', '例文振り仮名', '英語例文', '日本語ターゲット', 'レベル']

_JITENDEX_PATCH = 'scripts.repair_pos.build_jitendex_index'
_PITCH_PATCH = 'scripts.repair_pos.get_pitch_accent'
_NO_PITCH = {'pattern': None, 'mora_count': 0, 'source': 'unknown'}


def _write_csv(path: Path, rows: list[dict], columns: list[str] = COLUMNS) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _blank(overrides: dict) -> dict:
    return {c: '' for c in COLUMNS} | overrides


class TestRepairFields:
    def test_fills_empty_pos(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'ある'})])
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist', '読み': 'ある'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '五段動詞（る）'

    def test_fills_empty_english_gloss(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'ある'})])
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist', '読み': 'ある'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert _read_csv(csv_path)[0]['英語訳'] == 'to be; to exist'

    def test_does_not_overwrite_existing_pos(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '食べる', '品詞': '一段動詞', '英語訳': 'to eat'})])
        jitendex = {'食べる': {'品詞': '他動詞', '英語訳': 'to consume', '読み': 'たべる'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '一段動詞'

    def test_does_not_overwrite_existing_english_gloss(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '食べる', '英語訳': 'to eat'})])
        jitendex = {'食べる': {'品詞': '一段動詞', '英語訳': 'to consume', '読み': 'たべる'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['英語訳'] == 'to eat'
        assert rows[0]['品詞'] == '一段動詞'

    def test_no_rows_need_repair_is_noop(self, tmp_path):
        # Rows with both 品詞 and ピッチアクセント filled are skipped entirely
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            _blank({'単語': '食べる', '品詞': '一段動詞', '英語訳': 'to eat', 'ピッチアクセント': '2'}),
            _blank({'単語': '走る', '品詞': '自動詞', '英語訳': 'to run', 'ピッチアクセント': '1'}),
        ])
        before = csv_path.read_text(encoding='utf-8')
        with patch(_JITENDEX_PATCH, return_value={}), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert csv_path.read_text(encoding='utf-8') == before

    def test_english_gloss_not_backfilled_when_only_pitch_missing(self, tmp_path):
        # 英語訳 backfill only runs when 品詞 was also empty; pitch-only repairs don't touch it
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '食べる', '品詞': '一段動詞'})])
        jitendex = {'食べる': {'品詞': '一段動詞', '英語訳': 'to eat', '読み': 'たべる'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert _read_csv(csv_path)[0]['英語訳'] == ''

    def test_skips_words_not_in_jitendex(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'ありがとうございます'})])
        with patch(_JITENDEX_PATCH, return_value={}), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == ''

    def test_preserves_all_other_columns(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({
            '単語': 'ある', '例文': 'ここに本がある。', '英語例文': 'There is a book here.', 'レベル': 'N4',
        })])
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be', '読み': 'ある'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        row = _read_csv(csv_path)[0]
        assert row['例文'] == 'ここに本がある。'
        assert row['英語例文'] == 'There is a book here.'
        assert row['レベル'] == 'N4'

    def test_handles_mixed_rows(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [
            _blank({'単語': 'ある'}),
            _blank({'単語': '食べる', '品詞': '一段動詞', '英語訳': 'to eat', 'ピッチアクセント': '2'}),
            _blank({'単語': 'ありがとうございます'}),
        ])
        jitendex = {'ある': {'品詞': '五段動詞（る）', '英語訳': 'to be; to exist', '読み': 'ある'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        rows = _read_csv(csv_path)
        assert rows[0]['品詞'] == '五段動詞（る）'
        assert rows[1]['品詞'] == '一段動詞'
        assert rows[2]['品詞'] == ''

    def test_tilde_word_strips_prefix_for_lookup(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': '～以上'})])
        jitendex = {'以上': {'品詞': '名詞', '英語訳': 'or more; and above', '読み': 'いじょう'}}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert _read_csv(csv_path)[0]['品詞'] == '名詞'

    def test_preserves_csv_columns(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'ある'})])
        with patch(_JITENDEX_PATCH, return_value={}), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        with open(csv_path, newline='', encoding='utf-8') as f:
            assert csv.DictReader(f).fieldnames == COLUMNS

    def test_backfills_pos_and_pitch_for_bare_na(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'ラッキーな'})])
        jitendex = {'ラッキー': {'品詞': 'な形容詞', '英語訳': 'lucky', '読み': 'らっきー'}}
        pitch = {'pattern': 3, 'mora_count': 4, 'source': 'kanjium'}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=pitch) as mock_pitch:
            repair_fields(csv_path)
        mock_pitch.assert_called_once_with('ラッキー', 'らっきー')
        row = _read_csv(csv_path)[0]
        assert row['品詞'] == 'な形容詞'
        assert row['英語訳'] == 'lucky'
        assert row['ピッチアクセント'] == '3'
        assert row['ピッチアクセント図'] == '4_3.svg'

    def test_backfills_pos_and_pitch_for_bare_to(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'すらりと'})])
        jitendex = {'すらり': {'品詞': '副詞', '英語訳': 'slender', '読み': 'すらり'}}
        pitch = {'pattern': 2, 'mora_count': 4, 'source': 'kanjium'}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=pitch) as mock_pitch:
            repair_fields(csv_path)
        mock_pitch.assert_called_once_with('すらり', 'すらり')
        row = _read_csv(csv_path)[0]
        assert row['品詞'] == '副詞'
        assert row['ピッチアクセント'] == '2'
        assert row['ピッチアクセント図'] == '4_2.svg'

    def test_backfills_pitch_when_pos_already_filled(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({'単語': 'ラッキーな', '品詞': 'な形容詞', '英語訳': 'lucky'})])
        jitendex = {'ラッキー': {'品詞': 'な形容詞', '英語訳': 'lucky', '読み': 'らっきー'}}
        pitch = {'pattern': 3, 'mora_count': 4, 'source': 'kanjium'}
        with patch(_JITENDEX_PATCH, return_value=jitendex), patch(_PITCH_PATCH, return_value=pitch):
            repair_fields(csv_path)
        row = _read_csv(csv_path)[0]
        assert row['ピッチアクセント'] == '3'
        assert row['品詞'] == 'な形容詞'

    def test_skips_row_with_both_pos_and_pitch_filled(self, tmp_path):
        csv_path = tmp_path / 'vocab.csv'
        _write_csv(csv_path, [_blank({
            '単語': 'ラッキーな', '品詞': '名詞', 'ピッチアクセント': '0', '英語訳': 'existing',
        })])
        before = csv_path.read_text(encoding='utf-8')
        with patch(_JITENDEX_PATCH, return_value={}), patch(_PITCH_PATCH, return_value=_NO_PITCH):
            repair_fields(csv_path)
        assert csv_path.read_text(encoding='utf-8') == before
