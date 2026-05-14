"""Tests for add_language.py."""

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


@pytest.fixture
def existing_csv(tmp_path):
    columns = make_csv_columns(['french'])
    rows = [
        {c: '' for c in columns} | {
            '単語': '食べる', '例文': '毎日食べる。', '英語訳': 'to eat',
            '英語例文': 'I eat every day.', 'レベル': 'N4',
        },
        {c: '' for c in columns} | {
            '単語': '飲む', '例文': '水を飲む。', '英語訳': 'to drink',
            '英語例文': 'I drink water.', 'レベル': 'N4',
        },
    ]
    path = tmp_path / 'test.csv'
    _write_csv(path, rows, columns)
    return path


def _mock_ollama(word, model, en_gloss, pos, need_sentence, **kwargs):
    langs = kwargs.get('langs', [])
    result = {'例文振り仮名': '', '日本語ターゲット': ''}
    for lang in langs:
        abbrev = LANGUAGES[lang][0]
        result[f'{abbrev}語例文'] = f'(mock {lang} translation)'
        result[f'{abbrev}語訳'] = f'(mock {lang} gloss)'
    return result


class TestAddLanguageColumns:
    def test_adds_correct_column_names(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate', side_effect=_mock_ollama),
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')
        with open(existing_csv, newline='', encoding='utf-8') as f:
            fieldnames = csv.DictReader(f).fieldnames
        assert '西語訳' in fieldnames
        assert '西語例文' in fieldnames

    def test_preserves_existing_columns(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        original_cols = make_csv_columns(['french'])
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate', side_effect=_mock_ollama),
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')
        with open(existing_csv, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for col in original_cols:
            assert col in rows[0]

    def test_gloss_lookup_hit_skips_ollama(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Rows have no example sentence — only the gloss lookup matters
        columns = make_csv_columns(['french'])
        rows = [
            {c: '' for c in columns} | {'単語': '食べる', '英語訳': 'to eat', 'レベル': 'N4'},
            {c: '' for c in columns} | {'単語': '飲む', '英語訳': 'to drink', 'レベル': 'N4'},
        ]
        path = tmp_path / 'test.csv'
        _write_csv(path, rows, columns)
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={'食べる': 'manger', '飲む': 'boire'}),
            patch('scripts.add_language.ollama_generate') as mock_gen,
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(path, 'spanish', 'gemma4:e4b')
        mock_gen.assert_not_called()

    def test_gloss_lookup_miss_calls_ollama(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate', side_effect=_mock_ollama) as mock_gen,
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')
        assert mock_gen.call_count == 2  # once per word

    def test_skips_words_in_checkpoint_and_tmp_exists(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        checkpoint_path = existing_csv.with_name(f'{existing_csv.stem}_add_spanish_checkpoint.json')
        checkpoint_path.write_text(json.dumps(['食べる']), encoding='utf-8')
        # Create a .tmp file as if a prior run partially completed
        out_path = existing_csv.with_suffix('.tmp')
        cols = make_csv_columns(['french']) + ['西語訳', '西語例文']
        _write_csv(out_path, [
            {c: '' for c in cols} | {'単語': '食べる', '西語訳': 'manger', '西語例文': 'ok'},
        ], cols)
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate', side_effect=_mock_ollama) as mock_gen,
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')
        # 食べる was checkpointed — Ollama should only be called for 飲む
        called_words = [c.kwargs.get('word') or c.args[0] for c in mock_gen.call_args_list]
        assert '食べる' not in called_words

    def test_stale_checkpoint_without_tmp_returns_early(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        checkpoint_path = existing_csv.with_name(f'{existing_csv.stem}_add_spanish_checkpoint.json')
        checkpoint_path.write_text(json.dumps(['食べる', '飲む']), encoding='utf-8')
        mtime_before = existing_csv.stat().st_mtime
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate') as mock_gen,
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')
        mock_gen.assert_not_called()
        assert not checkpoint_path.exists()
        assert existing_csv.stat().st_mtime == mtime_before

    def test_already_has_column_does_nothing(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Add 西語訳 column to existing CSV
        cols = make_csv_columns(['french']) + ['西語訳', '西語例文']
        rows = [
            {c: '' for c in cols} | {'単語': '食べる'},
            {c: '' for c in cols} | {'単語': '飲む'},
        ]
        _write_csv(existing_csv, rows, cols)
        mtime_before = existing_csv.stat().st_mtime
        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate') as mock_gen,
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')
        mock_gen.assert_not_called()
        assert existing_csv.stat().st_mtime == mtime_before

    def test_atomic_write_uses_tmp_file(self, existing_csv, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        replaced_paths = []
        original_replace = Path.replace

        def capture_replace(self, target):
            replaced_paths.append(self)
            return original_replace(self, target)

        with (
            patch('scripts.add_language.ensure_jmdict'),
            patch('scripts.add_language.build_jmdict_index', return_value={}),
            patch('scripts.add_language.ollama_generate', side_effect=_mock_ollama),
            patch.object(Path, 'replace', capture_replace),
        ):
            from scripts.add_language import add_language_columns
            add_language_columns(existing_csv, 'spanish', 'gemma4:e4b')

        assert any(str(p).endswith('.tmp') for p in replaced_paths)
