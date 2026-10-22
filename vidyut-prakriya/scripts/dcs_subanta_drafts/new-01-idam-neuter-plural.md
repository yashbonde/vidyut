# `idam` neuter nominative/accusative plural: `idAni` instead of `imAni`

**Draft, not posted.** Found by `scripts/check_dcs_subanta_coverage.py`
(see `scripts/dcs_subanta_report.md`).

## Summary

The neuter plural of `idam` comes out as `idAni`. The expected form is
`imAni` (इमानि): 7.2.109 *daś ca* replaces the d of idam with m before any
case ending, and the neuter dual already shows it (`ime`).

## Reproduce

```python
from vidyut.prakriya import Vyakarana, Pada, Pratipadika, Linga, Vibhakti, Vacana

v = Vyakarana()
for vibhakti in (Vibhakti.Prathama, Vibhakti.Dvitiya):
    for vacana in (Vacana.Dvi, Vacana.Bahu):
        pada = Pada.Subanta(pratipadika=Pratipadika.basic("idam"), linga=Linga.Napumsaka,
                            vibhakti=vibhakti, vacana=vacana)
        print(vibhakti, vacana, sorted({p.text for p in v.derive(pada)}))
```

| cell | vidyut | expected |
|---|---|---|
| nom./acc. dual | `ime` | `ime` |
| nom./acc. plural | `idAni` | `imAni` |

Seen with the WASM build served by the vidyut demo (2026-10-17) and with
vidyut 0.4.0 from PyPI.

## Grammar

- 7.2.102 *tyadādīnām aḥ* gives `ida`, 7.1.20 gives `Si`, 7.1.72 adds num.
- 7.2.109 *daś ca*: SK 345 "इदमो दस्य मः स्याद्विभक्तौ", with `imau`, `ime`.
  `Si` replaces jas/Sas and is a vibhakti by sthanivadbhava, so the rule
  applies here too. Compare the neuter pronouns in SK: "ते । तानि ... एते ।
  एतानि".
- In `angasya/subanta.rs` the 7.2.109 branch is guarded by
  `anga.has_u("idam") && anga.has_antya('a')`; after num is added for the
  plural, the anga probably no longer ends in `a`, so the branch is skipped.
  Not confirmed with a debugger.

## Corpus evidence (DCS, Oliver Hellwig, CC BY 4.0)

- `imāni` 317 tokens as neuter nominative or accusative plural, in classical,
  epic, BHS and Vedic texts (for example Rām Bā 71, sent 115795; Kir 8,
  sent 358386; AĀ 1.3.4, sent 765183), plus 157 tokens of Vedic `imā`.
- `idāni` is not attested.
