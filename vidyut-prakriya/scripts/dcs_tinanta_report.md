# Tinanta coverage against the DCS

This report checks vidyut-prakriya's finite verb (tiṅanta) generation against
every finite verb attested in the Digital Corpus of Sanskrit (DCS). It was
produced with `scripts/check_dcs_tinanta_coverage.py`. The regression sample
is `tests/data/dcs_tinanta_corpus.tsv`.

## Data and engine

- **Corpus:** Hellwig, O. (2010 to 2024). *The Digital Corpus of Sanskrit
  (DCS).* CoNLL-U dump from <https://github.com/OliverHellwig/sanskrit>,
  `dcs/data/conllu`, commit 8aeed5a1 (2026-08-24). Licensed CC BY 4.0. The
  DCS readme asks users to cite it as `Hellwig, Oliver. The Digital Corpus of
  Sanskrit (DCS). 2010 to 2024.`
- **Engine:** the vidyut-prakriya WASM build served by the vidyut demo,
  fetched 2026-10-22 (last-modified 2026-10-17; sha256 of
  `vidyut_prakriya_bg.wasm` starts `4cd706862cea2fe0`). It is close to `main`
  at 8da2f90 (it includes the leṬ work of #242) but is not built from this
  branch. Default `Vyakarana` settings: no chandasa rules, default pada.
- **Dhatupatha:** `data/dhatupatha.tsv` from this branch, with antargaṇas
  assigned the same way as `maybe_find_antargana` in `src/dhatupatha.rs`.
- For comparison the same script was also run with the Python bindings of
  vidyut 0.4.0 (`--engine python`).

To reproduce:

```
make wasm_release      # in vidyut-prakriya/, writes pkg/
python3 scripts/check_dcs_tinanta_coverage.py \
    PATH/TO/sanskrit/dcs/data/conllu --wasm-pkg pkg --out-dir /tmp/dcs
```

A full run takes about two minutes. Two runs with different `PYTHONHASHSEED`
values give byte-identical outputs.

## Method

1. **Items.** Every CoNLL-U token with `UPOS=VERB` and a `Person` feature is
   one finite verb token. Tokens are grouped into items by (lemma id, form,
   unsandhied form, person, number, tense, mood, formation, voice), with
   token counts and DCS time slots (`chapter-info.xml`).
2. **Tags to lakaras.** An item is checked against the lakaras its tag
   allows. DCS `Past` covers liṬ, luṄ and (in older annotation) laṄ, so
   `Past Ind` accepts any of the three. `Fut Ind` accepts lṚṬ and luṬ.
   Subjunctive (`Sub`) maps to leṬ. Injunctive (`Jus`) maps to laṄ or luṄ
   without the aṬ augment (`skip_at_agama`). `Voice=Pass` maps to karmaṇi.
   The Vedic categories with no single Pāṇinian lakara (aorist imperative
   and optative, pluperfect) are tried against the nearest lakaras and
   reported separately.
3. **Lemmas to dhatus.** DCS folds preverbs into the lemma (`uddhṛ`,
   `samudāhṛ`) and lists them in `dictionary.csv` (`ut`, `samudā`). The
   script splits the lemma into upasargas plus a root, allowing for sandhi
   at the join (vowel merger, `ud + sthā = utthā`, ṣatva and ṇatva), and
   checks the split against the listed preverbs. The root is then looked up
   in an index built from vidyut itself: the dhatu text of every
   dhatupatha entry, the laṬ stems of curādi and Āya roots (`coray`,
   `gopāy`), and the causative, desiderative and intensive stems
   (`darśay`, `didṛkṣ`), since DCS lists those as separate lemmas. A small
   alias table handles DCS citation habits (`paś` for dṛś, `ah` for brū,
   `dham` for dhmā, `gā` for the luṄ of iṆ, roots in -ai cited in -ā).
   Gati words (`antar`, `prādus`, `śrat`, `sākṣāt`, cvi words like
   `bhasmī`) are passed through as prefixes.
4. **Coverage.** An item is covered if ANY candidate dhatu entry, with
   vidyut's default pada, produces the attested form in an allowed lakara.
   The attested form is the DCS unsandhied form when present, else the
   surface form with word-final sandhi undone (`-o` to `-aḥ`, `-d` to `-t`,
   `-ṃ` to `-m`, and so on). Nasals before stops are compared loosely, and
   `cch` matches `ch`.
5. **Misses.** A second pass tries every lakara, both voices, both augment
   settings and the causative. The remaining misses are bucketed by the
   rules listed under "Misses" below. Nothing in steps 1 to 5 reads the
   Siddhāntakaumudī; that was a separate manual check (step 6).
6. **Verification.** Missed forms were searched in the SARIT TEI text of
   the Siddhāntakaumudī (and in `data/kashika.tsv` where it has the sūtra),
   and near misses (vidyut form differs by ṣ/s, ṇ/n or vowel length) were
   reviewed by hand.

## Headline numbers

| | tokens | types |
|---|---:|---:|
| Finite verbs in the DCS | 536,137 | 59,888 |
| Mapped to a dhatupatha entry | 531,893 (99.2%) | 58,185 (97.2%) |
| Covered by vidyut | 494,844 | 47,241 |
| Covered, share of mapped | 93.0% | 81.2% |
| Covered, share of all | 92.3% | 78.9% |

2,288 of the covered tokens (654 types) need a gati prefix such as `antar`
or a cvi word. vidyut accepts such prefixes as given, so these are weaker
evidence than the rest.

### By DCS tag (share of mapped tokens)

| Tag | tokens | covered | % |
|---|---:|---:|---:|
| Pres Ind (laṬ) | 184,388 | 174,931 | 95.9% |
| Past Ind (liṬ, luṄ, laṄ) | 95,604 | 86,252 | 90.4% |
| Pres Opt (vidhiliṄ) | 90,778 | 86,847 | 96.3% |
| Pres Imp (loṬ) | 52,751 | 48,137 | 92.4% |
| Impf Ind (laṄ) | 47,113 | 42,828 | 91.5% |
| Pres Ind Pass | 23,609 | 23,365 | 99.1% |
| Fut Ind (lṚṬ, luṬ) | 21,515 | 19,731 | 92.0% |
| Past Jus (injunctive) | 4,144 | 2,971 | 72.0% |
| Pres Imp Pass | 3,470 | 3,411 | 98.5% |
| Pres Sub (leṬ) | 3,107 | 1,399 | 47.0% |
| Past Imp (aorist imperative) | 1,709 | 115 | 6.9% |
| Impf Ind Pass | 1,505 | 1,440 | 96.2% |
| Past Sub (leṬ) | 1,328 | 113 | 8.6% |
| Pres Jus (injunctive) | 1,194 | 780 | 72.0% |
| Past Opt (aorist optative) | 1,103 | 319 | 28.9% |
| Pres Opt Pass | 852 | 832 | 97.7% |
| Past Ind Pass | 781 | 581 | 74.5% |
| Past Prec (āśīrliṄ) | 602 | 533 | 89.1% |
| Fut Cond (lṚṄ) | 348 | 252 | 72.4% |
| Plp / Pqp Ind (pluperfect) | 204 | 7 | 3.4% |

### By gaṇa (covered tokens over mapped tokens)

"More than one gaṇa" means the lemma maps to entries in several gaṇas
(vid, as, dhā, ...) and the item is not covered by exactly one of them.

| Gaṇa | tokens | covered | % |
|---|---:|---:|---:|
| bhvādi | 146,914 | 137,621 | 93.7% |
| adādi | 88,135 | 84,984 | 96.4% |
| juhotyādi | 21,181 | 20,818 | 98.3% |
| divādi | 28,553 | 27,097 | 94.9% |
| svādi | 19,826 | 19,551 | 98.6% |
| tudādi | 27,735 | 26,760 | 96.5% |
| rudhādi | 7,218 | 7,034 | 97.5% |
| tanādi | 14,915 | 14,915 | 100.0% |
| kryādi | 15,604 | 15,175 | 97.3% |
| curādi | 11,677 | 11,524 | 98.7% |
| more than one gaṇa | 150,135 | 129,365 | 86.2% |

### By DCS time slot

| Slot (examples) | tokens | covered | % of mapped |
|---|---:|---:|---:|
| 1 Vedic (Saṃhitās, Brāhmaṇas, Sūtras) | 189,074 | 165,172 | 88.5% |
| 2 Epic and early classical (MBh, Manu) | 148,692 | 139,489 | 94.2% |
| 3 Classical (kāvya, Purāṇas, śāstra) | 87,979 | 84,319 | 96.4% |
| 4 Medieval | 80,811 | 77,992 | 97.2% |
| 5 Late | 29,496 | 27,789 | 94.8% |

### Change from vidyut 0.4.0

With the same script and mapping, vidyut 0.4.0 covers 493,590 tokens
(46,833 types). The WASM build covers 439 item types (1,307 tokens) that
0.4.0 does not, and 0.4.0 covers 31 types (53 tokens) that the WASM build
does not.

- New: leṬ (349 types, e.g. `asāni`, `karavāṇi`, `pracodayāt`), the augment
  after a gati (`āvirabhūt`, `antaradhīyata`), `procuḥ`, `praṇanāma`, and
  `hanyeta` for the karmaṇi vidhiliṄ of han (0.4.0 gave `vadhyeta`, reported
  in #233; the 6 DCS tokens of `vadhyeta` are now missed). The known `vi + as` ṣatva fix (8.3.87) also shows up:
  0.4.0 gave `pratisyāt`, the WASM build gives `pratiṣyāt`.
- Lost: ātmanepada of sthā after `anu`, `prati`, `adhi`, `pari`
  (`anutiṣṭhate`, `pratitiṣṭhate`, `adhitiṣṭhasva`, 23 types, 38 tokens). The current
  code allows 1.3.23 (prakāśanastheyākhyayoś ca) only for sthā without an
  upasarga. See "Open questions".

## Misses

Buckets are assigned in this order; each item lands in the first that fits.

| Bucket | tokens | types |
|---|---:|---:|
| a1 denominative lemma (not a dhatupatha root) | 2,288 | 808 |
| a2 intensive lemma not mapped | 434 | 184 |
| a3 desiderative lemma not mapped | 114 | 54 |
| a4 root not in vidyut's dhatupatha, or not mappable | 1,408 | 657 |
| b2 produced only in the other voice | 3,162 | 772 |
| b3 produced in another lakara or without the augment | 6,883 | 1,041 |
| b4 lemma does not split into its listed preverbs | 38 | 25 |
| b5 produced as a causative (DCS lists it under the base root) | 816 | 345 |
| c1 Vedic category (subjunctive, injunctive, aorist imperative or optative, pluperfect) | 5,223 | 1,723 |
| c2 attested mainly in Vedic texts | 9,539 | 3,006 |
| c3 attested mainly in epic texts | 3,654 | 1,398 |
| c4 pada that Pāṇini does not assign to this root | 5,169 | 1,842 |
| d remaining (classical texts, standard category) | 2,565 | 792 |

**(a) Root not mappable.** Denominatives (`mahīyate`, `gopāya` as a
nāmadhātu, `namasyāmi`) need a prātipadika, so they are out of scope here.
Unmapped intensives and desideratives are mostly Vedic yaṅluk stems
(`dīdihi`, `johavīmi`, `roravīti`). The rest of a4 is DCS lemma noise
(`samādis` for samādiś), causative stems vidyut does not form (`homay`,
`pavay`, `yavay`) and DCS encoding damage (U+FFDE in `atitṝ`).

**(b) DCS annotation or lemma split.** These are forms vidyut does produce,
under another tag.

- b3: `veda`, `viduḥ`, `vettha` (2,177 + 648 + 203 tokens) are tagged
  `Past` by DCS, but Pāṇini derives them in laṬ (3.4.83 vido laṭo vā), and
  vidyut does so. `āha` and `āhuḥ` (laṬ of brū by 3.4.84) are the same case.
  The rest are injunctives that DCS tags as indicative (`bhavat`, `dhāyi`)
  and plain tag errors.
- b2: passives without `Voice=Pass` (`dadṛśe` "was seen", `mucyeta`,
  `adṛśyata`) and epic ātmanepada used actively (`vakṣye` 238 tokens,
  `ūce`), which vidyut produces only as karmaṇi.
- b5: causative aorists that DCS files under the base root (`ajījanat`,
  `ajīgamam`) and augmentless causatives (`samarpayat`).

**(c) Vedic and epic usage.** Pāṇini covers chandas, so these are flagged
rather than dismissed, but most of them are licensed only by chandasi rules
that the default engine does not run, or not licensed at all:

- c1, c2: `kṛdhi` (6.4.102 śruśṛṇupṛkṛvṛbhyaś chandasi), `gahi`, `duhe`, `śaye` (7.1.41 lopas ta
  ātmanepadeṣu), `duhre` (7.1.8), `havāmahe`, `huve` (6.1.34), `dādhāra`,
  `vāvṛdhe` (6.1.7), `smasi`, `emasi` (7.1.46 idanto masi), `sunotana`,
  `kṛṇota` (7.1.45), `akaḥ`, `akar` (2.4.80), `sasūva` (7.4.74). Most of
  these forms appear verbatim in the Siddhāntakaumudī, many in its Vaidikī
  section. A run
  with `is_chandasi(true)` (not exposed by the WASM or Python bindings
  today) would be the natural follow-up.
- c3, c4: epic "ārṣa" usage. Pada switching is the largest group
  (`labhet` 276, `gaccheta` 115, `trāhi` 69, `krīḍate` 53, `śṛṇuṣva` 214,
  `apaghnate`); thematic presents of athematic roots (`lihet`, `svapet`,
  `hunet`, `dadmi`, `gṛhṇa`, `bandha`, `hana`); and iṭ or stem changes
  (`nayiṣyati`, `bhajiṣyati`, `adadat`).

**(d) Remaining classical items.** After manual review of the top 300
types, these are the same epic or medieval irregularities as c3 and c4
(the pada heuristic misses some of them), DCS noise (`tatra` tagged as a
verb, `dadhati` tagged singular) or spelling (`ujhati`). Several near misses
turned out to be correct in vidyut once checked against the
Siddhāntakaumudī:

- `visismiye` (DCS) vs. vidyut `visiṣmiye`: SK 948 gives सिष्मिये.
- `āsva` vs. vidyut `āssva`: SK 1021 (आस उपवेशने) gives आस्स्व.
- `pariṇāmayati`, `upanāmayati` vs. vidyut `pariṇamayati`: on the gaṇasūtra
  jvalahvalahmalanamām anupasargād vā the SK says उपसृष्टे तु नित्यं
  मित्त्वम्, and explains `unnāmayati` as a denominative.
- `prajvalayati`: correct in vidyut when the ghaṭādi antargaṇa is passed.
- `upakramet`, `ācamet` vs. `upakrāmet`, `ācāmet` (7.3.76, 7.3.75): DCS
  spelling or epic.
- `anustauti`, `abhyasthām` vs. vidyut `anuṣṭauti`, `abhyaṣṭhām`: ṣatva by
  8.3.65 and 8.3.63. `abhyasthām` is the chandas option of 8.3.119
  (nivyabhibhyo 'ḍvyavāye vā chandasi); `anustauti` (5 tokens, Vedic) is
  not licensed by either.

## Verified candidate bug

### 8.3.102 nisas tapatāv anāsevane is not implemented

vidyut gives `nistapati` for `nis + tap`. The sūtra makes the s of nis
retroflex before tap when the action is not repeated:

> SK 2403 (8.3.102) निसस्तपतावनासेवने । षः स्यात् । आसेवनं पौनः पुन्यं
> ... । निष्टपति ।

- DCS: 21 tokens over 9 types, all with ṣṭ: `niṣṭapati` (12, e.g.
  BhārŚS 1.12), `niṣṭapataḥ` (3), `niṣṭapāmi`, `niṣṭapet`, `niṣṭaptā` (2
  each). The DCS has no `nistap-` tiṅanta at all.
- vidyut (WASM build and 0.4.0): `nistapati`, `nistapet`, `nistaptā`,
  `nistapāmi` for every tap entry (01.1140, 04.0054, 10.0350) with `nis` or
  `nir`.
- `src/tripadi/pada_8_3.rs` implements 8.3.101 but has no 8.3.102. There is
  no upstream issue for it.
- Confidence: high. vidyut has no way to model āsevana, so the fix is
  probably to apply ṣatva by default, or optionally.

Draft issue: `scripts/dcs_tinanta_issue_drafts.md`.

## Open questions (not filed)

These look odd against the corpus but the sources at hand do not settle
them, so no issue was drafted.

1. **1.3.22 with an upasarga in between.** vidyut makes sam + ud + sthā
   ātmanepada (`samuttiṣṭhate`, `samuttasthe`) because `atmanepada.rs`
   checks for `sam` anywhere before the dhatu. The corpus has only
   parasmaipada: `samuttasthau` (26 tokens, epic and classical),
   `samuttasthuḥ` (18), `samuttiṣṭhanti` (8). Whether 1.3.22 needs sam to
   be next to sthā is a question for a grammarian; the SK commentary on
   1.3.22 and 1.3.24 does not discuss it.
2. **7.4.95 for bhvādi prath.** vidyut gives `apaprathat` for curādi
   `praTa~` but `apipraTat` for the causative of bhvādi `praTa~\`
   (ghaṭādi). The sūtra names prath without a gaṇa; the SK quotes it under
   the curādi root (1554). DCS has 2 tokens of `apaprathat`.
3. **1.3.23 after an upasarga.** See "Change from vidyut 0.4.0". The
   sūtra is semantic and has no upasarga condition, but its SK examples
   have no upasarga either.

## Limits

- The engine is a prebuilt WASM, not this branch; rerun with a fresh
  `make wasm_release` before relying on the numbers.
- Lemma mapping is heuristic. It can overcount (a homophonous form of
  another root counts as covered; the regression TSV says which dhatu
  matched) and undercount (misses in a4 and b4).
- The c buckets use DCS time slots and an ending-based pada heuristic, so
  they are rough. Every number here is per DCS item, not per sentence
  meaning.
