"""Tests for pipeline helper functions."""

from pathlib import Path
from unittest.mock import patch

from jlpt_vocab import pipeline
import csv as _csv

from jlpt_vocab.pipeline import (
    word_in_sentence, extract_target, _ts_field, _parse_json, _empty_ollama,
    make_csv_columns, ollama_generate_furigana,
    find_repair_candidates, detect_csv_languages,
)
from tests.conftest import requires_unidic


@requires_unidic
class TestWordInSentence:
    def test_exact_match(self):
        assert word_in_sentence('食べる', 'もっと果物を食べるべきです。')

    def test_no_false_positive_substring(self):
        # 夫 must not match inside 大丈夫 — the core guard this function provides
        assert not word_in_sentence('夫', '大丈夫ですか。')

    def test_lemma_match_inflected(self):
        # 走った is an inflected form; lemma should be 走る
        assert word_in_sentence('走る', '公園で走った。')

    def test_word_not_in_sentence(self):
        assert not word_in_sentence('食べる', '今日は晴れです。')

    def test_empty_sentence(self):
        assert not word_in_sentence('食べる', '')

    def test_noun_present(self):
        assert word_in_sentence('学校', '学校へ行きます。')

    def test_noun_not_present(self):
        assert not word_in_sentence('病院', '学校へ行きます。')


@requires_unidic
class TestExtractTarget:
    def test_returns_surface_form(self):
        # fugashi splits 食べた into 食べ (stem, lemma=食べる) + た (aux)
        # extract_target returns the matching token's surface, which is 食べ
        result = extract_target('食べる', 'りんごを食べた。')
        assert result == '食べ'

    def test_exact_surface_match(self):
        result = extract_target('学校', '学校へ行きます。')
        assert result == '学校'

    def test_word_absent_returns_empty(self):
        result = extract_target('食べる', '今日は晴れです。')
        assert result == ''

    def test_empty_sentence_returns_empty(self):
        assert extract_target('食べる', '') == ''


class TestFetchChadmuroDedup:
    def test_counter_kanji_deduplicated(self):
        from unittest.mock import patch, MagicMock
        import jlpt_vocab.pipeline as pl
        ts_text = '{ id: 1, kanji: "～杯、～杯、～杯", japanese: "～ 杯[はい]、～ 杯[ぱい]、～ 杯[ばい]", english: "cup" }'
        mock_resp = MagicMock()
        mock_resp.text = ts_text
        mock_resp.raise_for_status = lambda: None
        with patch('jlpt_vocab.pipeline.requests.get', return_value=mock_resp):
            words = pl.fetch_chadmuro_words('n4')
        assert words[0]['単語'] == '～杯'

    def test_furigana_raw_preserved_with_all_readings(self):
        from unittest.mock import patch, MagicMock
        import jlpt_vocab.pipeline as pl
        ts_text = '{ id: 1, kanji: "～杯、～杯、～杯", japanese: "～ 杯[はい]、～ 杯[ぱい]、～ 杯[ばい]", english: "cup" }'
        mock_resp = MagicMock()
        mock_resp.text = ts_text
        mock_resp.raise_for_status = lambda: None
        with patch('jlpt_vocab.pipeline.requests.get', return_value=mock_resp):
            words = pl.fetch_chadmuro_words('n4')
        assert words[0]['振り仮名_raw'] == '～ 杯[はい]、～ 杯[ぱい]、～ 杯[ばい]'

    def test_unique_parts_unchanged(self):
        from unittest.mock import patch, MagicMock
        import jlpt_vocab.pipeline as pl
        ts_text = '{ id: 1, kanji: "一、二、三", japanese: "いち、に、さん", english: "one two three" }'
        mock_resp = MagicMock()
        mock_resp.text = ts_text
        mock_resp.raise_for_status = lambda: None
        with patch('jlpt_vocab.pipeline.requests.get', return_value=mock_resp):
            words = pl.fetch_chadmuro_words('n4')
        assert words[0]['単語'] == '一、二、三'


class TestTsField:
    def test_extracts_kanji(self):
        entry = 'kanji: "食べる"'
        assert _ts_field(entry, 'kanji') == '食べる'

    def test_extracts_english(self):
        entry = 'english: "to eat"'
        assert _ts_field(entry, 'english') == 'to eat'

    def test_missing_field_returns_none(self):
        assert _ts_field('kanji: "食べる"', 'japanese') is None

    def test_with_surrounding_context(self):
        entry = '{ kanji: "行く", japanese: "いく", english: "to go" }'
        assert _ts_field(entry, 'kanji') == '行く'
        assert _ts_field(entry, 'english') == 'to go'


class TestEmptyOllama:
    def test_contains_base_keys_only_when_no_langs(self):
        result = _empty_ollama()
        assert set(result.keys()) == {'例文', '英語例文', '例文振り仮名', '日本語ターゲット'}

    def test_all_values_are_empty_strings(self):
        assert all(v == '' for v in _empty_ollama().values())

    def test_empty_ollama_no_langs(self):
        result = _empty_ollama()
        assert set(result.keys()) == {'例文', '英語例文', '例文振り仮名', '日本語ターゲット'}

    def test_empty_ollama_includes_all_lang_keys(self):
        result = _empty_ollama(['french', 'spanish'])
        assert '仏語例文' in result
        assert '西語例文' in result
        assert '仏語訳' in result
        assert '西語訳' in result
        assert '例文' in result


class TestMakeCsvColumns:
    def test_french_only(self):
        cols = make_csv_columns(['french'])
        assert cols == [
            '単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
            '英語訳', '仏語訳', '例文', '例文振り仮名', '英語例文', '仏語例文',
            '日本語ターゲット', 'レベル',
        ]
        assert len(cols) == 13

    def test_two_languages(self):
        cols = make_csv_columns(['french', 'spanish'])
        assert '仏語訳' in cols
        assert '西語訳' in cols
        assert '仏語例文' in cols
        assert '西語例文' in cols
        assert cols.index('仏語訳') < cols.index('西語訳')
        assert cols.index('仏語例文') < cols.index('西語例文')
        assert len(cols) == 15

    def test_gloss_before_example(self):
        cols = make_csv_columns(['french', 'spanish'])
        gloss_indices = [cols.index('仏語訳'), cols.index('西語訳')]
        example_indices = [cols.index('仏語例文'), cols.index('西語例文')]
        assert all(gi < cols.index('例文') for gi in gloss_indices)
        assert all(ei > cols.index('英語例文') for ei in example_indices)

    def test_english_only(self):
        cols = make_csv_columns([])
        assert cols == [
            '単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
            '英語訳', '例文', '例文振り仮名', '英語例文',
            '日本語ターゲット', 'レベル',
        ]
        assert len(cols) == 11
        assert not any('語訳' in c and c != '英語訳' for c in cols)
        assert not any('語例文' in c and c != '英語例文' for c in cols)


class TestOllamaGenerateFurigana:
    def test_returns_ruby_html(self):
        with patch('jlpt_vocab.pipeline._ollama_chat', return_value='食[た]べる'):
            result = ollama_generate_furigana('食べる', 'たべる', 'gemma4:e4b')
        assert result == '<ruby>食<rt>た</rt></ruby>べる'

    def test_returns_empty_on_failure(self):
        with patch('jlpt_vocab.pipeline._ollama_chat', side_effect=Exception('fail')):
            result = ollama_generate_furigana('食べる', 'たべる', 'gemma4:e4b')
        assert result == ''

    def test_returns_empty_when_no_client(self):
        original = pipeline.ollama_client
        try:
            pipeline.ollama_client = None
            with patch('jlpt_vocab.pipeline._ollama_chat') as mock_chat:
                result = ollama_generate_furigana('食べる', 'たべる', 'gemma4:e4b')
            mock_chat.assert_not_called()
            assert result == ''
        finally:
            pipeline.ollama_client = original


def _write_csv(path, rows, columns):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = _csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


_REPAIR_COLS = make_csv_columns(['french'])


class TestFindRepairCandidates:
    def test_returns_empty_field_words(self, tmp_path):
        path = tmp_path / 'test.csv'
        rows = [
            {c: 'x' for c in _REPAIR_COLS} | {'単語': '食べる'},
            {c: 'x' for c in _REPAIR_COLS} | {'単語': '走る', '例文振り仮名': ''},
        ]
        _write_csv(path, rows, _REPAIR_COLS)
        result = find_repair_candidates(path, ['例文振り仮名'])
        assert '走る' in result
        assert '食べる' not in result

    def test_ignores_complete_rows(self, tmp_path):
        path = tmp_path / 'test.csv'
        rows = [{c: 'x' for c in _REPAIR_COLS} | {'単語': '食べる'}]
        _write_csv(path, rows, _REPAIR_COLS)
        assert find_repair_candidates(path, ['例文振り仮名']) == set()

    def test_missing_csv_returns_empty_set(self, tmp_path):
        assert find_repair_candidates(tmp_path / 'missing.csv', ['例文振り仮名']) == set()

    def test_short_row_treated_as_empty(self, tmp_path):
        # csv.DictReader fills trailing missing fields with None (restval default).
        # Write a raw CSV where one row has fewer fields than the header to reproduce
        # the real failure mode: a row written with English-only columns into a
        # multi-language CSV leaves the last columns as None when read back.
        path = tmp_path / 'test.csv'
        cols = list(_REPAIR_COLS)
        # 単語 + (len(cols)-3) filler = len(cols)-2 fields: 2 fewer than the header,
        # so DictReader sets the last two columns to None.
        short_row = '食べる' + ',x' * (len(cols) - 3)
        assert short_row.count(',') == len(cols) - 3  # sanity: len(cols)-2 fields total
        path.write_text(','.join(cols) + '\n' + short_row + '\n', encoding='utf-8')
        result = find_repair_candidates(path, [cols[-1]])
        assert '食べる' in result

    def test_checks_only_given_cols(self, tmp_path):
        path = tmp_path / 'test.csv'
        rows = [{c: '' for c in _REPAIR_COLS} | {'単語': '食べる', '例文振り仮名': 'ok'}]
        _write_csv(path, rows, _REPAIR_COLS)
        # Only checking 例文振り仮名 which is non-empty; other empty cols not in repair_cols
        assert find_repair_candidates(path, ['例文振り仮名']) == set()


class TestBuildArgparse:
    def test_languages_defaults_to_english_only(self):
        from scripts.build import _make_parser
        args = _make_parser().parse_args(['--model', 'gemma4:e4b'])
        assert args.languages == []

    def test_languages_accepts_single_language(self):
        from scripts.build import _make_parser
        args = _make_parser().parse_args(['--model', 'gemma4:e4b', '--languages', 'french'])
        assert args.languages == ['french']

    def test_languages_accepts_multiple(self):
        from scripts.build import _make_parser
        args = _make_parser().parse_args(['--model', 'gemma4:e4b', '--languages', 'french', 'spanish'])
        assert args.languages == ['french', 'spanish']

    def test_resume_infers_languages_from_existing_csv(self, tmp_path):
        # main() should detect languages from the CSV header when --resume is used
        # without --languages, so resumed words are written with the correct columns.
        from unittest.mock import patch
        import scripts.build as build_mod
        path = tmp_path / 'vocab.csv'
        _write_csv(path, [], make_csv_columns(['french']))
        captured = {}

        def fake_process_word(word, model, jitendex, lang_indexes, langs, **kw):
            captured['langs'] = langs
            raise SystemExit(0)

        argv = ['build.py', '--model', 'gemma4:e4b', '--resume', '--output', str(path)]
        with patch('sys.argv', argv), \
             patch('scripts.build.ensure_all'), \
             patch('scripts.build.fetch_chadmuro_words', return_value=[{'単語': '食べる', '振り仮名_raw': '食べる', '英語訳_raw': 'to eat', 'レベル': 'N4'}]), \
             patch('scripts.build.build_jitendex_index', return_value={}), \
             patch('scripts.build.build_jmdict_index', return_value={}), \
             patch('scripts.build.process_word', side_effect=fake_process_word):
            try:
                build_mod.main()
            except SystemExit:
                pass
        assert captured.get('langs') == ['french']

    def test_resume_explicit_languages_not_overridden(self, tmp_path):
        from unittest.mock import patch
        import scripts.build as build_mod
        path = tmp_path / 'vocab.csv'
        _write_csv(path, [], make_csv_columns(['french']))
        captured = {}

        def fake_process_word(word, model, jitendex, lang_indexes, langs, **kw):
            captured['langs'] = langs
            raise SystemExit(0)

        argv = ['build.py', '--model', 'gemma4:e4b', '--resume', '--output', str(path), '--languages', 'spanish']
        with patch('sys.argv', argv), \
             patch('scripts.build.ensure_all'), \
             patch('scripts.build.fetch_chadmuro_words', return_value=[{'単語': '食べる', '振り仮名_raw': '食べる', '英語訳_raw': 'to eat', 'レベル': 'N4'}]), \
             patch('scripts.build.build_jitendex_index', return_value={}), \
             patch('scripts.build.build_jmdict_index', return_value={}), \
             patch('scripts.build.process_word', side_effect=fake_process_word):
            try:
                build_mod.main()
            except SystemExit:
                pass
        assert captured.get('langs') == ['spanish']

    def test_repair_infers_languages_and_reprocesses_incomplete_rows(self, tmp_path):
        # --repair must still detect languages from the CSV and drop+reprocess
        # incomplete rows — regression guard for the if/elif restructure.
        from unittest.mock import patch
        import json, scripts.build as build_mod
        path = tmp_path / 'vocab.csv'
        cols = make_csv_columns(['french'])
        _write_csv(path, [
            {c: 'ok' for c in cols} | {'単語': '食べる'},
            {c: '' for c in cols} | {'単語': '走る', '例文振り仮名': ''},
        ], cols)
        # Seed checkpoint so 食べる is treated as already done and only 走る is repaired.
        ckpt = path.with_name('vocab_checkpoint.json')
        ckpt.write_text(json.dumps(['食べる']), encoding='utf-8')
        captured = {}

        def fake_process_word(word, model, jitendex, lang_indexes, langs, **kw):
            captured['word'] = word
            captured['langs'] = langs
            raise SystemExit(0)

        argv = ['build.py', '--model', 'gemma4:e4b', '--repair', '--output', str(path)]
        with patch('sys.argv', argv), \
             patch('scripts.build.ensure_all'), \
             patch('scripts.build.fetch_chadmuro_words', return_value=[
                 {'単語': '食べる', '振り仮名_raw': '食べる', '英語訳_raw': 'to eat', 'レベル': 'N4'},
                 {'単語': '走る', '振り仮名_raw': '走る', '英語訳_raw': 'to run', 'レベル': 'N4'},
             ]), \
             patch('scripts.build.build_jitendex_index', return_value={}), \
             patch('scripts.build.build_jmdict_index', return_value={}), \
             patch('scripts.build.process_word', side_effect=fake_process_word):
            try:
                build_mod.main()
            except SystemExit:
                pass
        # 走る is the incomplete row — it should be the one reprocessed
        assert captured.get('word') == '走る'
        assert captured.get('langs') == ['french']


class TestDetectCsvLanguages:
    def test_single_language(self, tmp_path):
        path = tmp_path / 'test.csv'
        cols = make_csv_columns(['french'])
        _write_csv(path, [], cols)
        assert detect_csv_languages(path) == ['french']

    def test_multiple_languages(self, tmp_path):
        path = tmp_path / 'test.csv'
        cols = make_csv_columns(['french', 'spanish'])
        _write_csv(path, [], cols)
        result = detect_csv_languages(path)
        assert result == ['french', 'spanish']

    def test_missing_file_returns_empty(self, tmp_path):
        assert detect_csv_languages(tmp_path / 'missing.csv') == []

    def test_english_only_csv(self, tmp_path):
        path = tmp_path / 'test.csv'
        _write_csv(path, [], make_csv_columns([]))
        assert detect_csv_languages(path) == []


class TestParseJson:
    def test_plain_json(self):
        result = _parse_json('{"key": "value"}')
        assert result == {'key': 'value'}

    def test_strips_json_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        assert _parse_json(raw) == {'key': 'value'}

    def test_strips_plain_fence(self):
        raw = '```\n{"key": "value"}\n```'
        assert _parse_json(raw) == {'key': 'value'}

    def test_japanese_values(self):
        raw = '{"例文": "今日は晴れです。"}'
        assert _parse_json(raw) == {'例文': '今日は晴れです。'}
