"""Tests for add_words.py."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jlpt_vocab.pipeline import make_csv_columns, LANGUAGES


def _write_csv(path, rows, columns):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def _mock_ollama(*args, **kwargs):
    langs = kwargs.get('langs', [])
    result = {
        '例文': '今日は食べる。', '例文振り仮名': '今日は食べる。',
        '英語例文': 'I eat today.', '日本語ターゲット': '食べる',
    }
    for lang in langs:
        abbrev = LANGUAGES[lang][0]
        result[f'{abbrev}語例文'] = f'(mock {lang})'
        result[f'{abbrev}語訳'] = f'(mock {lang} gloss)'
    return result


_OLLAMA_PATCH = 'jlpt_vocab.pipeline.ollama_generate'


class TestAddWords:
    def test_writes_custom_level(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words
            add_words(['食べる'], output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]['レベル'] == 'Custom'

    def test_creates_csv_with_header_if_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words
            add_words(['食べる'], output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == make_csv_columns(['french'])

    def test_appends_without_duplicate_header(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        cols = make_csv_columns(['french'])
        _write_csv(output, [{c: '' for c in cols} | {'単語': '走る', 'レベル': 'N4'}], cols)
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words
            add_words(['食べる'], output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            content = f.read()
        header = ','.join(cols)
        assert content.count(header) == 1
        words = [r['単語'] for r in csv.DictReader(open(output, encoding='utf-8'))]
        assert '走る' in words
        assert '食べる' in words

    def test_exits_on_column_mismatch(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        cols = make_csv_columns(['french'])
        _write_csv(output, [], cols)
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
        ):
            from scripts.add_words import add_words
            with pytest.raises(SystemExit) as exc_info:
                add_words(['食べる'], output, 'gemma4:e4b', ['french', 'spanish'])
        assert 'scripts/add_language.py' in str(exc_info.value)

    def test_skips_word_in_checkpoint(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        checkpoint = output.with_name('out_checkpoint.json')
        checkpoint.write_text(json.dumps(['食べる']), encoding='utf-8')
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama) as mock_gen,
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words
            add_words(['食べる'], output, 'gemma4:e4b', ['french'])
        mock_gen.assert_not_called()

    def test_furigana_bracket_notation(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        jitendex = {'食[た]べる': {'品詞': '', '英語訳': '', '読み': '', '例文': '', '英語例文': '', '例文振り仮名': ''}}
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value=jitendex),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
        ):
            from scripts.add_words import add_words
            add_words(['食[た]べる'], output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]['振り仮名'] == '<ruby>食<rt>た</rt></ruby>べる'

    def test_furigana_kanji_only_with_reading(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        jitendex = {'猫背': {'品詞': '名詞', '英語訳': 'stoop', '読み': 'ねこぜ', '例文': '', '英語例文': '', '例文振り仮名': ''}}
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value=jitendex),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
        ):
            from scripts.add_words import add_words
            add_words(['猫背'], output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]['振り仮名'] == '<ruby>猫背<rt>ねこぜ</rt></ruby>'

    def test_furigana_mixed_calls_ollama_furigana(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        jitendex = {'食べる': {'品詞': '一段動詞', '英語訳': 'to eat', '読み': 'たべる', '例文': '', '英語例文': '', '例文振り仮名': ''}}
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value=jitendex),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value='<ruby>食<rt>た</rt></ruby>べる') as mock_furi,
        ):
            from scripts.add_words import add_words
            add_words(['食べる'], output, 'gemma4:e4b', ['french'])
        mock_furi.assert_called_once()

    def test_furigana_empty_when_no_reading(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        jitendex = {'猫背': {'品詞': '名詞', '英語訳': 'stoop', '読み': '', '例文': '', '英語例文': '', '例文振り仮名': ''}}
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value=jitendex),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
        ):
            from scripts.add_words import add_words
            add_words(['猫背'], output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]['振り仮名'] == ''

    def test_words_from_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        words_file = tmp_path / 'words.txt'
        words_file.write_text('猫背\n蹴る\n', encoding='utf-8')
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words_from_args
            add_words_from_args([], words_file, output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            words = [r['単語'] for r in csv.DictReader(f)]
        assert words == ['猫背', '蹴る']

    def test_words_from_file_and_cli(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        words_file = tmp_path / 'words.txt'
        words_file.write_text('猫背\n蹴る\n', encoding='utf-8')
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words_from_args
            # 猫背 appears in both file and CLI; should appear only once
            add_words_from_args(['納豆', '猫背'], words_file, output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            words = [r['単語'] for r in csv.DictReader(f)]
        assert words == ['猫背', '蹴る', '納豆']

    def test_file_blank_lines_and_comments_skipped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        words_file = tmp_path / 'words.txt'
        words_file.write_text('猫背\n\n# this is a comment\n蹴る\n', encoding='utf-8')
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words_from_args
            add_words_from_args([], words_file, output, 'gemma4:e4b', ['french'])
        with open(output, newline='', encoding='utf-8') as f:
            words = [r['単語'] for r in csv.DictReader(f)]
        assert words == ['猫背', '蹴る']

    def test_no_words_raises_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        from scripts.add_words import add_words_from_args
        with pytest.raises(SystemExit):
            add_words_from_args([], None, output, 'gemma4:e4b', ['french'])

    def test_file_not_found_raises_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path / 'out.csv'
        from scripts.add_words import add_words_from_args
        with pytest.raises(SystemExit):
            add_words_from_args([], tmp_path / 'nonexistent.txt', output, 'gemma4:e4b', ['french'])

    def test_uses_default_output_when_no_output_given(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with (
            patch('scripts.add_words.ensure_all'),
            patch('scripts.add_words.build_jitendex_index', return_value={}),
            patch('scripts.add_words.build_jmdict_index', return_value={}),
            patch(_OLLAMA_PATCH, side_effect=_mock_ollama),
            patch('scripts.add_words.get_pitch_columns', return_value={'ピッチアクセント': '', 'ピッチアクセント図': ''}),
            patch('scripts.add_words.ollama_generate_furigana', return_value=''),
        ):
            from scripts.add_words import add_words, DEFAULT_OUTPUT
            add_words(['食べる'], DEFAULT_OUTPUT, 'gemma4:e4b', ['french'])
        assert (tmp_path / 'output' / 'custom_words.csv').exists()
