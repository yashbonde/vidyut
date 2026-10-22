# `maghavan`: 6.4.128 *maghavā bahulam* not implemented

**Draft, not posted.**

## Summary

`Pratipadika.basic("maGavan")` gives only the an-stem paradigm (`maGavA`,
`maGavAnO`, `maGonA`, `maGavasu`). 6.4.128 optionally replaces the end of
maghavan with tṛ, giving the ugit stem `maghavat`: `maGavAn`, `maGavantO`,
`maGavatA`, `maGavatsu`. Both paradigms should be produced. Seen in the
2026-10-17 WASM build and in vidyut 0.4.0.

## Reproduce

```python
from vidyut.prakriya import Vyakarana, Pada, Pratipadika, Linga, Vibhakti, Vacana

v = Vyakarana()
for vibhakti, vacana in [(Vibhakti.Prathama, Vacana.Eka), (Vibhakti.Trtiya, Vacana.Eka),
                         (Vibhakti.Saptami, Vacana.Bahu)]:
    pada = Pada.Subanta(pratipadika=Pratipadika.basic("maGavan"), linga=Linga.Pum,
                        vibhakti=vibhakti, vacana=vacana)
    print(vibhakti, vacana, sorted({p.text for p in v.derive(pada)}))
# expected: [maGavA, maGavAn], [maGavatA, maGonA], [maGavatsu, maGavasu]
```

## Grammar

SK 360, 6.4.128 *maghavā bahulam*: "मघवन्शब्दस्य वा तृ इत्यन्तादेशः स्यात् ।
ऋ इत्", then SK 361 (7.1.70, num): "उपधादीर्घः । मघवान्". The existing test
`sutra_6_4_133` checks only the an-stem forms (`maGonaH`, `maGonA`).

## Corpus evidence (DCS, Oliver Hellwig, CC BY 4.0)

96 tokens: `maghavān` 61 (AB 5.21, sent 664360), `maghavatā` 21 (BhāgPur
4.20, sent 94412), `maghavatsu` 10 (ṚV 1.64), `maghavati` 2, `maghavate`,
`maghavato`. Most are epic and puranic (67).
