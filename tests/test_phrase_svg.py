"""Tests for scripts/phrase_svg.py — hand-specified pitch contours for phrases."""

import pytest

from jlpt_vocab.svg import MORA_W, PADDING_X, Y_HIGH, Y_LOW
from scripts.generate_svgs import pitch_sequence
from scripts.phrase_svg import (
    pitch_levels, read_specs, render_phrase_svg, svg_name,
)


# ---------------------------------------------------------------------------
# pitch_levels
# ---------------------------------------------------------------------------

class TestPitchLevels:
    @pytest.mark.parametrize('mora_count', [1, 2, 3, 4, 5])
    def test_drop_position_equals_accent_pattern(self, mora_count):
        for pattern in range(mora_count + 1):
            if pattern == 0:
                rises, drops = {1}, set()
            elif pattern == 1:
                rises, drops = {0}, {1}
            else:
                rises, drops = {1}, {pattern}
            assert pitch_levels(mora_count, rises, drops) == pitch_sequence(mora_count, pattern)

    def test_starts_low_with_no_rise(self):
        assert pitch_levels(3, set(), set()) == ['L', 'L', 'L']

    def test_rise_zero_starts_high(self):
        assert pitch_levels(4, {0}, {1}) == list('HLLL')

    def test_multiple_rises_and_drops(self):
        assert pitch_levels(8, {1, 5}, {3}) == list('LHHLLHHH')

    def test_drop_after_final_mora_leaves_phrase_high(self):
        assert pitch_levels(3, {1}, {3}) == ['L', 'H', 'H']

    @pytest.mark.parametrize('rises, drops', [
        ({4}, set()),
        (set(), {4}),
        ({-1}, set()),
    ])
    def test_rejects_out_of_range_positions(self, rises, drops):
        with pytest.raises(ValueError):
            pitch_levels(3, rises, drops)

    def test_rejects_rise_and_drop_at_same_boundary(self):
        with pytest.raises(ValueError):
            pitch_levels(4, {2}, {2})

    def test_rejects_drop_while_already_low(self):
        with pytest.raises(ValueError):
            pitch_levels(4, {1}, {2, 3})

    def test_rejects_rise_while_already_high(self):
        with pytest.raises(ValueError):
            pitch_levels(4, {1, 2}, set())


# ---------------------------------------------------------------------------
# render_phrase_svg
# ---------------------------------------------------------------------------

class TestRenderPhraseSvg:
    def test_returns_svg_element(self):
        svg = render_phrase_svg(5, {1}, {4}, {3})
        assert svg.startswith('<svg')
        assert svg.endswith('</svg>')

    def test_one_circle_per_mora(self):
        assert render_phrase_svg(5, {1}, {4}, set()).count('<circle') == 5

    def test_lines_connect_consecutive_dots(self):
        assert render_phrase_svg(5, {1}, {4}, set()).count('<line') == 4

    def test_hollow_circle_per_particle(self):
        svg = render_phrase_svg(8, {1, 5}, {3}, {3, 8})
        assert svg.count('fill="white"') == 2

    def test_no_hollow_circles_without_particles(self):
        assert 'fill="white"' not in render_phrase_svg(4, {1}, {3}, set())

    def test_width_has_no_particle_gap(self):
        svg = render_phrase_svg(5, {1}, {4}, {3})
        assert f'width="{PADDING_X * 2 + 5 * MORA_W}"' in svg

    def test_high_and_low_dots_use_expected_heights(self):
        svg = render_phrase_svg(2, {1}, set(), set())
        first, second = svg.split('<circle')[1:3]
        assert f'cy="{Y_LOW}"' in first
        assert f'cy="{Y_HIGH}"' in second

    def test_particle_positions_are_one_indexed(self):
        svg = render_phrase_svg(3, {1}, set(), {1})
        first = svg.split('<circle')[1]
        assert 'fill="white"' in first

    def test_rejects_particle_out_of_range(self):
        with pytest.raises(ValueError):
            render_phrase_svg(3, {1}, set(), {4})


# ---------------------------------------------------------------------------
# svg_name
# ---------------------------------------------------------------------------

class TestSvgName:
    def test_all_sections(self):
        assert svg_name(5, {1}, {4}, {3}) == 'phrase_5_r1_d4_p3.svg'

    def test_multiple_positions_joined_with_dashes(self):
        assert svg_name(8, {1, 5}, {3}, {3, 8}) == 'phrase_8_r1-5_d3_p3-8.svg'

    def test_empty_sections_omitted(self):
        assert svg_name(3, {1}, set(), set()) == 'phrase_3_r1.svg'
        assert svg_name(3, set(), set(), {1}) == 'phrase_3_p1.svg'
        assert svg_name(3, set(), set(), set()) == 'phrase_3.svg'

    def test_positions_sorted(self):
        assert svg_name(9, {5, 1}, set(), set()) == 'phrase_9_r1-5.svg'


# ---------------------------------------------------------------------------
# read_specs
# ---------------------------------------------------------------------------

class TestReadSpecs:
    def test_parses_multiple_specs(self, tmp_path):
        path = tmp_path / 'phrases.txt'
        path.write_text(
            '--mora 5 --rise 1 --drop 4 --particles 3\n'
            '--mora 8 --rise 1 5 --drop 3 --particles 3 8\n',
            encoding='utf-8',
        )
        specs = read_specs(path)
        assert [s.mora for s in specs] == [5, 8]
        assert specs[1].rise == [1, 5]
        assert specs[1].particles == [3, 8]

    def test_skips_comments_and_blank_lines(self, tmp_path):
        path = tmp_path / 'phrases.txt'
        path.write_text(
            '# 腹が立つ\n'
            '\n'
            '--mora 5 --rise 1 --drop 4 --particles 3\n'
            '   \n',
            encoding='utf-8',
        )
        assert len(read_specs(path)) == 1

    def test_omitted_flags_default_to_empty(self, tmp_path):
        path = tmp_path / 'phrases.txt'
        path.write_text('--mora 3 --rise 1\n', encoding='utf-8')
        spec = read_specs(path)[0]
        assert spec.drop == []
        assert spec.particles == []
