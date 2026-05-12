"""Tests for furigana conversion and normalisation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from furigana import bracket_to_ruby, normalise_furigana


class TestBracketToRuby:
    def test_simple_kanji(self):
        assert bracket_to_ruby('食[た]べる') == '<ruby>食<rt>た</rt></ruby>べる'

    def test_multiple_kanji(self):
        assert bracket_to_ruby('主[しゅ] 人[じん]') == '<ruby>主<rt>しゅ</rt></ruby><ruby>人<rt>じん</rt></ruby>'

    def test_prefix_parens(self):
        assert bracket_to_ruby('（ご） 主[しゅ] 人[じん]') == '（ご）<ruby>主<rt>しゅ</rt></ruby><ruby>人<rt>じん</rt></ruby>'

    def test_pure_kana_unchanged(self):
        assert bracket_to_ruby('のど') == 'のど'

    def test_multi_char_reading(self):
        assert bracket_to_ruby('夫[おっと]') == '<ruby>夫<rt>おっと</rt></ruby>'

    def test_mixed_kanji_kana_base(self):
        # Base group contains trailing kana (e.g. verb stem)
        assert bracket_to_ruby('食[た]べ') == '<ruby>食<rt>た</rt></ruby>べ'


class TestNormaliseFurigana:
    def test_strips_redundant_hiragana_ruby(self):
        assert normalise_furigana('<ruby>もらう<rt>もらう</rt></ruby>') == 'もらう'

    def test_strips_redundant_katakana_ruby(self):
        assert normalise_furigana('<ruby>テレビ<rt>テレビ</rt></ruby>') == 'テレビ'

    def test_strips_katakana_halfwidth_paren_reading(self):
        assert normalise_furigana('テレビ(てれび)') == 'テレビ'

    def test_strips_katakana_fullwidth_paren_reading(self):
        assert normalise_furigana('テレビ（てれび）') == 'テレビ'

    def test_converts_halfwidth_paren_to_ruby(self):
        assert normalise_furigana('漢字(かな)') == '<ruby>漢字<rt>かな</rt></ruby>'

    def test_converts_fullwidth_paren_to_ruby(self):
        assert normalise_furigana('漢字（かな）') == '<ruby>漢字<rt>かな</rt></ruby>'

    def test_converts_bracket_to_ruby(self):
        assert normalise_furigana('漢字[かな]') == '<ruby>漢字<rt>かな</rt></ruby>'

    def test_does_not_add_ruby_to_hiragana_base(self):
        # A hiragana base followed by paren should not become ruby
        result = normalise_furigana('たべる(たべる)')
        assert '<ruby>' not in result

    def test_preserves_existing_valid_ruby(self):
        html = '<ruby>食<rt>た</rt></ruby>べる'
        assert normalise_furigana(html) == html
