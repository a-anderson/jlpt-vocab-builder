"""Auto-download data sources on first run. Each function is a no-op if the target exists."""

import zipfile
from pathlib import Path

import requests

_JITENDEX_URL = 'https://github.com/stephenmk/stephenmk.github.io/releases/latest/download/jitendex-yomitan.zip'
_JMDICT_URL = 'https://github.com/yomidevs/jmdict-yomitan/releases/latest/download/JMdict_{lang}.zip'
_NHK_URL = 'https://raw.githubusercontent.com/javdejong/nhk-pronunciation/master/ACCDB_unicode.csv'
_KANJIUM_URL = 'https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt'

DATA_DIR = Path('data')


def _download_zip(url: str, dest_dir: Path) -> None:
    """Download zip from url, extract all files into dest_dir, delete the zip."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {url} ...')
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    zip_path = dest_dir / Path(url).name
    with open(zip_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()


def _download_file(url: str, dest: Path) -> None:
    """Download a single file from url to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {url} ...')
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def ensure_jitendex() -> None:
    if not (DATA_DIR / 'jitendex-yomitan').exists():
        _download_zip(_JITENDEX_URL, DATA_DIR / 'jitendex-yomitan')


def ensure_jmdict(lang: str) -> None:
    """lang is a lowercase language name e.g. 'french', 'spanish'."""
    if not (DATA_DIR / f'JMdict_{lang}').exists():
        _download_zip(_JMDICT_URL.format(lang=lang), DATA_DIR / f'JMdict_{lang}')


def ensure_nhk() -> None:
    dest = DATA_DIR / 'nhk_data' / 'ACCDB_unicode.csv'
    if not dest.exists():
        _download_file(_NHK_URL, dest)


def ensure_kanjium() -> None:
    if not (DATA_DIR / 'accents.txt').exists():
        _download_file(_KANJIUM_URL, DATA_DIR / 'accents.txt')


def ensure_all(langs: list[str]) -> None:
    """Download all required data for the given language list."""
    ensure_jitendex()
    for lang in langs:
        ensure_jmdict(lang)
    ensure_nhk()
    ensure_kanjium()
