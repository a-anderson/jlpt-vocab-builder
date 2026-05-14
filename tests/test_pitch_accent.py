"""Tests for pitch accent utilities."""

from pathlib import Path

import pytest

from jlpt_vocab.pitch_accent import split_mora, svg_filename, plain_kana, get_pitch_accent, get_pitch_columns, _decode_nhk_ac
from scripts.generate_svgs import pitch_sequence, particle_level

_REPO_ROOT = Path(__file__).parent.parent
_PITCH_DATA_AVAILABLE = (
    (_REPO_ROOT / 'data' / 'accents.txt').exists()
    and (_REPO_ROOT / 'data' / 'nhk_data' / 'ACCDB_unicode.csv').exists()
)


class TestSplitMora:
    def test_simple(self):
        assert split_mora('たべる') == ['た', 'べ', 'る']

    def test_compound_kana(self):
        assert split_mora('きょうと') == ['きょ', 'う', 'と']

    def test_compound_katakana(self):
        assert split_mora('キョウト') == ['キョ', 'ウ', 'ト']

    def test_empty(self):
        assert split_mora('') == []

    def test_single_mora(self):
        assert split_mora('か') == ['か']

    def test_compound_at_end(self):
        assert split_mora('しゃしん') == ['しゃ', 'し', 'ん']


class TestSvgFilename:
    def test_known_pattern(self):
        assert svg_filename(3, 2) == '3_2.svg'

    def test_heiban(self):
        assert svg_filename(4, 0) == '4_0.svg'

    def test_unknown(self):
        assert svg_filename(3, None) == 'unknown.svg'

    def test_odaka(self):
        assert svg_filename(2, 2) == '2_2.svg'


class TestPlainKana:
    def test_bracketed_kanji(self):
        assert plain_kana('食[た]べる') == 'たべる'

    def test_multiple_kanji(self):
        assert plain_kana('主[しゅ] 人[じん]') == 'しゅじん'

    def test_pure_kana(self):
        assert plain_kana('のど') == 'のど'


class TestPitchSequence:
    def test_heiban_one_mora(self):
        # Pattern 0 on 1 mora: just L (no H mora to follow)
        assert pitch_sequence(1, 0) == ['L']

    def test_heiban_four_mora(self):
        # L H H H — pitch stays up, particle also high
        assert pitch_sequence(4, 0) == ['L', 'H', 'H', 'H']

    def test_atamadaka_one_mora(self):
        assert pitch_sequence(1, 1) == ['H']

    def test_atamadaka_three_mora(self):
        # H L L — drops immediately after first mora
        assert pitch_sequence(3, 1) == ['H', 'L', 'L']

    def test_nakadaka_drops_after_second(self):
        # Pattern 2 on 4 mora: L H L L
        assert pitch_sequence(4, 2) == ['L', 'H', 'L', 'L']

    def test_nakadaka_drops_after_third(self):
        # Pattern 3 on 4 mora: L H H L
        assert pitch_sequence(4, 3) == ['L', 'H', 'H', 'L']

    def test_odaka_equals_mora_count(self):
        # Pattern == mora_count (odaka): L H H H — all word mora high, drop on particle
        assert pitch_sequence(4, 4) == ['L', 'H', 'H', 'H']

    def test_odaka_two_mora(self):
        # Pattern 2 on 2 mora (odaka): L H
        assert pitch_sequence(2, 2) == ['L', 'H']

    def test_empty_mora_count(self):
        assert pitch_sequence(0, 0) == []

    def test_sequence_length_matches_mora_count(self):
        for n in range(1, 6):
            for p in range(n + 1):
                assert len(pitch_sequence(n, p)) == n


class TestParticleLevel:
    def test_heiban_particle_is_high(self):
        assert particle_level(4, 0) == 'H'

    def test_atamadaka_particle_is_low(self):
        assert particle_level(3, 1) == 'L'

    def test_nakadaka_particle_is_low(self):
        assert particle_level(4, 2) == 'L'

    def test_odaka_particle_is_low(self):
        # Drop occurs ON the particle — particle is LOW despite last word mora being H
        assert particle_level(3, 3) == 'L'

    def test_all_non_zero_patterns_are_low(self):
        for pattern in range(1, 5):
            assert particle_level(4, pattern) == 'L'


class TestDecodeNhkAc:
    def test_heiban_two_mora(self):
        # '1' padded to '01' — no '2' → pattern 0
        assert _decode_nhk_ac('1', 2) == 0

    def test_heiban_three_mora(self):
        assert _decode_nhk_ac('11', 3) == 0

    def test_heiban_four_mora(self):
        assert _decode_nhk_ac('111', 4) == 0

    def test_atamadaka_three_mora(self):
        # '200' → '2' at index 0 → pattern 1
        assert _decode_nhk_ac('200', 3) == 1

    def test_nakadaka_three_mora(self):
        # '20' padded to '020' → '2' at index 1 → pattern 2
        assert _decode_nhk_ac('20', 3) == 2

    def test_nakadaka_four_mora_drop_after_third(self):
        # '120' padded to '0120' → '2' at index 2 → pattern 3
        assert _decode_nhk_ac('120', 4) == 3

    def test_all_zeros_is_heiban(self):
        assert _decode_nhk_ac('000', 3) == 0


@pytest.mark.skipif(not _PITCH_DATA_AVAILABLE, reason='pitch accent data not downloaded — run the pipeline first')
class TestGetPitchAccent:
    """Integration tests against real local Kanjium and NHK data files."""

    def test_kanjium_path_food(self):
        result = get_pitch_accent('食べる', 'たべる')
        assert result['pattern'] == 2
        assert result['source'] == 'kanjium'
        assert result['mora_count'] == 3

    def test_kanjium_path_heiban(self):
        result = get_pitch_accent('行く', 'いく')
        assert result['pattern'] == 0
        assert result['source'] == 'kanjium'

    def test_kanjium_path_atamadaka(self):
        result = get_pitch_accent('静か', 'しずか')
        assert result['pattern'] == 1
        assert result['source'] == 'kanjium'

    def test_nhk_fallback(self):
        # 愛知 (Aichi prefecture) was chosen because it is a proper noun absent from
        # Kanjium (which covers common vocabulary) but present in NHK's broadcaster
        # pronunciation data. If this assertion ever fails with source='kanjium',
        # Kanjium has been updated and a new NHK-only word should be selected.
        get_pitch_accent.cache_clear()
        result = get_pitch_accent('愛知', 'あいち')
        assert result['source'] == 'nhk'
        assert result['pattern'] == 1
        assert result['mora_count'] == 3

    def test_unknown_word_returns_none_pattern(self):
        get_pitch_accent.cache_clear()
        result = get_pitch_accent('zzz_not_a_word', 'zzz')
        assert result['pattern'] is None
        assert result['source'] == 'unknown'

    def test_mora_count_matches_reading(self):
        result = get_pitch_accent('食べる', 'たべる')
        assert result['mora_count'] == len(split_mora('たべる'))


@pytest.mark.skipif(not _PITCH_DATA_AVAILABLE, reason='pitch accent data not downloaded — run the pipeline first')
class TestGetPitchColumns:
    def test_returns_both_keys(self):
        cols = get_pitch_columns('食べる', 'たべる')
        assert 'ピッチアクセント' in cols
        assert 'ピッチアクセント図' in cols

    def test_pattern_as_string(self):
        cols = get_pitch_columns('食べる', 'たべる')
        assert cols['ピッチアクセント'] == '2'

    def test_svg_filename_format(self):
        cols = get_pitch_columns('食べる', 'たべる')
        assert cols['ピッチアクセント図'] == '3_2.svg'

    def test_unknown_word_produces_unknown_svg(self):
        get_pitch_accent.cache_clear()
        cols = get_pitch_columns('zzz_not_a_word', 'zzz')
        assert cols['ピッチアクセント'] == ''
        assert cols['ピッチアクセント図'] == 'unknown.svg'
