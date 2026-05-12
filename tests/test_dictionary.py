"""Tests for dictionary index builders.

Unit tests use the sample_example_node fixture from conftest so they are
fast and offline. Integration tests read the local data files.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dictionary import _codes_to_hinshi, _find_pos_codes, _find_glosses, _ruby_html


# ---------------------------------------------------------------------------
# Unit tests for internal helpers (fast, offline, fixture-based)
# ---------------------------------------------------------------------------

class TestCodesToHinshi:
    def test_transitive_verb(self):
        assert _codes_to_hinshi(['vt']) == '他動詞'

    def test_intransitive_verb(self):
        assert _codes_to_hinshi(['vi']) == '自動詞'

    def test_vt_beats_vi_when_both_present(self):
        # vt must be checked before vi — not a substring match issue
        assert _codes_to_hinshi(['vi', 'vt']) == '他動詞'

    def test_ichidan_verb(self):
        assert _codes_to_hinshi(['v1']) == '一段動詞'

    def test_godan_u(self):
        assert _codes_to_hinshi(['v5u']) == '五段動詞（う）'

    def test_godan_r(self):
        assert _codes_to_hinshi(['v5r']) == '五段動詞（る）'

    def test_suru_verb(self):
        assert _codes_to_hinshi(['vs-i']) == 'サ変動詞（する）'

    def test_i_adjective(self):
        assert _codes_to_hinshi(['adj-i']) == 'い形容詞'

    def test_na_adjective(self):
        assert _codes_to_hinshi(['adj-na']) == 'な形容詞'

    def test_noun(self):
        assert _codes_to_hinshi(['n']) == '名詞'

    def test_adverb(self):
        assert _codes_to_hinshi(['adv']) == '副詞'

    def test_empty_codes(self):
        assert _codes_to_hinshi([]) == ''

    def test_unknown_code(self):
        assert _codes_to_hinshi(['xyz']) == ''

    def test_priority_order_v1_over_n(self):
        # v1 appears before n in the priority map
        assert _codes_to_hinshi(['n', 'v1']) == '一段動詞'

    def test_v5k_s_before_v5k(self):
        # v5k-s must be checked before v5k to avoid substring collision
        assert _codes_to_hinshi(['v5k-s']) == '五段動詞（く）'
        assert _codes_to_hinshi(['v5k']) == '五段動詞（く）'


class TestFindPosCodes:
    def test_extracts_codes(self, sample_pos_node):
        codes = _find_pos_codes(sample_pos_node)
        assert 'vt' in codes
        assert 'v1' in codes

    def test_ignores_non_pos_nodes(self, sample_pos_node):
        codes = _find_pos_codes(sample_pos_node)
        assert 'should not appear as POS' not in codes

    def test_empty_tree(self):
        assert _find_pos_codes([]) == []

    def test_nested_pos_node(self):
        node = {'tag': 'div', 'content': [
            {'tag': 'span', 'data': {'content': 'part-of-speech-info', 'code': 'n'}, 'content': '名詞'},
        ]}
        assert _find_pos_codes(node) == ['n']


class TestFindGlosses:
    def test_extracts_glosses(self, sample_glossary_node):
        glosses = _find_glosses(sample_glossary_node)
        assert 'to eat' in glosses
        assert 'to consume' in glosses

    def test_skips_extra_info(self, sample_glossary_node):
        glosses = _find_glosses(sample_glossary_node)
        assert 'should be skipped' not in glosses

    def test_empty_tree(self):
        assert _find_glosses([]) == []

    def test_no_glossary_node(self):
        node = {'tag': 'div', 'data': {'content': 'extra-info'}, 'content': []}
        assert _find_glosses(node) == []


class TestRubyHtml:
    def test_plain_string_passthrough(self):
        assert _ruby_html('もっと') == 'もっと'

    def test_ruby_node(self, sample_ruby_node):
        html = _ruby_html(sample_ruby_node)
        assert '<ruby>果<rt>くだ</rt></ruby>' in html
        assert '<ruby>物<rt>もの</rt></ruby>' in html

    def test_plain_text_preserved_in_output(self, sample_ruby_node):
        html = _ruby_html(sample_ruby_node)
        assert 'もっと' in html
        assert 'を食べる。' in html

    def test_rt_node_standalone(self):
        assert _ruby_html({'tag': 'rt', 'content': 'よ'}) == '<rt>よ</rt>'

    def test_empty_list(self):
        assert _ruby_html([]) == ''

    def test_non_ruby_tag_recurses(self):
        node = {'tag': 'span', 'content': 'テスト'}
        assert _ruby_html(node) == 'テスト'


class TestFindExample:
    def test_extracts_plain_japanese(self, sample_example_node):
        from dictionary import _find_example
        result = _find_example(sample_example_node)
        assert result is not None
        assert result[0] == 'もっと果物を食べるべきです。'

    def test_extracts_english(self, sample_example_node):
        from dictionary import _find_example
        result = _find_example(sample_example_node)
        assert result is not None
        assert result[1] == 'You should eat more fruit.'

    def test_extracts_furigana_html(self, sample_example_node):
        from dictionary import _find_example
        result = _find_example(sample_example_node)
        assert result is not None
        furigana = result[2]
        assert '<ruby>果<rt>くだ</rt></ruby>' in furigana
        assert '<ruby>物<rt>もの</rt></ruby>' in furigana
        assert '<ruby>食<rt>た</rt></ruby>' in furigana

    def test_furigana_plain_text_matches_japanese(self, sample_example_node):
        """Stripping ruby tags from the furigana should give the plain sentence."""
        import re
        from dictionary import _find_example
        result = _find_example(sample_example_node)
        assert result is not None
        stripped = re.sub(r'<ruby>|</ruby>|<rt>[^<]*</rt>', '', result[2])
        assert stripped == result[0]

    def test_returns_none_for_missing_example(self):
        from dictionary import _find_example
        assert _find_example({'tag': 'div', 'content': []}) is None
        assert _find_example([]) is None

    def test_plain_text_has_no_ruby_tags(self, sample_example_node):
        from dictionary import _find_example
        result = _find_example(sample_example_node)
        assert result is not None
        assert '<ruby>' not in result[0]
        assert '<rt>' not in result[0]


# ---------------------------------------------------------------------------
# Integration tests (read local data files)
# ---------------------------------------------------------------------------

class TestJitendexIndex:
    def test_common_verb_present(self, jitendex_index):
        assert '食べる' in jitendex_index

    def test_verb_has_english_gloss(self, jitendex_index):
        assert 'to eat' in jitendex_index['食べる']['英語訳']

    def test_verb_has_pos(self, jitendex_index):
        assert jitendex_index['食べる']['品詞'] != ''

    def test_verb_has_example_sentence(self, jitendex_index):
        assert jitendex_index['食べる']['例文'] == 'もっと果物を食べるべきです。'

    def test_example_has_english(self, jitendex_index):
        assert jitendex_index['食べる']['英語例文'] == 'You should eat more fruit.'

    def test_example_has_furigana(self, jitendex_index):
        furigana = jitendex_index['食べる']['例文振り仮名']
        assert '<ruby>' in furigana
        assert '<rt>' in furigana

    def test_furigana_contains_correct_readings(self, jitendex_index):
        furigana = jitendex_index['食べる']['例文振り仮名']
        assert '<ruby>果<rt>くだ</rt></ruby>' in furigana
        assert '<ruby>物<rt>もの</rt></ruby>' in furigana

    def test_intransitive_verb_pos(self, jitendex_index):
        assert '走る' in jitendex_index
        assert jitendex_index['走る']['品詞'] == '自動詞'

    def test_adjective_pos(self, jitendex_index):
        assert '美しい' in jitendex_index
        assert jitendex_index['美しい']['品詞'] == 'い形容詞'

    def test_na_adjective_pos(self, jitendex_index):
        assert '静か' in jitendex_index
        assert jitendex_index['静か']['品詞'] == 'な形容詞'

    def test_index_size_reasonable(self, jitendex_index):
        assert len(jitendex_index) > 10_000

    def test_no_internal_keys_leaked(self, jitendex_index):
        assert '_pop' not in jitendex_index['食べる']


class TestFrenchIndex:
    def test_index_populated(self, french_index):
        assert len(french_index) > 1_000

    def test_returns_string(self, french_index):
        for v in list(french_index.values())[:10]:
            assert isinstance(v, str)

    def test_common_word_present(self, french_index):
        common = {'食べる', '行く', '見る', '来る', '日本', '学校'}
        assert any(w in french_index for w in common)
