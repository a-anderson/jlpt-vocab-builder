"""Tests for scripts/generate_svgs.py — SVG rendering and CSV parsing."""

import csv
import re

import pytest

from jlpt_vocab.svg import CORNER_R, DOT_R
from scripts.generate_svgs import (
    Y_HIGH, Y_LOW, MORA_W, PADDING_X, PARTICLE_GAP,
    collect_pairs, render_svg, render_unknown_svg,
)


# ---------------------------------------------------------------------------
# render_svg
# ---------------------------------------------------------------------------

class TestRenderSvg:
    def test_returns_svg_element(self):
        assert render_svg(2, 0).startswith('<svg')

    def test_closes_svg_element(self):
        assert render_svg(2, 0).endswith('</svg>')

    def test_dot_count_equals_mora_plus_particle(self):
        # mora_count word dots + 1 particle dot
        for mora_count in (1, 2, 3, 4):
            svg = render_svg(mora_count, 0)
            assert svg.count('<circle') == mora_count + 1, f'mora_count={mora_count}'

    def test_particle_dot_is_hollow(self):
        # Hollow particle dot uses fill="none" (transparent); word dots use a colour fill
        assert render_svg(3, 0).count('fill="none"') == 1

    def test_line_stops_at_hollow_dot_edge(self):
        # The particle is transparent, so the line must not show through its middle
        svg = render_svg(2, 2)
        x2, y2 = map(float, re.findall(r'x2="([\d.]+)" y2="([\d.]+)"', svg)[-1])
        cx, cy = map(float, re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)"', svg)[-1])
        assert ((cx - x2) ** 2 + (cy - y2) ** 2) ** 0.5 >= DOT_R

    def test_transparent_by_default(self):
        assert '<rect' not in render_svg(3, 0)

    def test_background_draws_rounded_rect(self):
        rect = re.search(r'<rect[^>]*/>', render_svg(3, 0, background='white')).group(0)
        assert 'fill="white"' in rect
        assert f'rx="{CORNER_R}"' in rect

    def test_background_fills_particle(self):
        svg = render_svg(3, 0, background='white')
        assert 'fill="none"' not in svg
        assert re.search(r'<circle[^>]*fill="white"', svg)

    def test_background_drawn_first(self):
        svg = render_svg(3, 0, background='white')
        assert svg.index('<rect') < svg.index('<line')

    def test_heiban_first_mora_is_low(self):
        # Heiban (pattern 0): L H H... — first dot at Y_LOW
        svg = render_svg(3, 0)
        first_circle_start = svg.index('<circle')
        first_circle = svg[first_circle_start: svg.index('/>', first_circle_start)]
        assert f'cy="{Y_LOW}"' in first_circle

    def test_atamadaka_first_mora_is_high(self):
        # Atamadaka (pattern 1): H L L... — first dot at Y_HIGH
        svg = render_svg(3, 1)
        first_circle_start = svg.index('<circle')
        first_circle = svg[first_circle_start: svg.index('/>', first_circle_start)]
        assert f'cy="{Y_HIGH}"' in first_circle

    def test_width_scales_with_mora_count(self):
        def svg_width(mora_count):
            svg = render_svg(mora_count, 0)
            start = svg.index('width="') + len('width="')
            end = svg.index('"', start)
            return int(svg[start:end])

        assert svg_width(4) > svg_width(2)

    def test_width_formula(self):
        # width = PADDING_X * 2 + mora_count * MORA_W + PARTICLE_GAP + MORA_W
        mora_count, pattern = 3, 0
        expected = PADDING_X * 2 + mora_count * MORA_W + PARTICLE_GAP + MORA_W
        svg = render_svg(mora_count, pattern)
        start = svg.index('width="') + len('width="')
        end = svg.index('"', start)
        assert int(svg[start:end]) == expected

    def test_lines_connect_consecutive_dots(self):
        # N+1 dots (word mora + particle) → N connecting lines
        for mora_count in (1, 2, 3, 4):
            svg = render_svg(mora_count, 0)
            assert svg.count('<line') == mora_count, f'mora_count={mora_count}'


# ---------------------------------------------------------------------------
# render_unknown_svg
# ---------------------------------------------------------------------------

class TestRenderUnknownSvg:
    def test_is_valid_svg(self):
        assert render_unknown_svg().startswith('<svg')

    def test_transparent_by_default(self):
        assert '<rect' not in render_unknown_svg()

    def test_background_draws_rounded_rect(self):
        svg = render_unknown_svg(background='white')
        assert re.search(rf'<rect[^>]*rx="{CORNER_R}"[^>]*fill="white"', svg)
        assert svg.index('<rect') < svg.index('<text')

    def test_contains_question_mark(self):
        assert '?' in render_unknown_svg()


# ---------------------------------------------------------------------------
# collect_pairs
# ---------------------------------------------------------------------------

def _write_csv(tmp_path, rows):
    # collect_pairs only reads ピッチアクセント図; other CSV columns are not needed
    path = tmp_path / 'vocab.csv'
    fieldnames = ['単語', 'ピッチアクセント図']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


class TestCollectPairs:
    def test_extracts_pair_from_filename(self, tmp_path):
        path = _write_csv(tmp_path, [{'単語': '食べる', 'ピッチアクセント図': '4_2.svg'}])
        pairs, has_unknown = collect_pairs(path)
        assert pairs == {(4, 2)}
        assert not has_unknown

    def test_unknown_svg_sets_flag(self, tmp_path):
        path = _write_csv(tmp_path, [{'単語': '食べる', 'ピッチアクセント図': 'unknown.svg'}])
        pairs, has_unknown = collect_pairs(path)
        assert pairs == set()
        assert has_unknown

    def test_empty_filename_sets_flag(self, tmp_path):
        path = _write_csv(tmp_path, [{'単語': '食べる', 'ピッチアクセント図': ''}])
        pairs, has_unknown = collect_pairs(path)
        assert pairs == set()
        assert has_unknown

    def test_deduplicates_pairs(self, tmp_path):
        rows = [
            {'単語': '食べる', 'ピッチアクセント図': '3_2.svg'},
            {'単語': '走る',   'ピッチアクセント図': '3_2.svg'},
        ]
        path = _write_csv(tmp_path, rows)
        pairs, _ = collect_pairs(path)
        assert pairs == {(3, 2)}

    def test_no_underscore_filename_sets_flag(self, tmp_path):
        # Filename with no underscore can't be split into (mora_count, pattern)
        path = _write_csv(tmp_path, [{'単語': '食べる', 'ピッチアクセント図': 'bad.svg'}])
        pairs, has_unknown = collect_pairs(path)
        assert pairs == set()
        assert has_unknown

    def test_non_integer_parts_set_flag(self, tmp_path):
        # Two underscore-separated parts but non-integer values → ValueError branch
        path = _write_csv(tmp_path, [{'単語': '食べる', 'ピッチアクセント図': 'bad_value.svg'}])
        pairs, has_unknown = collect_pairs(path)
        assert pairs == set()
        assert has_unknown

    def test_collects_multiple_distinct_pairs(self, tmp_path):
        rows = [
            {'単語': '食べる', 'ピッチアクセント図': '3_2.svg'},
            {'単語': '走る',   'ピッチアクセント図': '2_1.svg'},
        ]
        path = _write_csv(tmp_path, rows)
        pairs, has_unknown = collect_pairs(path)
        assert pairs == {(3, 2), (2, 1)}
        assert not has_unknown
