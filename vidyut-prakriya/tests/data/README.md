# Test data

## `rv_let_corpus.tsv` — present-stem leṬ (लट्-stem)

826 present-stem subjunctive (leṬ) forms from the Rigveda, filtered from
Oliver Hellwig's morpho-lexical annotation of the Rigveda.

- **Tag filtered:** `tense_mode = "Present conjunctive (subjunctive)"`

## `rv_let_aorist_corpus.tsv` — aorist-stem leṬ (लुङ्-stem)

605 aorist-stem subjunctive forms from the Rigveda. Used for the Phase 4
implementation track (leṬ built on the aorist stem, distinct from the
present-stem leṬ in `rv_let_corpus.tsv`).

- **Tag filtered:** `tense_mode = "Aorist conj./subj."`

## `rv_let_perfect_corpus.tsv` — perfect-stem leṬ (लिट्-stem)

182 perfect-stem subjunctive forms from the Rigveda. Used for the Phase 5
implementation track (leṬ built on the perfect/reduplicated stem).

- **Tag filtered:** `tense_mode = "Perfect conjunctive (subj.)"`

## Source and license

- **Source:** Hellwig, O., Hettrich, H., Modi, A., Pinkal, M. (2018).
  *Multi-layer Annotation of the Rigveda.* LREC 2018.
  Repository: <https://github.com/OliverHellwig/sanskrit>
- **License:** CC BY 4.0

### Columns (same for all three TSVs)

| Column | Meaning |
|---|---|
| `ref` | maṇḍala.sūkta.ṛc.pāda (e.g., `1.166.14.2` = RV 1.166.14, line 2 = pādas c+d) |
| `pos` | word position within the line |
| `word` | surface form (IAST) |
| `surface_form` | canonical surface form (IAST, same as `word` for most rows) |
| `lemma` | dictionary lemma (IAST) |
| `root`, `prefixes` | usually empty |
| `person` | 1 / 2 / 3 |
| `number` | 1 (sg) / 2 (du) / 3 (pl) |
| `tense_mode` | matches the per-TSV filter above |

### Used by

- `tests/integration/rv_let_corpus.rs` — लट्-stem (active baseline, ~83% match)
- `tests/integration/rv_let_aorist_corpus.rs` — लुङ्-stem (Phase 4 scaffold; currently expected to fail until `Tinanta::let_stem(LetStem::Lun)` is implemented)
- `tests/integration/rv_let_perfect_corpus.rs` — लिट्-stem (Phase 5 scaffold; currently expected to fail until `Tinanta::let_stem(LetStem::Lit)` is implemented)

Each test reads its TSV, derives each form via vidyut, and asserts the
corpus `surface_form` appears in vidyut's output. Failures are listed all
at once in the test output.

## `dcs_subanta_corpus.tsv`: nominal forms from the DCS

12,000 attested subanta forms (nouns, adjectives, pronouns, numerals) from
the Digital Corpus of Sanskrit that vidyut-prakriya derives. The sample is
deterministic: the five most frequent items of every (stem class, linga,
vibhakti, vacana) cell, then the most frequent items overall. It is written by
`scripts/check_dcs_subanta_coverage.py --corpus-out`, and
`scripts/check_dcs_subanta_coverage.py --check-corpus` re-derives every row
against a WASM build or the Python bindings. The method, coverage numbers and
the misses are in `scripts/dcs_subanta_report.md`.

- **Source:** Oliver Hellwig, *The Digital Corpus of Sanskrit (DCS)*,
  2010 to 2024, <https://github.com/OliverHellwig/sanskrit>, CoNLL-U dump,
  commit `8aeed5a`.
- **License:** CC BY 4.0

| Column | Meaning |
|---|---|
| `pratipadika` | the vidyut input: `basic:deva`, `nyap:ramA`, `taddhitanta:SrI/matup`, `krdanta:pra+ancu~/Bhvadi/kvin`, `krdanta:BA\/Adadi/unadi:qavatu` |
| `linga`, `vibhakti`, `vacana` | vidyut enum names |
| `form` | the derived form that matches the attestation (SLP1) |
| `form_iast` | the DCS form (pausa form, or surface form where the DCS pausa form was reconstructed automatically) |
| `lemma` | DCS lemma (IAST) |
| `stem_class` | coarse stem class used in the report |
| `tokens` | number of DCS tokens of this item |
| `ref`, `sent_id` | DCS chapter citation and sentence id of the first attestation |
