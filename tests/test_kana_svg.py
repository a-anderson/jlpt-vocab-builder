"""Tests for scripts/kana_svg.py — pitch diagrams with kana under each mora."""

import re
import unicodedata

import pytest

from jlpt_vocab.svg import CORNER_R, LABEL_Y, MORA_W, LABELLED_PADDING_X, SVG_HEIGHT_LABELLED
from scripts.kana_svg import parse_notation, read_lines, render_kana_svg, svg_name


def levels(line: str) -> str:
    return ''.join(parse_notation(line)[1])


# ---------------------------------------------------------------------------
# parse_notation
# ---------------------------------------------------------------------------

class TestParseNotation:
    def test_splits_kana_into_mora(self):
        mora, _, _ = parse_notation('きょうと')
        assert mora == ['きょ', 'う', 'と']

    def test_heiban_rises_after_first_mora(self):
        assert levels('たべる') == 'LHH'

    def test_nakadaka(self):
        assert levels('たべま＼した') == 'LHHLL'

    def test_atamadaka_starts_high(self):
        assert levels('た＼べて') == 'HLL'

    def test_single_mora_stays_low(self):
        assert levels('き') == 'L'

    def test_single_mora_atamadaka(self):
        assert levels('き＼') == 'H'

    def test_drop_onto_particle(self):
        mora, lv, particles = parse_notation('はし＼[が]')
        assert mora == ['は', 'し', 'が']
        assert ''.join(lv) == 'LHL'
        assert particles == {3}

    def test_heiban_runs_flat_across_words(self):
        assert levels('あたま[が]あがらない') == 'LHHHHHHHH'

    def test_leading_explicit_rise_replaces_automatic_rise(self):
        assert levels('よ／ろし＼くお／ねがいしま＼す') == 'LHHLLHHHHHL'

    def test_leading_explicit_rise_can_be_late(self):
        assert levels('あた／まが') == 'LLHH'

    def test_later_rise_keeps_automatic_rise(self):
        assert levels('よろし＼く お／ねがいしま＼す') == 'LHHLLHHHHHL'

    def test_rise_at_start_means_starts_high(self):
        assert levels('／たべ＼る') == 'HHL'

    def test_spaces_are_ignored(self):
        assert parse_notation('よろし＼く お／ねがいしま＼す') == \
            parse_notation('よろし＼くお／ねがいしま＼す')

    def test_fullwidth_space_ignored(self):
        assert levels('たべ　ま＼した') == 'LHHLL'

    def test_ascii_markers(self):
        assert parse_notation('よろし\\くお/ねがいしま\\す') == \
            parse_notation('よろし＼くお／ねがいしま＼す')

    def test_katakana_long_vowel_and_small_kana(self):
        mora, lv, _ = parse_notation('コ＼ーヒー')
        assert mora == ['コ', 'ー', 'ヒ', 'ー']
        assert ''.join(lv) == 'HLLL'

    @pytest.mark.parametrize('kana, expected', [
        ('しゃしん', ['しゃ', 'し', 'ん']),
        ('ちゅうしゃ', ['ちゅ', 'う', 'しゃ']),
        ('りょこう', ['りょ', 'こ', 'う']),
        ('パーティー', ['パ', 'ー', 'ティ', 'ー']),
        ('ファイル', ['ファ', 'イ', 'ル']),
        ('シェフ', ['シェ', 'フ']),
    ])
    def test_compound_kana_are_one_mora(self, kana, expected):
        assert parse_notation(kana)[0] == expected

    def test_compound_kana_with_markers(self):
        mora, lv, particles = parse_notation('きょ＼う[しゃ]')
        assert mora == ['きょ', 'う', 'しゃ']
        assert ''.join(lv) == 'HLL'
        assert particles == {3}

    @pytest.mark.parametrize('line', ['き＼ょう', 'き[ょ]', 'し／ゃしん'])
    def test_rejects_marker_inside_compound(self, line):
        with pytest.raises(ValueError):
            parse_notation(line)

    def test_sokuon_and_n_are_mora(self):
        assert parse_notation('きって')[0] == ['き', 'っ', 'て']
        assert parse_notation('ほん')[0] == ['ほ', 'ん']

    def test_multi_mora_particle(self):
        _, _, particles = parse_notation('ここ[から]')
        assert particles == {3, 4}

    def test_nfc_normalised(self):
        decomposed = unicodedata.normalize('NFD', 'たべま＼した')
        assert parse_notation(decomposed)[0] == ['た', 'べ', 'ま', 'し', 'た']

    @pytest.mark.parametrize('line', ['食べる', 'taberu', 'たべる。'])
    def test_rejects_non_kana(self, line):
        with pytest.raises(ValueError):
            parse_notation(line)

    @pytest.mark.parametrize('line', ['は[し', 'はし]', 'は[し[が]]'])
    def test_rejects_unbalanced_brackets(self, line):
        with pytest.raises(ValueError):
            parse_notation(line)

    def test_rejects_drop_while_low(self):
        with pytest.raises(ValueError):
            parse_notation('＼たべる')

    def test_rejects_rise_while_high(self):
        with pytest.raises(ValueError):
            parse_notation('た／べ／る')

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            parse_notation('  ')


# ---------------------------------------------------------------------------
# svg_name
# ---------------------------------------------------------------------------

class TestSvgName:
    def test_nakadaka(self):
        assert svg_name('たべま＼した') == 'たべました_r1_d3.svg'

    def test_particle(self):
        assert svg_name('はし＼[が]') == 'はしが_r1_d2_p3.svg'

    def test_multiple_rises_and_drops(self):
        assert svg_name('よろし＼く お／ねがいしま＼す') == 'よろしくおねがいします_r1-5_d3-10.svg'

    def test_starts_high(self):
        assert svg_name('た＼べて') == 'たべて_r0_d1.svg'

    def test_flat_single_mora_has_no_sections(self):
        assert svg_name('き') == 'き.svg'

    def test_same_diagram_same_name(self):
        assert svg_name('たべる') == svg_name('た／べる')

    def test_name_is_nfc(self):
        name = svg_name(unicodedata.normalize('NFD', 'たべる'))
        assert name == unicodedata.normalize('NFC', name)


# ---------------------------------------------------------------------------
# render_kana_svg
# ---------------------------------------------------------------------------

class TestRenderKanaSvg:
    def test_one_label_per_mora(self):
        svg = render_kana_svg('きょうと')
        assert re.findall(r'<text[^>]*>([^<]*)</text>', svg) == ['きょ', 'う', 'と']

    def test_compound_kana_label_under_one_dot(self):
        svg = render_kana_svg('りょ＼こう')
        assert svg.count('<circle') == 3
        assert re.findall(r'<text[^>]*>([^<]*)</text>', svg) == ['りょ', 'こ', 'う']

    def test_labels_centred_under_dots(self):
        svg = render_kana_svg('たべる')
        xs = [int(x) for x in re.findall(r'<text x="(\d+)"', svg)]
        assert xs == [LABELLED_PADDING_X + i * MORA_W + MORA_W // 2 for i in range(3)]
        assert f'y="{LABEL_Y}"' in svg

    def test_labelled_height(self):
        assert f'height="{SVG_HEIGHT_LABELLED}"' in render_kana_svg('たべる')

    def test_width_matches_mora_count(self):
        assert f'width="{LABELLED_PADDING_X * 2 + 4 * MORA_W}"' in render_kana_svg('はし＼[が]よ')

    def test_particles_hollow(self):
        assert render_kana_svg('ここ[から]').count('fill="none"') == 2

    def test_background(self):
        svg = render_kana_svg('はし＼[が]', background='white')
        assert re.search(
            rf'<rect width="\d+" height="{SVG_HEIGHT_LABELLED}" rx="{CORNER_R}" fill="white"', svg
        )
        assert 'fill="none"' not in svg


# ---------------------------------------------------------------------------
# read_lines
# ---------------------------------------------------------------------------

class TestReadLines:
    def test_skips_comments_and_blank_lines(self, tmp_path):
        path = tmp_path / 'examples.txt'
        path.write_text(
            '# 食べる — conjugations\n'
            'たべ＼る\n'
            '\n'
            '  たべま＼した  \n',
            encoding='utf-8',
        )
        assert read_lines(path) == ['たべ＼る', 'たべま＼した']
