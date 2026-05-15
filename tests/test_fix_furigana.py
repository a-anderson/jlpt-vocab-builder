"""Tests for scripts/fix_furigana.py."""

import json
from unittest.mock import patch

import pytest

from scripts.fix_furigana import (
    build_reading_index,
    fix_word,
    needs_fix,
    process_lines,
    reading_from_notation,
    strip_brackets,
)

_CHAT_PATCH = 'scripts.fix_furigana._chat'


# ---------------------------------------------------------------------------
# strip_brackets
# ---------------------------------------------------------------------------

class TestStripBrackets:
    def test_single_bracket(self):
        assert strip_brackets('食[た]べる') == '食べる'

    def test_multiple_brackets(self):
        assert strip_brackets('火[か]曜[よう]日[び]') == '火曜日'

    def test_empty_bracket(self):
        assert strip_brackets('単[]') == '単'

    def test_whole_word_bracket(self):
        assert strip_brackets('今朝[けさ]') == '今朝'

    def test_no_brackets_unchanged(self):
        assert strip_brackets('ある') == 'ある'

    def test_non_kana_in_bracket_stripped(self):
        assert strip_brackets('お土[omiyage]産') == 'お土産'


# ---------------------------------------------------------------------------
# needs_fix
# ---------------------------------------------------------------------------

class TestNeedsFix:

    # --- Valid notation — should return False ---

    def test_per_kanji_valid(self):
        assert needs_fix('火[か]曜[よう]日[び]') is False

    def test_single_kanji_with_bracket(self):
        assert needs_fix('食[た]べる') is False

    def test_whole_compound_ateji(self):
        # Bracket on last kanji covers the whole compound — valid
        assert needs_fix('今朝[けさ]') is False

    def test_whole_compound_with_kana_suffix(self):
        assert needs_fix('練習[れんしゅう]する') is False

    def test_iteration_mark_compound(self):
        # 々 must be treated as part of the kanji run
        assert needs_fix('色々[いろいろ]') is False
        assert needs_fix('時々[ときどき]') is False

    def test_honorific_prefix_whole_compound(self):
        # お is bare kana prefix; 土産 ends the kanji run with a bracket
        assert needs_fix('お土産[おみやげ]') is False

    def test_per_kanji_with_honorific_prefix(self):
        assert needs_fix('お花[はな]見[み]') is False

    def test_pure_hiragana(self):
        assert needs_fix('ある') is False

    def test_pure_katakana(self):
        assert needs_fix('テレビ') is False

    def test_mixed_kana_no_kanji(self):
        assert needs_fix('ありがとうございます') is False

    # --- Invalid notation — should return True ---

    def test_terminal_kanji_without_bracket(self):
        # 曜 and 日 are terminal kanji with no bracket
        assert needs_fix('火[かようび]曜日') is True

    def test_second_kanji_without_bracket(self):
        assert needs_fix('簡[かんたん]単') is True

    def test_empty_bracket(self):
        assert needs_fix('単[]') is True

    def test_empty_bracket_mid_word(self):
        assert needs_fix('火[か]曜[]日[び]') is True

    def test_kanji_repeated_as_its_own_reading(self):
        # Kanji 待 used as its own reading — non-kana in bracket
        assert needs_fix('待[待]') is True

    def test_romaji_in_bracket(self):
        assert needs_fix('お土[omiyage]産') is True

    def test_bracket_after_kana(self):
        # Bracket attached to kana い rather than to the kanji 洗
        assert needs_fix('洗い[あらい]') is True

    def test_all_kanji_unbracketed(self):
        assert needs_fix('火曜日') is True

    def test_single_kanji_no_bracket(self):
        assert needs_fix('木') is True


# ---------------------------------------------------------------------------
# reading_from_notation
# ---------------------------------------------------------------------------

class TestReadingFromNotation:
    def test_per_kanji(self):
        assert reading_from_notation('火[か]曜[よう]日[び]') == 'かようび'

    def test_with_kana_suffix(self):
        assert reading_from_notation('食[た]べる') == 'たべる'

    def test_whole_compound(self):
        assert reading_from_notation('今朝[けさ]') == 'けさ'

    def test_honorific_prefix(self):
        # お is bare kana; 花 and 見 each have brackets
        assert reading_from_notation('お花[はな]見[み]') == 'おはなみ'

    def test_pure_kana(self):
        assert reading_from_notation('ある') == 'ある'

    def test_with_suru_suffix(self):
        assert reading_from_notation('練習[れんしゅう]する') == 'れんしゅうする'

    def test_iteration_mark_compound(self):
        assert reading_from_notation('色々[いろいろ]') == 'いろいろ'


# ---------------------------------------------------------------------------
# build_reading_index
# ---------------------------------------------------------------------------

class TestBuildReadingIndex:
    def _write_bank(self, directory, name, entries):
        path = directory / name
        path.write_text(json.dumps(entries), encoding='utf-8')

    def test_reads_single_bank(self, tmp_path):
        self._write_bank(tmp_path, 'term_bank_1.json', [
            ['火曜日', 'かようび', '', '', 0, [], 1, ''],
        ])
        index = build_reading_index(tmp_path)
        assert index['火曜日'] == 'かようび'

    def test_keeps_highest_popularity(self, tmp_path):
        # Lower-popularity entry comes first in file order
        self._write_bank(tmp_path, 'term_bank_1.json', [
            ['食べる', 'たべる', '', '', -5, [], 1, ''],
            ['食べる', 'くう', '', '', -10, [], 2, ''],  # lower popularity
        ])
        index = build_reading_index(tmp_path)
        assert index['食べる'] == 'たべる'

    def test_highest_popularity_across_banks(self, tmp_path):
        self._write_bank(tmp_path, 'term_bank_1.json', [
            ['食べる', 'たべる', '', '', 10, [], 1, ''],
        ])
        self._write_bank(tmp_path, 'term_bank_2.json', [
            ['食べる', 'くう', '', '', 5, [], 2, ''],
        ])
        index = build_reading_index(tmp_path)
        assert index['食べる'] == 'たべる'

    def test_empty_directory(self, tmp_path):
        assert build_reading_index(tmp_path) == {}

    def test_multiple_terms(self, tmp_path):
        self._write_bank(tmp_path, 'term_bank_1.json', [
            ['火曜日', 'かようび', '', '', 0, [], 1, ''],
            ['水曜日', 'すいようび', '', '', 0, [], 2, ''],
        ])
        index = build_reading_index(tmp_path)
        assert index == {'火曜日': 'かようび', '水曜日': 'すいようび'}


# ---------------------------------------------------------------------------
# fix_word
# ---------------------------------------------------------------------------

class TestFixWord:
    def test_valid_per_kanji_output_accepted(self):
        with patch(_CHAT_PATCH, return_value='火[か]曜[よう]日[び]'):
            result = fix_word('火曜日', 'かようび', 'model')
        assert result == '火[か]曜[よう]日[び]'

    def test_valid_ateji_whole_compound_accepted(self):
        with patch(_CHAT_PATCH, return_value='今朝[けさ]'):
            result = fix_word('今朝', 'けさ', 'model')
        assert result == '今朝[けさ]'

    def test_honorific_prefix_per_kanji_accepted(self):
        with patch(_CHAT_PATCH, return_value='お花[はな]見[み]'):
            result = fix_word('お花見', 'おはなみ', 'model')
        assert result == 'お花[はな]見[み]'

    def test_model_output_whitespace_stripped(self):
        with patch(_CHAT_PATCH, return_value='  火[か]曜[よう]日[び]  '):
            result = fix_word('火曜日', 'かようび', 'model')
        assert result == '火[か]曜[よう]日[び]'

    def test_returns_none_when_characters_changed(self):
        # Model swapped a kanji
        with patch(_CHAT_PATCH, return_value='水[か]曜[よう]日[び]'):
            assert fix_word('火曜日', 'かようび', 'model') is None

    def test_returns_none_when_bracket_contains_romaji(self):
        with patch(_CHAT_PATCH, return_value='お土[o]産[miyage]'):
            assert fix_word('お土産', 'おみやげ', 'model') is None

    def test_returns_none_when_bracket_is_empty(self):
        with patch(_CHAT_PATCH, return_value='火[か]曜[]日[び]'):
            assert fix_word('火曜日', 'かようび', 'model') is None

    def test_returns_none_when_reading_does_not_match(self):
        # Model invented readings that don't match the known reading あさって
        with patch(_CHAT_PATCH, return_value='明[あ]後[ご]日[か]'):
            assert fix_word('明後日', 'あさって', 'model') is None

    def test_honorific_prefix_whole_compound_accepted(self):
        # お is bare kana in the plain word; the bracket absorbs it into おみやげ.
        # The validation strips leading bare kana before comparing bracket sum.
        with patch(_CHAT_PATCH, return_value='お土産[おみやげ]'):
            result = fix_word('お土産', 'おみやげ', 'model')
        assert result == 'お土産[おみやげ]'

    def test_returns_none_when_model_drops_characters(self):
        with patch(_CHAT_PATCH, return_value='火曜[かようび]'):
            # strip_brackets → 火曜 ≠ 火曜日
            assert fix_word('火曜日', 'かようび', 'model') is None


# ---------------------------------------------------------------------------
# process_lines (pipeline integration)
# ---------------------------------------------------------------------------

class TestProcessLines:
    def test_fixes_broken_notation(self):
        lines = ['火[かようび]曜日,']
        reading_index = {'火曜日': 'かようび'}
        with patch(_CHAT_PATCH, return_value='火[か]曜[よう]日[び]'):
            fixed, count = process_lines(lines, reading_index, 'model')
        assert fixed == ['火[か]曜[よう]日[び],']
        assert count == 1

    def test_preserves_correct_notation(self):
        lines = ['火[か]曜[よう]日[び],']
        fixed, count = process_lines(lines, {}, 'model')
        assert fixed == ['火[か]曜[よう]日[び],']
        assert count == 0

    def test_preserves_csv_trailing_comma(self):
        lines = ['簡[かんたん]単,']
        reading_index = {'簡単': 'かんたん'}
        with patch(_CHAT_PATCH, return_value='簡[かん]単[たん]'):
            fixed, count = process_lines(lines, reading_index, 'model')
        assert fixed[0].endswith(',')

    def test_plain_text_no_trailing_comma(self):
        lines = ['簡[かんたん]単']
        reading_index = {'簡単': 'かんたん'}
        with patch(_CHAT_PATCH, return_value='簡[かん]単[たん]'):
            fixed, count = process_lines(lines, reading_index, 'model')
        assert not fixed[0].endswith(',')

    def test_skips_comment_lines(self):
        lines = ['# N5 verbs', '食[た]べる,']
        fixed, count = process_lines(lines, {}, 'model')
        assert fixed[0] == '# N5 verbs'
        assert count == 0

    def test_skips_blank_lines(self):
        lines = ['', '食[た]べる,']
        fixed, count = process_lines(lines, {}, 'model')
        assert fixed[0] == ''
        assert count == 0

    def test_skips_pure_kana(self):
        lines = ['ある,', 'テレビ,']
        fixed, count = process_lines(lines, {}, 'model')
        assert fixed == ['ある,', 'テレビ,']
        assert count == 0

    def test_uses_reading_from_broken_notation_when_not_in_index(self):
        # 簡単 not in index; reading extracted from broken brackets: かんたん
        lines = ['簡[かんたん]単,']
        with patch(_CHAT_PATCH, return_value='簡[かん]単[たん]'):
            fixed, count = process_lines(lines, {}, 'model')
        assert fixed == ['簡[かん]単[たん],']

    def test_fallback_to_whole_compound_when_fix_word_returns_none(self):
        lines = ['明[あさって]後日,']
        reading_index = {'明後日': 'あさって'}
        with patch(_CHAT_PATCH, return_value='明[あ]後[ご]日[か]'):  # wrong reading → None
            fixed, count = process_lines(lines, reading_index, 'model')
        # Fallback: bracket after last kanji (日) with full reading
        assert fixed == ['明後日[あさって],']
        assert count == 1

    def test_word_already_correct_not_counted_as_changed(self):
        # word that needs_fix passes but fix_word returns the same thing
        lines = ['火[か]曜[よう]日[び],']
        fixed, count = process_lines(lines, {}, 'model')
        assert count == 0

    def test_processes_multiple_lines(self):
        lines = [
            '# comment',
            '火[か]曜[よう]日[び],',         # already correct
            '簡[かんたん]単,',               # needs fix
            'ある,',                          # pure kana, skip
        ]
        reading_index = {'簡単': 'かんたん'}
        with patch(_CHAT_PATCH, return_value='簡[かん]単[たん]'):
            fixed, count = process_lines(lines, reading_index, 'model')
        assert fixed[0] == '# comment'
        assert fixed[1] == '火[か]曜[よう]日[び],'
        assert fixed[2] == '簡[かん]単[たん],'
        assert fixed[3] == 'ある,'
        assert count == 1

    def test_skips_word_with_no_known_reading(self):
        # Kanji with no bracket and no entry in the reading index — reading_from_notation
        # returns '' because there are no brackets or kana to extract from.
        lines = ['木,']
        fixed, count = process_lines(lines, {}, 'model')
        assert fixed == ['木,']
        assert count == 0
