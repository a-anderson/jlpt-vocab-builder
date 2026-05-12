"""Tests for build_jlpt_csv helper functions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_jlpt_csv import word_in_sentence, extract_target, _ts_field, _parse_json, _empty_ollama


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
    def test_contains_all_expected_keys(self):
        result = _empty_ollama()
        expected = {'例文', '英語例文', '仏語例文', '例文振り仮名', '日本語ターゲット', '仏語訳'}
        assert set(result.keys()) == expected

    def test_all_values_are_empty_strings(self):
        assert all(v == '' for v in _empty_ollama().values())


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
