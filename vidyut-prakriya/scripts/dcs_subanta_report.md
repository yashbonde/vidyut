# vidyut-prakriya subantas against the Digital Corpus of Sanskrit

This report checks how many attested nominal forms (nouns, adjectives,
pronouns and numerals) of the Digital Corpus of Sanskrit (DCS) vidyut-prakriya
can derive, sorts the misses, and lists the vidyut defects that the misses
point to. It was produced with `check_dcs_subanta_coverage.py` in this
directory; the regression sample is `../tests/data/dcs_subanta_corpus.tsv`.

## Data and credit

- **Corpus:** Oliver Hellwig, *The Digital Corpus of Sanskrit (DCS)*,
  2010 to 2024, <https://github.com/OliverHellwig/sanskrit>, CoNLL-U dump in
  `dcs/data/conllu`, commit `8aeed5a` (2026-08-24). Licensed CC BY 4.0. Only
  the `*.conllu` files are read; the `*.conllu_parsed` files are a parallel
  treebank version of many of the same chapters (84% of their sentences repeat
  a `.conllu` sentence), so reading both would count those tokens twice.
- **Engine:** the vidyut-prakriya WebAssembly build served by vidyut's own
  demo (fetched 2026-10-22, `Last-Modified` 2026-10-17; sha256 of
  `vidyut_prakriya_bg.wasm` begins `4cd70686`), run under Node 22. This branch
  is cut from upstream main `8da2f90`; the build is expected to be close to
  main but was not built from this tree, because no Rust toolchain was used.
  Where noted, results were also compared with the `vidyut` 0.4.0 Python
  bindings from PyPI.
- **Verification:** Bhattoji Dikshita's *Siddhantakaumudi* (SK), SARIT TEI
  edition (`bhattojidiksita-siddhantakaumudi.xml`); SK numbers below follow
  that edition.

## Method

1. Every DCS token tagged NOUN, ADJ, PRON or NUM with a real case is an
   attestation. Compound members (`Case=Cpd`, 813,310 tokens) are skipped.
   Distinct (lemma, gender, case, number, form) items are counted with their
   token frequency and the DCS period of each token (time slot 1 is "Vedic";
   the epics, puranas and two mahatmyas are "epic"; eight Buddhist Hybrid
   Sanskrit texts are "BHS"; the rest is "classical").
2. The form compared is the annotator's pausa form (`Unsandhied`). Where the
   DCS marks that form `UnsandhiedReconstructed=True` it was generated
   automatically and is often wrong (`tāta` becomes "tātaiḥ", `patyur` becomes
   "pateḥ", `bhiṣak` becomes "bhiṣaj"), so the surface form is used instead,
   with the usual final-sound sandhi undone (`devo` may be `devaḥ`, `tāṃs` may
   be `tān`). For a word inside a multiword token, the derived form must also
   fit the surface of the whole token. Nasals before consonants are compared as
   anusvara on both sides, because the DCS writes `saṃdeha` where vidyut writes
   `sandeha`.
3. Lemmas are converted from IAST to SLP1 and passed to vidyut as follows:
   - basic pratipadika with the token's gender, which lets vidyut add the
     feminine suffix itself (`sundara` + Stri gives `sundarI`);
   - `nyap` for DCS feminine lemmas in -ā and polysyllabic -ī, except the
     non-derived ī-stems (`lakṣmī`, `tarī`, `tantrī`, `avī`, `starī`);
   - a few pronoun lemmas are renamed (`mad` to `asmad`, `tvad` to `yuṣmad`,
     `ka` to `kim`, `ubh` to `ubha`), `ahar` to `ahan`, `puṃs` to `pums`, and
     stems cited strong (`bhagavant`) are cut back to -at;
   - indefinites (`kaścit`, `kaścana`) are checked as `kim` after the particle
     is stripped from the form.
   This is the **primary input**. When it misses, a short list of
   **alternative inputs** is tried: kṛdanta or taddhitanta inputs for stems
   whose behaviour depends on their derivation (`bhavat` as BA + ḍavatu,
   `mahat` as maha + ati, `vidvas` as vid + śatṛ, `śrī`, `dhī`, `bhī`, `hrī`,
   `bhū`, `gir`, `pur`, `āśis` as kvip, the añc stems as kvin, the rāj stems as
   kvip, -mat/-vat stems as matup, comparatives as īyasun), explicit feminine
   stems (`nyap` of -ā, -ī, -atī, -inī, -trī, -vī, -ikā), the other of nyap and
   basic, and the short stem of a feminine noun used at the end of a bahuvrihi
   (`nāmākhyaḥ` from `ākhyā`, 1.2.48).
4. An item is covered if the attested form is among vidyut's outputs for that
   slot. Misses are classified by rules that run in a fixed order: hand-reviewed
   pairs, the new defects verified below, DCS lemmatization problems (a), the
   open upstream issues, spelling variants (a), Vedic endings and texts (b),
   epic, puranic or BHS texts (b), forms that vidyut produces only for another
   slot or gender (a), and the rest (c). The rules are in the script.

The output is deterministic (two runs give byte-identical files).

## Headline numbers

| | items (types) | tokens |
|---|---:|---:|
| attested nominal items | 279,962 | 2,903,345 |
| covered by the primary input | 261,003 (93.2%) | 2,799,539 (96.4%) |
| covered by primary or alternative input | 268,334 (95.8%) | 2,840,589 (97.8%) |

Another 4,582 tokens have a lemma or form that does not convert to SLP1
(placeholders such as `_`, digits, stray characters).

Of the 62,756 tokens that no input covers: 22,337 are (a) mapping or DCS
annotation problems, 23,784 are (b) Vedic, epic or other forms outside the
classical paradigm, 10,568 match an open upstream issue, 3,976 are the new
defects below, and 2,091 are unexplained (mostly one-off spellings and lemma
mismatches; see the end of this report).

### By stem ending (tokens)

| ending | types | tokens | primary | with alternatives |
|---|---:|---:|---:|---:|
| a | 187,426 | 1,489,322 | 98.1% | 98.7% |
| pronoun | 2,277 | 561,695 | 97.9% | 97.9% |
| i | 16,250 | 169,613 | 98.2% | 98.8% |
| ā | 19,058 | 118,517 | 94.7% | 99.1% |
| -an | 4,120 | 81,218 | 96.5% | 96.5% |
| u | 7,885 | 78,757 | 96.8% | 97.6% |
| ī | 10,910 | 66,761 | 92.3% | 97.5% |
| -as | 4,152 | 63,265 | 97.1% | 99.0% |
| -in | 9,663 | 48,542 | 97.5% | 97.7% |
| numeral | 956 | 45,351 | 99.0% | 99.0% |
| -mat/-vat | 5,912 | 35,302 | 40.6% | 92.5% |
| ṛ | 2,505 | 31,388 | 90.3% | 90.3% |
| other dental | 2,524 | 24,523 | 99.1% | 99.1% |
| palatal (c j ś) | 1,488 | 23,095 | 88.9% | 89.7% |
| other consonant | 1,513 | 18,449 | 93.2% | 93.2% |
| -is/-us | 742 | 15,140 | 61.9% | 65.3% |
| -at/-ant | 1,044 | 13,294 | 78.4% | 81.5% |
| ū | 505 | 5,875 | 68.1% | 89.9% |
| e/ai/o/au | 162 | 4,609 | 98.5% | 98.5% |
| -ac/-añc | 341 | 3,262 | 63.1% | 67.5% |
| -r | 205 | 2,944 | 83.7% | 90.5% |
| -vas | 324 | 2,423 | 72.6% | 95.6% |

### By gender, case, number and period (tokens)

| | tokens | primary | with alternatives |
|---|---:|---:|---:|
| masculine | 1,700,914 | 96.7% | 98.1% |
| neuter | 766,664 | 97.4% | 97.5% |
| feminine | 435,767 | 93.5% | 97.5% |
| nominative | 1,225,043 | 96.6% | 98.7% |
| accusative | 706,118 | 95.9% | 97.2% |
| instrumental | 269,269 | 96.7% | 97.7% |
| dative | 64,256 | 96.6% | 97.2% |
| ablative | 74,734 | 87.6% | 87.8% |
| genitive | 257,980 | 98.3% | 98.7% |
| locative | 225,043 | 97.3% | 98.0% |
| vocative | 80,902 | 96.2% | 97.2% |
| singular | 2,272,839 | 96.6% | 98.1% |
| dual | 64,398 | 90.7% | 92.4% |
| plural | 566,108 | 96.3% | 97.3% |
| classical | 821,536 | 97.6% | 98.6% |
| epic and puranic | 1,257,504 | 97.7% | 99.1% |
| Vedic | 767,617 | 93.4% | 95.0% |
| BHS | 56,688 | 91.5% | 97.3% |

The ablative is low because the DCS tags `-tas` adverbs (`prayatnataḥ`,
`mattaḥ`) as ablatives and lemmatizes the abstract suffix `-tva` as a noun
`tva`, which vidyut reads as the sarvadi pronoun `tva` (`tvāt` against
`tvasmāt`). The dual is low mostly because of Vedic duals in -ā.

### Inputs that matter

40,999 tokens are covered only by an alternative input: 22,665 by a kṛdanta or
taddhitanta input, 11,656 by an explicit feminine stem, 6,115 by a short
upasarjana stem, and 563 by swapping nyap and basic. The first group is the
practical lesson: a basic pratipadika does not know that it carries an
anubandha, so `Pratipadika.basic("SrImat")` gives nominative `SrImat`, not
`SrImAn`; the same holds for `Bagavat` (3,600 tokens of `bhagavān` alone),
`Bavat`, `vIryavat`, `DImat`, `vidvas`, comparatives in -īyas, and for kvip
stems such as `SrI` (`SryA` against `SriyA`) and `gir`. Users of the DCS or of
any dictionary stem list need the kṛdanta and taddhitanta inputs.

## Miss categories

The largest groups, with examples (form, DCS lemma, slot, tokens).

**(a) Mapping and DCS annotation, 22,337 tokens.**
- `enad` (8,461): the anvadesha substitute of idam/etad (2.4.34) is a DCS
  lemma (`enam`, `enān`), but it is not an input stem for vidyut.
- `-tas` adverbs tagged as ablatives (4,896): `prayatnataḥ` 240,
  `tattvataḥ` 231, `mattaḥ`, `tvattaḥ`.
- the suffix `-tva` lemmatized as a noun (4,435): `tvāt` 3,438, `tve`.
- spelling variants in the source (3,167): `patrāṇi` for `pattrāṇi`, `satvaṃ`,
  `chatraṃ`, `mūrcchā`; also compounds that the DCS lemmatizes as one stem,
  where vidyut applies ṇatva across the members (`karīṣāgnau`).
- a form identical to a consonant-final lemma (435): sutra citations in the
  Aṣṭādhyāyī and Kāśikā (`ṭhañ`, `vuñ`) and reconstructions.
- `ubhaya` in the dual (339): ubhaya has no dual; these are forms of `ubha`.
- other slot or gender (371), sarvadi words in a non-pronominal sense (233:
  `samāḥ` "equal", `parāṇām` "of the enemies").

**(b) Outside the classical paradigm, 23,784 tokens.**
- Vedic endings: -ā for -au and for neuter -āni (3,767, 7.1.39 and 6.1.70),
  -āsaḥ (1,283, 7.1.50), -ebhiḥ (914, 7.1.10), Vedic pronoun forms (442:
  `asme`, `tve`).
- Other items mostly attested in Vedic texts (14,142): `aśvinā`, `dyām`,
  `ātman` as a locative, `devīḥ` as a nominative plural.
- Items mostly attested in epic, puranic or BHS texts (3,000): `kaccit`,
  `svayaṃbhuvā`, `koṭyo`.
- `pati` declined as a ghi stem outside compounds (236: `pateḥ`, `patinā`,
  1.4.8), `sakhi` and `pathin` as plain stems.

**Open upstream issues, 10,568 tokens.** See the next section.

**(c) New defects, 3,976 tokens.** See "New verified defects".

## Open upstream issues: DCS evidence

"Cells" counts attested tokens in the slots that the issue says are affected;
"derived" counts how many of those the tested build derives; "matching misses"
counts misses that show exactly the reported defect.

| issue | topic | cells | derived | matching misses | verdict |
|---|---|---:|---:|---:|---|
| #255 | palatal sibilant stems | 1,429 | 481 | 835 | confirmed: `dikṣu` 367, `digbhyaḥ` 118, `vikṣu` 65, `digbhiḥ` 30, `dik`/`dig` 44, `tādṛk`/`yādṛg` |
| #256 | bare -at/-ant stems | 9,202 | 6,347 | 664 | confirmed: `arhantaḥ` 77, `bṛhantam` 63, `arhantam` 25, `bṛhantaḥ` 20; plus 22,665 tokens (see "Inputs that matter") that only kṛdanta or taddhitanta inputs derive |
| #257 | neuter i-stems | 2,313 | 2,088 | 206 | accusative plural part is fixed in this build (fails in 0.4.0); the akṣi/asthi/dadhi/sakthi part is confirmed: 113 tokens in the cells the issue names (`asthiṣu`, `asthibhiḥ`, `asthnām`, `akṣibhyām`, `akṣṇām`) |
| #258 | -in stems | 104 | 49 | 13 | neuter accusative plural is fixed in this build; feminine genitive plural and locative singular confirmed but rare in the DCS, which lemmatizes most of these feminines as -inī; the same locative `-yE` appears for every basic stem that vidyut feminizes itself (`kadalyE`, `maṅgalyE`, `mahatyE`), 54 more tokens |
| #259 | numerals in sg/du | 167 | 141 | 26 | supported: tri and catur are plural in the DCS; the few singular tags are `catuḥ` "four times" (suc) and sutra citations |
| #260 | -is/-us ruki | 10,527 | 4,845 | 6,216 | confirmed, the largest known issue: `cakṣuṣā` 498, `haviṣā` 409, `yajuṣā` 294, `sarpiṣā` 250, `āyuṣā` 200; the same defect hits -iṣmat/-uṣmat stems (`āyuṣmān` 389, `cakṣuṣmān`) |
| #261 | bare -tṛ agent nouns | 5,639 | 3,018 | 2,599 | confirmed; the accusative singular is the largest cell (`bhartāram` 327, `savitāram` 117, `kartāram` 93), although the issue lists it as correct: both this build and 0.4.0 give `dAtaram` |
| #271 | -mat/-mant weak cells | 4,724 | 4,670 | 6 | not confirmed: 98.9% derived; the 6 misses are Vedic `-ante` datives; `basic("DImat")` gives `DImate` in this build and in 0.4.0 |
| #250 | eka not sarvadi | 678 | 660 | 0 | fixed in this build (`ekasmin`, `ekasmai`, `ekasyāḥ` derived); the 18 non-derived tokens are Vedic or epic non-pronominal forms |
| #247 | -aka feminines in -ikā | 1,158 | 906 | 209 | confirmed: 209 tokens (119 types) of -ikā for DCS -aka lemmas that vidyut gives as -akā: `paramikām`, `ātmikā`, `pūrvikām`, `sādhikā`, `dāyikā` |
| #229 | alpa feminine | 58 | 58 | 0 | supported: all 58 feminine tokens of alpa are ṭāp forms (`alpā`), which vidyut-prakriya derives; the issue is in the generated stem list |
| #262 | Dhatu.mula lookup | | | | not testable with nominal data |

Comment drafts with these numbers are in `dcs_subanta_drafts/comments.md`.

## New verified defects

Each was checked against the SK before being listed. Token counts are DCS
tokens that miss because of the defect; references are the first attestation
in DCS file order (chapter citation and `sent_id`). Issue drafts are in
`dcs_subanta_drafts/`.

### 1. `idam` neuter plural: `idAni` instead of `imAni` (475 tokens)

- DCS: `imāni` 317 tokens (nominative and accusative; AĀ 1.3.4 #765183,
  Rām Bā 71 #115795, Kir 8 #358386), Vedic `imā` 157.
- vidyut: `basic("idam")`, Napumsaka, Prathama or Dvitiya, Bahu gives `idAni`;
  the dual gives `ime`, so 7.2.109 does fire there. Same in 0.4.0.
- Rule: 7.2.109 *daś ca*. SK 345: "इदमो दस्य मः स्याद्विभक्तौ" (d of idam
  becomes m before a case ending), with `imau`, `ime`; the neuter pronouns
  are listed as `te`, `tāni`, `ete`, `etāni`. `śi` is a case ending by
  sthanivadbhava, so `ima` + `śi` gives `imāni`.
- Confidence: high.

### 2. `mahat` cannot reach `mahAn` through the public API (1,801 tokens)

- DCS: `mahān` 1,573 (ACint 2 #506384), `mahāntam` 167, `mahāntaḥ` 50,
  duals `mahāntau` 11.
- vidyut: `basic("mahat")` gives `mahat` (expected, see #256), but the
  documented kṛdanta input `Pratipadika.krdanta(maha~ Bhvadi, Unadi::ati)`
  gives `mahan`, `mahantam`, `mahantaH`. The trace shows śap (3.1.68) inserted
  between `mah` and `at` because of śatṛvat, so when 6.4.10 tests the anga for
  the text `mahant`, the terms read `mah` + `a` + `ant` and the rule does not
  fire. The integration test `sutra_6_4_10` passes only because it builds the
  stem with `.require("mahat")`, which derives the kṛdanta separately first
  (`prepare_pratipadika_inner` in `ashtadhyayi.rs`); the WASM and Python APIs
  cannot set `require`.
- Rule: 6.4.10 *sāntamahataḥ saṃyogasya*. SK, under uṇādi *vartamāne
  pṛṣadbṛhanmahat...*: "उगित्त्वान्नुम् । सान्तमहत इति दीर्घः ... महान् ।
  महान्तौ".
- Confidence: high for the output, medium for the cause (not rebuilt here).

### 3. Stems in añc (kvin): weak cases, feminine and two pūrvapada rules (1,479 tokens)

- DCS: feminines `prācī`/`prācīm`/`prācyām` (476 tokens), `udīcī` (252),
  `pratīcī` (253), `samīcī` (53); weak cases `prācaḥ` (AB 6.22 #664736),
  `udīcaḥ`, `pratīcaḥ`, 226 tokens; strong and neuter forms of `tiryañc`
  and `samyañc`, 113 tokens. Most tokens are Vedic prose, but these are the
  classical forms.
- vidyut, with `Pratipadika.krdanta(ancu~ Bhvadi + prefix, Krt::kvin)`:
  - accusative plural `pracaH` (pra), `praticaH` (prati), `uccaH` (ud),
    `saMcaH` (sam), `avacaH` (ava); expected `prAcaH`, `pratIcaH`, `udIcaH`,
    `samIcaH`, `avAcaH`. In 0.4.0 `prAcaH` was right, so the pra case is a
    regression; `pratyacaH` was already wrong.
  - feminine: no ṅīp at all (`prAN`, `prAYcO` for Stri).
  - sam: strong `samaN` (expected `samyaN`, 6.3.93).
  - the basic stems `prAYc`, `tiryaYc` decline as plain nasal stems
    (`tiryaN` for neuter `tiryak`).
- Rules: 6.4.138 *acaḥ* with 6.3.138 *cau* (SK 417: "प्राचः । प्राचा ...
  प्रतीचः । प्रतीचा"), 6.4.139 *uda īt* (SK 420: "उदीचः । उदीचा"), 6.3.93
  *samaḥ sami* (SK 421: "सम्यङ् ... समीचः"), 4.1.6 *ugitaś ca* (SK 455:
  "अञ्चतेस्तु स्यादेव । प्राची । प्रतीची").
- Confidence: high. `tiras` + añc could not be tested properly, because the
  WASM krdanta input has no upapada field; it is left out of the draft.

### 4. `nyap` stems of the ajādi gaṇa get a second ṭāp (83 tokens)

- DCS: `vatse` 33 (DKCar 2.6 #489018), `ajayā` 15, `bāle` 7, `bālayā`,
  `jyeṣṭhayā`, `kaniṣṭhayā`, `madhyamayā`, `aśvayā`, `kokilayā`.
- vidyut: `nyap("ajA")` gives instrumental `ajAyA`, genitive dual `ajAyoH`,
  vocative `ajE`; `nyap("ramA")` gives `ramayA`, `rame`. `basic("aja")` with
  Stri is correct. Same in 0.4.0.
- Cause: `stritva::run` adds ṭāp when `last.has_text_in(gana::AJADI)`, and the
  gaṇa lists the feminine forms (`ajA`, `vatsA`, `jyezWA`), so a nyap stem
  that already carries its dummy ṭāp matches and gets another one.
- Rules: 4.1.4 *ajādyataṣ ṭāp* (SK 454: "अजा"), then the ramā paradigm,
  7.3.105 *āṅi cāpaḥ* (SK 289: "रमया") and 7.3.106 (SK: "हे रमे").
- Confidence: high.

### 5. `maghavan`: 6.4.128 not implemented (96 tokens)

- DCS: `maghavān` 61 (AB 5.21 #664360), `maghavatā` 21 (BhāgPur 4.20
  #94412), `maghavatsu` 10, `maghavati`, `maghavate`, `maghavato`.
- vidyut: only the an-stem paradigm (`maGavA`, `maGonA`). Same in 0.4.0.
- Rule: 6.4.128 *maghavā bahulam*, an optional tṛ substitute that makes the
  stem ugit. SK 360 and 361: "मघवन्शब्दस्य वा तृ इत्यन्तादेशः स्यात् ...
  मघवान्".
- Confidence: high (an optional rule, so both paradigms should be produced).

### 6. `samrāj`: 8.3.25 not applied (42 tokens)

- DCS: `samrāṭ`/`samrāḍ` 30 (AgniPur 18 #484650, BhāgPur 3.22 #91594), Vedic
  `samrājā`.
- vidyut: `Pratipadika.krdanta(rAjf~^ Bhvadi + sam, Krt::kvip)` gives
  `saMrAw`, `saMrAjO`, with anusvara; same in 0.4.0. (The basic stem gives
  `samrAk`, the expected basic-stem limitation for 8.2.36.)
- Rule: 8.3.25 *mo rāji samaḥ kvau*. SK 126: "समो मस्य म एव स्यात् । सम्राट्".
- Confidence: high; low frequency.

### Leads not verified

- matup after `garut`, `kakud`, `harit`: the taddhitanta input gives
  `garutvAn`, `kakudvAn` (8.2.10), while the DCS has `garutmān` 13 and
  `kakudmān` 8. vidyut's yavādi list blocks only 8.2.9, and lists `kakuda`
  rather than `kakud`. The SK edition used does not settle whether
  *ayavādibhyaḥ* continues into 8.2.10, so this is not reported.
- `udanvat` as `udan` + matup gives `udavataH`; 8.2.13 is a nipatana.

## What remains unexplained

2,006 tokens (1,251 types) are not generated and match no rule, plus 85 where
vidyut puts the form in another slot. The top of the list was read by hand:
lemma and form disagree (`ghuṭikā` for lemma `guṭikā`, `īśvarī` for `īśvarā`,
`saurāṣṭrī` for `saurāṣṭrā`), spelling variants of vowels or sibilants
(`coraṃ` for `cora`, `kāśīśa`, `koṣa`, `vasti`/`basti`), feminine bahuvrihi
forms (`mannāmnīm`, `lolākṣyāḥ`), kvip compounds passed as basic stems
(`manobhuvā`, `sudhiyaḥ`), and truncated DCS forms (`tayo`, `sarvai`).
None of the top 60 looked like a vidyut defect beyond those listed above.

## Reproducing

```
# DCS: git clone https://github.com/OliverHellwig/sanskrit
# Engine: a `wasm-pack build --target web` of vidyut-prakriya, giving
#   vidyut_prakriya.js and vidyut_prakriya_bg.wasm in one directory.
python3 -I scripts/check_dcs_subanta_coverage.py \
    sanskrit/dcs/data/conllu/files --wasm-dir <build dir> \
    --summary-out summary.json --misses-out misses.tsv --alt-out alt.tsv \
    --corpus-out tests/data/dcs_subanta_corpus.tsv

# Regression check of the sample against a build (WASM or Python bindings):
python3 -I scripts/check_dcs_subanta_coverage.py \
    --check-corpus tests/data/dcs_subanta_corpus.tsv --wasm-dir <build dir>
python3 scripts/check_dcs_subanta_coverage.py \
    --check-corpus tests/data/dcs_subanta_corpus.tsv --engine python
```

A full run reads 16,051 CoNLL-U files and takes about one minute. With the
tested build all 12,000 sample rows are derived; with vidyut 0.4.0 11,868 are.
