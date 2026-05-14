"""Tests for headword normalisation."""

from jlpt_vocab.normalise import normalise_word


class TestNormaliseWord:
    def test_plain_word(self):
        result = normalise_word('食べる')
        assert result['lookup_forms'] == ['食べる']
        assert result['inferred_pos'] == ''

    def test_prefix_paren(self):
        result = normalise_word('（ご）主人')
        assert result['lookup_forms'] == ['ご主人', '主人']
        assert result['inferred_pos'] == ''

    def test_suffix_na(self):
        result = normalise_word('残念（な）')
        assert result['lookup_forms'] == ['残念']
        assert result['inferred_pos'] == 'な形容詞'

    def test_suffix_suru(self):
        result = normalise_word('勉強（する）')
        assert result['lookup_forms'] == ['勉強']
        assert result['inferred_pos'] == 'サ変動詞（する）'

    def test_suffix_no(self):
        result = normalise_word('主要（の）')
        assert result['lookup_forms'] == ['主要']
        assert result['inferred_pos'] == 'の形容詞'

    def test_unknown_suffix(self):
        result = normalise_word('何か（も）')
        assert result['lookup_forms'] == ['何か']
        assert result['inferred_pos'] == ''

    def test_lookup_forms_is_list(self):
        result = normalise_word('行く')
        assert isinstance(result['lookup_forms'], list)
        assert len(result['lookup_forms']) >= 1
