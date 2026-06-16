"""Tests for scripts/add_particle.py and jlpt_vocab.pipeline.get_particle."""

import csv
import sys
from pathlib import Path

import pytest

from jlpt_vocab.pipeline import get_particle
from scripts.add_particle import main


COLUMNS = ['単語', '振り仮名', '品詞', '英語訳', 'レベル']


def _write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("pos,expected", [
    ("名詞", "が"),
    ("な形容詞", "が"),
    ("の形容詞", "が"),
    ("代名詞", "が"),
    ("い形容詞", "よ"),
    ("他動詞", "よ"),
    ("自動詞", "よ"),
    ("一段動詞", "よ"),
    ("五段動詞（う）", "よ"),
    ("副詞", ""),
    ("助詞", ""),
    ("接続詞", ""),
    ("表現", ""),
    ("", ""),
])
def test_get_particle(pos, expected):
    assert get_particle(pos) == expected


def test_main_transforms_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / 'test.csv'
    _write_csv(csv_path, [
        {'単語': '犬', '振り仮名': 'いぬ', '品詞': '名詞', '英語訳': 'dog', 'レベル': 'n5'},
        {'単語': '食べる', '振り仮名': '<ruby>食<rt>た</rt></ruby>べる', '品詞': '一段動詞', '英語訳': 'eat', 'レベル': 'n5'},
        {'単語': 'でも', '振り仮名': 'でも', '品詞': '接続詞', '英語訳': 'but', 'レベル': 'n5'},
    ])
    monkeypatch.setattr(sys, 'argv', ['add_particle.py', '--input', str(csv_path)])
    main()
    rows = _read_csv(csv_path)
    assert rows[0]['単語'] == '犬が'
    assert rows[0]['振り仮名'] == 'いぬが'
    assert rows[1]['単語'] == '食べるよ'
    assert rows[2]['単語'] == 'でも'  # no particle for conjunctions


def test_main_idempotent(tmp_path, monkeypatch):
    csv_path = tmp_path / 'test.csv'
    _write_csv(csv_path, [
        {'単語': '犬が', '振り仮名': 'いぬが', '品詞': '名詞', '英語訳': 'dog', 'レベル': 'n5'},
    ])
    monkeypatch.setattr(sys, 'argv', ['add_particle.py', '--input', str(csv_path)])
    main()
    rows = _read_csv(csv_path)
    assert rows[0]['単語'] == '犬が'  # not 犬がが


def test_main_creates_backup_on_inplace_write(tmp_path, monkeypatch):
    csv_path = tmp_path / 'test.csv'
    _write_csv(csv_path, [
        {'単語': '犬', '振り仮名': 'いぬ', '品詞': '名詞', '英語訳': 'dog', 'レベル': 'n5'},
    ])
    monkeypatch.setattr(sys, 'argv', ['add_particle.py', '--input', str(csv_path)])
    main()
    assert (tmp_path / 'test.bak').exists()


def test_main_no_backup_when_writing_to_separate_file(tmp_path, monkeypatch):
    input_path = tmp_path / 'input.csv'
    output_path = tmp_path / 'output.csv'
    _write_csv(input_path, [
        {'単語': '犬', '振り仮名': 'いぬ', '品詞': '名詞', '英語訳': 'dog', 'レベル': 'n5'},
    ])
    monkeypatch.setattr(sys, 'argv', ['add_particle.py', '--input', str(input_path), '--output', str(output_path)])
    main()
    assert not (tmp_path / 'input.bak').exists()


def test_main_output_separate_file(tmp_path, monkeypatch):
    input_path = tmp_path / 'input.csv'
    output_path = tmp_path / 'output.csv'
    _write_csv(input_path, [
        {'単語': '猫', '振り仮名': 'ねこ', '品詞': '名詞', '英語訳': 'cat', 'レベル': 'n5'},
    ])
    monkeypatch.setattr(sys, 'argv', ['add_particle.py', '--input', str(input_path), '--output', str(output_path)])
    main()
    assert _read_csv(input_path)[0]['単語'] == '猫'  # input untouched
    assert _read_csv(output_path)[0]['単語'] == '猫が'
