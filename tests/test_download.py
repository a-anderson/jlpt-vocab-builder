"""Tests for download.py — all network calls are mocked."""

import io
import zipfile as _zf
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


def _make_zip(filename='test.txt', content=b'data') -> bytes:
    buf = io.BytesIO()
    with _zf.ZipFile(buf, 'w') as z:
        z.writestr(filename, content)
    return buf.getvalue()


def _mock_get_zip(url, **kwargs):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.iter_content.return_value = [_make_zip()]
    return mock


def _mock_get_bytes(content: bytes):
    def _inner(url, **kwargs):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.content = content
        return mock
    return _inner


class TestEnsureJmdict:
    def test_skips_if_dir_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'data' / 'JMdict_french').mkdir(parents=True)
        with patch('requests.get') as mock_get:
            from jlpt_vocab.download import ensure_jmdict
            ensure_jmdict('french')
        mock_get.assert_not_called()

    def test_downloads_extracts_and_deletes_zip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch('requests.get', side_effect=_mock_get_zip):
            from jlpt_vocab.download import ensure_jmdict
            ensure_jmdict('spanish')
        assert (tmp_path / 'data' / 'JMdict_spanish').exists()
        assert not list((tmp_path / 'data' / 'JMdict_spanish').glob('*.zip'))


class TestEnsureKanjium:
    def test_skips_if_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'data').mkdir(parents=True)
        (tmp_path / 'data' / 'accents.txt').write_text('x', encoding='utf-8')
        with patch('requests.get') as mock_get:
            from jlpt_vocab.download import ensure_kanjium
            ensure_kanjium()
        mock_get.assert_not_called()

    def test_downloads_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        content = b'exp\treading\t0\n'
        with patch('requests.get', side_effect=_mock_get_bytes(content)):
            from jlpt_vocab.download import ensure_kanjium
            ensure_kanjium()
        dest = tmp_path / 'data' / 'accents.txt'
        assert dest.exists()
        assert dest.read_bytes() == content


class TestEnsureAll:
    def test_calls_each_component(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with (
            patch('jlpt_vocab.download.ensure_jitendex') as mock_ji,
            patch('jlpt_vocab.download.ensure_jmdict') as mock_jm,
            patch('jlpt_vocab.download.ensure_nhk') as mock_nhk,
            patch('jlpt_vocab.download.ensure_kanjium') as mock_ka,
        ):
            from jlpt_vocab.download import ensure_all
            ensure_all(['french', 'spanish'])
        mock_ji.assert_called_once()
        assert mock_jm.call_count == 2
        mock_jm.assert_any_call('french')
        mock_jm.assert_any_call('spanish')
        mock_nhk.assert_called_once()
        mock_ka.assert_called_once()
