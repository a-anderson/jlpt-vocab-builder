# jlpt-vocab-builder

Builds a JLPT N4–N1 vocabulary CSV (~8,000 words) suitable for import into Anki or any SRS tool. Each row contains the word, furigana, part of speech, pitch accent, English and French glosses, an example sentence with furigana markup, sentence translations, the surface form of the word as used in the sentence, and a reference to a pitch accent diagram SVG.

---

## Output

`jlpt_vocab.csv` — one row per word, 13 columns:

| Column | Example |
|---|---|
| 単語 (word) | 食べる |
| 振り仮名 (furigana) | `<ruby>食<rt>た</rt></ruby>べる` |
| 品詞 (part of speech) | 他動詞 |
| ピッチアクセント (pitch pattern) | `2` |
| ピッチアクセント図 (pitch diagram) | `3_2.svg` |
| 英語訳 (English gloss) | to eat; to consume |
| 仏語訳 (French gloss) | manger; consommer |
| 例文 (example sentence) | 毎朝ご飯を食べる。 |
| 例文振り仮名 (sentence furigana) | `<ruby>毎朝<rt>まいあさ</rt></ruby>ご飯を…` |
| 英語例文 (English sentence) | I eat rice every morning. |
| 仏語例文 (French sentence) | Je mange du riz chaque matin. |
| 日本語ターゲット (surface form) | 食べた |
| レベル (JLPT level) | N4 |

Furigana columns use HTML `<ruby>` tags. Enable **Allow HTML in fields** when importing into Anki.

---

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) running locally with a model pulled, e.g. `ollama pull gemma4:e4b`
- The following data files downloaded to the project root:

| File | Source |
|---|---|
| `jitendex-yomitan/` | [Jitendex for Yomitan](https://github.com/stephenmk/stephenmk.github.io/releases/latest/download/jitendex-yomitan.zip) — extract zip |
| `JMdict_french/` | [JMdict French for Yomitan](https://github.com/yomidevs/jmdict-yomitan/releases/latest/download/JMdict_french.zip) — extract zip |
| `nhk_data/ACCDB_unicode.csv` | [NHK pronunciation CSV](https://raw.githubusercontent.com/javdejong/nhk-pronunciation/master/ACCDB_unicode.csv) |
| `accents.txt` | [Kanjium pitch accents](https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt) |

---

## Setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m unidic download
```

---

## Running

```bash
source venv/bin/activate

# Full run (all levels)
python build_jlpt_csv.py --model gemma4:e4b

# Subset
python build_jlpt_csv.py --model gemma4:e4b --levels n4 n3

# Resume after interruption
python build_jlpt_csv.py --model gemma4:e4b --resume

# Generate pitch accent SVGs (run once after CSV is complete)
python generate_pitch_svgs.py
```

The pipeline writes rows incrementally and checkpoints after every word, so `--resume` picks up exactly where it left off.

### Parallel runs

Processing all four levels takes several hours. Run one level per terminal for a ~4× speedup:

```bash
python build_jlpt_csv.py --model gemma4:e4b --levels n4 --output n4.csv
python build_jlpt_csv.py --model gemma4:e4b --levels n3 --output n3.csv
python build_jlpt_csv.py --model gemma4:e4b --levels n2 --output n2.csv
python build_jlpt_csv.py --model gemma4:e4b --levels n1 --output n1.csv
```

Concatenate when all are done:

```bash
head -1 n4.csv > jlpt_vocab.csv
for f in n4.csv n3.csv n2.csv n1.csv; do tail -n +2 "$f"; done >> jlpt_vocab.csv
```

### Dropping words

To remove words from a CSV and its paired checkpoint (e.g. before reprocessing failed rows):

```bash
python drop_words.py 下りる 招致 --output n4.csv
```

Then re-run with `--resume` to regenerate just those rows.

---

## Anki integration

1. Import `jlpt_vocab.csv` via **File → Import**. Enable **Allow HTML in fields**.
2. Copy all SVGs from `pitch_svgs/` into your Anki media folder:
   - macOS: `~/Library/Application Support/Anki2/<profile>/collection.media/`
   - Linux: `~/.local/share/Anki2/<profile>/collection.media/`
   - Windows: `%APPDATA%\Anki2\<profile>\collection.media\`
3. Reference the columns in your card template:

```html
{{振り仮名}}
<img src="{{ピッチアクセント図}}">
{{英語訳}} / {{仏語訳}}
{{例文振り仮名}}
{{英語例文}} / {{仏語例文}}
```

---

## Tests

```bash
python -m pytest tests/ -v
```

---

## Data sources & licensing

| Source | Used for | Licence |
|---|---|---|
| [chadmuro/jlpt-vocab](https://github.com/chadmuro/jlpt-vocab) | Word lists | MIT |
| [Jitendex](https://github.com/stephenmk/stephenmk.github.io) | EN glosses, POS, example sentences | CC BY-SA 4.0 |
| [JMdict French](https://github.com/yomidevs/jmdict-yomitan) | French glosses | CC BY-SA 4.0 |
| Kanjium / NHK pitch data | Pitch accent | Derived from commercial dictionaries — personal study only |
