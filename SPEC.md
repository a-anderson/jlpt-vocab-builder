# JLPT Vocabulary CSV Builder — Project Specification

## Purpose

Build a comprehensive Japanese vocabulary study dataset covering JLPT levels N4–N1 (~8,000 words), output as a single CSV file suitable for import into Anki or any SRS tool. Each row represents one word and contains everything needed to study it: the word itself, readings, part of speech, English and French definitions, an example sentence with furigana, translations of that sentence, the conjugated/surface form of the word as used in the sentence, pitch accent pattern, and a reference to a pitch accent diagram SVG.

A separate script generates the pitch accent SVG files from the completed CSV.

---

## Output CSV columns

| Column | Japanese name | Example | Description |
|---|---|---|---|
| Word | 単語 | 食べる | Headword as it appears in the source (kanji where applicable) |
| Furigana | 振り仮名 | `<ruby>食<rt>た</rt></ruby>べる` | Ruby HTML furigana |
| Part of speech | 品詞 | 他動詞 | Japanese grammatical category |
| Pitch accent | ピッチアクセント | `2` | Numeric drop pattern (0 = 平板/heiban) |
| Pitch diagram | ピッチアクセント図 | `3_2.svg` | SVG filename: `{mora_count}_{pattern}.svg` |
| English | 英語訳 | to eat; to consume | Semicolon-separated English glosses |
| French | 仏語訳 | manger; consommer | Semicolon-separated French glosses |
| Example sentence | 例文 | 毎朝ご飯を食べる。 | Japanese example sentence |
| Sentence furigana | 例文振り仮名 | `<ruby>毎朝<rt>まいあさ</rt></ruby>...` | Example sentence with ruby HTML furigana |
| English sentence | 英語例文 | I eat rice every morning. | Natural English translation |
| French sentence | 仏語例文 | Je mange du riz chaque matin. | Natural French translation |
| Target form | 日本語ターゲット | 食べた | Surface form of the word as it appears in the sentence |
| Level | レベル | N4 | JLPT level |

---

## Data sources

### Word list
**Source:** [chadmuro/jlpt-vocab](https://github.com/chadmuro/jlpt-vocab)

Fetch raw `.ts` files directly:
```
https://raw.githubusercontent.com/chadmuro/jlpt-vocab/main/data/{level}/vocabulary.ts
```
Levels: `n4`, `n3`, `n2`, `n1` (N5 is not in this repo — omit it).

Each file exports a TypeScript array. Parse with regex — it is not valid JSON. The relevant fields are:
- `kanji` — the display headword (use as 単語)
- `japanese` — furigana in bracket notation e.g. `食[た]べる` or `（ご） 主[しゅ] 人[じん]` (use for 振り仮名 and kana reading)
- `english` — English gloss fallback (use if Jitendex has no match)

### English glosses + POS
**Source:** [Jitendex for Yomitan](https://github.com/stephenmk/stephenmk.github.io/releases/latest/download/jitendex-yomitan.zip)

Download the zip, extract to a local directory. Contains multiple `term_bank_N.json` files. Each entry is a positional array:
```
[term, reading, def_tags, rules, popularity, definitions, sequence, term_tags]
  [0]    [1]      [2]       [3]      [4]          [5]         [6]       [7]
```

Key points:
- `def_tags` (index 2) contains POS as space-separated JMDict codes, optionally prefixed with a sense number e.g. `"1 v5u vt uk"` → strip the leading digit and space before parsing
- `popularity` (index 4) is a frequency score — higher = more common. When multiple entries exist for the same headword, keep the one with the **highest popularity**. This ensures common meanings win over rare/archaic ones (e.g. 字 → "character" not "Chinese courtesy name")
- `definitions` (index 5) is a list of structured content objects. Extract glosses only from `ul` nodes where `data.content == "glossary"`. **Skip** nodes where `data.content` is any of: `examples`, `references`, `notes`, `forms`, `formsTable`, `attribution`, `xref`, `xref-content`, `xref-glossary`, `info-gloss`, `refGlosses`
- Example sentences are in `ul` nodes where `data.content == "examples"` and `lang == "ja"`. The first `li` child (no `lang` attribute) is the Japanese sentence; the second `li` child (`lang == "en"`) is the English translation
- `"forms"` entries (where `def_tags == "forms"`) contain no glosses — skip them entirely

POS tag → 品詞 mapping (key ones — extend as needed):
```
vt → 他動詞    vi → 自動詞    v1 → 一段動詞
v5u → 五段動詞（う）   v5k → 五段動詞（く）   ... (and so on for each v5 ending)
vk → カ変動詞   vs-i → サ変動詞（する）
adj-i → い形容詞   adj-na → な形容詞   adj-no → の形容詞
n → 名詞   adv → 副詞   prt → 助詞   conj → 接続詞
pn → 代名詞   int → 感動詞   exp → 表現   suf → 接尾語   pref → 接頭語
```
**Important:** check `vt` before `vi` before other verb tags, because `"intransitive verb"` is a substring of `"transitive verb"` (and similar issues exist in tag resolution). Also strip any leading sense number from `def_tags` before splitting into individual tags.

### French glosses
**Source:** [JMdict French for Yomitan](https://github.com/yomidevs/jmdict-yomitan/releases/latest/download/JMdict_french.zip)

Same term bank format as Jitendex. Key difference: `definitions` (index 5) is a **plain list of strings**, not structured content objects. Just join them with `"; "`. Still use `popularity` for ranking when multiple entries exist per headword.

### Example sentences (primary)
**Source:** Jitendex (same zip as above)

Extract from the `examples` ul node as described above. If an entry has an example sentence, use it — no need to call Ollama for the sentence itself, only for the French translation and sentence furigana.

### Example sentences + full generation (fallback)
**Source:** Ollama (local LLM)

Used when:
1. Jitendex has no example sentence for a word → generate JP sentence + EN + FR translations
2. Jitendex has a sentence but no FR translation → generate FR translation only
3. Always: generate `例文振り仮名` (sentence with ruby HTML furigana)
4. Always: generate `日本語ターゲット` (surface form of the word in the sentence) if fugashi can't find it

### Pitch accent (primary)
**Source:** Kanjium `accents.txt`
```
https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt
```
Download once and cache locally. Tab-separated, three columns: `expression`, `reading`, `pitch_pattern` (numeric drop position). Contains 124,137 entries. Words may appear multiple times with different readings — the first entry for a given expression is the most common reading/pattern; keep only the first match per expression when building the index.

Index by both `expression` (kanji) and `reading` (kana) so lookups work either way.

**Licensing note:** Kanjium pitch data is derived from commercial dictionaries (NHK, etc.). Use for personal study only.

### Pitch accent (fallback)
**Source:** NHK pronunciation CSV
```
https://raw.githubusercontent.com/javdejong/nhk-pronunciation/master/ACCDB_unicode.csv
```
Download once and cache locally. CSV columns (0-indexed): `NID`, `ID`, `WAVname`, `K_FLD`, `ACT`, `midashigo`(5), `nhk`(6), `kanjiexpr`(7), ..., `ac`(18).

Index by columns 5 (midashigo), 7 (kanjiexpr), and 6 (nhk reading). The `ac` column (index 18) is the numeric pitch accent pattern.

**Licensing note:** Derived from the NHK 日本語発音アクセント辞典 (commercial). Use for personal study only.

### Pitch accent (last resort)
**Source:** OJAD web API
```
https://www.ojad.jp/api/v0/words?limit=5&word={word}
```
Undocumented, unofficial API. Only reach here if both local sources fail. Response is JSON — look for an `accent` integer field in the `accents` array, or parse a `↓` marker in the `mora` string. Handle failures gracefully and silently.

---

## Word normalisation

Many words in the chadmuro dataset contain parenthesised content that must be handled before any lookup:

**Prefix parens** e.g. `（ご）主人`:
- Strip parens content to get bare form: `主人`
- Build form with content included: `ご主人`
- Try lookups in order: `ご主人` first, then `主人`

**Suffix parens** e.g. `残念（な）`, `勉強（する）`:
- These encode POS hints, not part of the lookup word
- Strip to get bare form: `残念`
- Infer 品詞: `な` → `な形容詞`, `する` → `サ変動詞`, `の` → `の形容詞`
- Use inferred POS as fallback if dictionary lookup finds no POS

---

## Furigana format

### Word furigana (振り仮名)
Source is bracket notation from chadmuro e.g. `食[た]べる` or `（ご） 主[しゅ] 人[じん]`.

Convert to ruby HTML:
- `食[た]べる` → `<ruby>食<rt>た</rt></ruby>べる`
- `（ご） 主[しゅ] 人[じん]` → `（ご）<ruby>主<rt>しゅ</rt></ruby><ruby>人<rt>じん</rt></ruby>`

Key regex rules:
- Base group must **start with a CJK character** to prevent absorbing preceding particles
- Collapse spaces between adjacent ruby blocks
- Collapse spaces immediately before a ruby block (for prefix cases like `（ご）`)

### Sentence furigana (例文振り仮名)
Generated by Ollama. Post-process with a normalisation function that handles whatever convention the LLM uses:

1. Strip redundant ruby where base is pure kana or pure katakana (e.g. `<ruby>もらう<rt>もらう</rt></ruby>` → `もらう`)
2. Strip paren/bracket readings on pure katakana words (e.g. `テレビ(てれび)` → `テレビ`)
3. Convert halfwidth paren notation: `漢字(かな)` → `<ruby>漢字<rt>かな</rt></ruby>`
4. Convert fullwidth paren notation: `漢字（かな）` → `<ruby>漢字<rt>かな</rt></ruby>`
5. Convert bracket notation: `漢字[かな]` → `<ruby>漢字<rt>かな</rt></ruby>`

Rules for all conversions:
- Base must start with a CJK character (prevents particle absorption)
- Never add furigana to katakana words
- Never add furigana to hiragana

---

## Sentence verification

When a sentence is retrieved from Jitendex, verify the target word actually appears as a **morphological token** — not just as a substring — using fugashi. For example, `夫` must not match `大丈夫`.

```python
import fugashi
tagger = fugashi.Tagger()
for token in tagger(sentence):
    lemma = token.feature.lemma or token.surface
    if lemma == word or token.surface == word:
        return True  # genuine match
return False
```

---

## Pitch accent diagrams

Generated by a separate script (`generate_pitch_svgs.py`) after the CSV is complete.

**Filename convention:** `{mora_count}_{pattern}.svg` e.g. `3_2.svg`

**Pitch pattern rules:**
- Pattern 0 (平板/heiban): `L H H H...` — particle is **HIGH**
- Pattern 1 (頭高/atamadaka): `H L L L...` — particle is **LOW**
- Pattern N, 2 ≤ N < mora_count (中高/nakadaka): `L H...H L...` — particle is **LOW**
- Pattern N = mora_count (尾高/odaka): `L H H...H` — particle is **LOW** (drops ON particle)

The odaka/heiban distinction is the reason the particle dot must be shown — both produce identical word-mora sequences for the same mora count, and only the particle pitch disambiguates them.

**SVG design:**
- Dots: solid red (#E05A6A) for high mora, solid cyan (#4EC3E0) for low mora
- Connecting lines between consecutive dots
- Particle dot: **hollow** (white fill, coloured stroke) to distinguish from word mora dots
- Particle colour follows its H/L level
- A small gap between the last word mora dot and the particle dot

---

## Ollama prompts

### Full generation (no Jitendex sentence found)

```
You are creating Japanese language study materials for a JLPT learner.

Target word: {word}
Part of speech: {pos}
English meaning: {en_gloss}

Write ONE example sentence that:
- Uses {word} naturally in a way that clearly illustrates its meaning and typical usage
- Is appropriately complex for a learner studying this word
- Prefers sentences that show the word in an informative context, not a trivial one

Rules for 例文振り仮名:
- Reproduce the sentence exactly, adding <ruby>kanji<rt>reading</rt></ruby> tags
- Add furigana ONLY on kanji characters — never on hiragana, katakana, or punctuation
- Do NOT wrap katakana words in ruby tags
- Correct: テレビを<ruby>見<rt>み</rt></ruby>る
- Incorrect: <ruby>テレビ<rt>テレビ</rt></ruby>を<ruby>見<rt>み</rt></ruby>る

Respond ONLY with a JSON object, no markdown, no explanation:
{
  "例文": "<sentence in natural Japanese>",
  "例文振り仮名": "<sentence with ruby tags on kanji only>",
  "英語例文": "<natural English translation>",
  "仏語例文": "<natural French translation>",
  "日本語ターゲット": "<surface form of {word} as it appears in the sentence>"
}
```

### Partial completion (Jitendex sentence found, need FR + furigana)

```
You are creating Japanese language study materials for a JLPT learner.

Target word: {word}
Part of speech: {pos}
Japanese sentence: {existing_jp}
English translation: {existing_en}

Rules for 例文振り仮名:
- Reproduce the sentence exactly, adding <ruby>kanji<rt>reading</rt></ruby> tags
- Add furigana ONLY on kanji characters — never on hiragana, katakana, or punctuation
- Do NOT wrap katakana words in ruby tags

Respond ONLY with a JSON object, no markdown, no explanation:
{
  "仏語例文": "<natural French translation of the Japanese sentence>",
  "例文振り仮名": "<sentence with ruby tags on kanji only>",
  "日本語ターゲット": "<surface form of {word} as it appears in the sentence>"
}
```

The LLM will return inconsistent furigana conventions — always post-process the `例文振り仮名` field through the normalisation function described above.

---

## Pipeline

### Main script: `build_jlpt_csv.py`

```
python build_jlpt_csv.py --model gemma3:12b
python build_jlpt_csv.py --model gemma3:12b --levels n4 n3   # subset
python build_jlpt_csv.py --model gemma3:12b --resume          # resume after crash
```

**Step 1 — Fetch word lists**
- Fetch raw `.ts` files from chadmuro repo for each level
- Parse with regex to extract `kanji`, `japanese`, `english` fields
- Deduplicate by headword (keep lowest level if a word appears in multiple)

**Step 2 — Build lookup indexes** (done once before the word loop)
- Download and extract Jitendex zip → build EN gloss + POS index + example index
- Download and extract JMdict French zip → build FR gloss index
- Download NHK CSV → build pitch accent index
- All indexes: `dict[headword → data]`, keeping highest-popularity entry per headword

**Step 3 — Word loop** (writes CSV incrementally, checkpoints after each word)

For each word:
1. Normalise headword → `lookup_forms` list + `inferred_pos`
2. Try each lookup form against Jitendex index → get `品詞`, `英語訳`, example sentence
3. Try each lookup form against JMdict French index → get `仏語訳`
4. If no `品詞` from Jitendex → use `inferred_pos`
5. If no `英語訳` from Jitendex → use `english` field from chadmuro source
6. If no `仏語訳` from JMdict French → call Ollama for French word translation
7. For the example sentence:
   - If Jitendex has one → verify with fugashi → use it
   - If not → call Ollama to generate sentence + EN + FR
8. Call Ollama for `例文振り仮名` and `日本語ターゲット` (always)
9. Post-process `例文振り仮名` through `normalise_furigana()`
10. If `日本語ターゲット` is empty → try fugashi as fallback
11. Look up pitch accent: OJAD first, NHK CSV fallback
12. Write row to CSV, flush, save checkpoint

**Step 4 — Generate SVGs** (separate script, run after CSV is complete)
```
python generate_pitch_svgs.py
```
Reads CSV, collects unique `(mora_count, pattern)` pairs from `ピッチアクセント図` column, generates one SVG per pair into `./pitch_svgs/`.

---

## File structure

```
build_jlpt_csv.py       — main pipeline
dictionary.py           — Jitendex + JMdict French index builders
pitch_accent.py         — OJAD + NHK pitch accent lookup
generate_pitch_svgs.py  — SVG diagram generator

jlpt_vocab.csv          — output
checkpoint.json         — resume state (safe to delete after completion)

dictionaries/
  jitendex-yomitan.zip
  JMdict_french.zip
  jitendex/term_bank_*.json
  jmdict_french/term_bank_*.json

nhk_data/
  ACCDB_unicode.csv

pitch_svgs/
  3_2.svg               — one file per (mora_count, pattern) combination
  4_0.svg
  unknown.svg           — placeholder for words with no pitch data
  ...
```

---

## Dependencies

```
requests>=2.31
fugashi[unidic]>=1.3
unidic-lite>=1.0
tqdm>=4.66
ollama>=0.2
```

After installing: `python -m unidic download`

No `lxml` required — all dictionary sources are JSON or CSV.

---

## Anki integration

Import `jlpt_vocab.csv` via **File → Import**. Enable "Allow HTML in fields" so ruby furigana renders.

Copy all SVGs from `pitch_svgs/` into your Anki media folder:
- macOS: `~/Library/Application Support/Anki2/<profile>/collection.media/`
- Linux: `~/.local/share/Anki2/<profile>/collection.media/`
- Windows: `%APPDATA%\Anki2\<profile>\collection.media\`

In your card template:
```html
{{振り仮名}}
<img src="{{ピッチアクセント図}}">
{{英語訳}}
{{例文振り仮名}}
{{英語例文}} / {{仏語例文}}
```

---

## Known issues and caveats

**OJAD API:** Undocumented, unofficial. May return unexpected JSON structure or fail silently. Always fall back to NHK CSV gracefully.

**NHK CSV licensing:** Derived from a copyrighted commercial dictionary. Personal study use only.

**Ollama JSON reliability:** Small models produce malformed JSON. Strip markdown fences before parsing. Log failures and continue — words that fail will have empty sentence fields and can be retried with `--resume`.

**Jitendex coverage:** Good for N4–N3, thinner for N2–N1. Expect more Ollama generation for higher levels.

**Furigana in sentences:** Ollama produces inconsistent conventions. Always run `normalise_furigana()` on the output regardless of how clean it looks.

**Pitch accent for compound/honorific words:** Words like `（ご）主人` should use the normalised lookup form (`ご主人` or `主人`) for pitch accent lookup, not the raw headword with parentheses.

**`forms` entries in Jitendex:** Many headwords have a companion `forms` entry (with `def_tags == "forms"`) containing variant spelling tables. These yield no glosses and should be skipped — filter by checking `def_tags.strip() == "forms"` or checking that the entry has no `glossary` ul nodes.
