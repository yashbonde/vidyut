# añc + kvin stems: weak cases lose 6.3.138, no feminine ṅīp, 6.3.93 missing

**Draft, not posted.**

## Summary

For `Pratipadika.krdanta(Dhatu.mula("ancu~", Gana.Bhvadi).with_prefixes([...]), Krt.kvin)`:

| prefix | cell | vidyut | expected | rule |
|---|---|---|---|---|
| pra | acc. pl. / instr. sg. | `pracaH`, `pracA` | `prAcaH`, `prAcA` | 6.4.138, 6.3.138 |
| prati | acc. pl. / instr. sg. | `praticaH`, `praticA` | `pratIcaH`, `pratIcA` | 6.4.138, 6.3.138 |
| ava | acc. pl. | `avacaH` | `avAcaH` | 6.4.138, 6.3.138 |
| ud | acc. pl. / instr. sg. | `uccaH`, `uccA` | `udIcaH`, `udIcA` | 6.4.139 |
| sam | nom. sg. / acc. pl. | `samaN`, `saMcaH` | `samyaN`, `samIcaH` | 6.3.93, 6.3.138 |
| pra | feminine nom. sg. | `prAN` | `prAcI` | 4.1.6 |
| pra | neuter nom. du. | `pracI` | `prAcI` | 6.3.138 |

The strong cases are right (`prAN`, `prAYcO`, `prAYcaH`, `pratyaN`).

With vidyut 0.4.0 from PyPI the pra weak cases were right (`prAcaH`, `prAcA`),
so that part looks like a regression; `pratyacaH` and the feminine `prAN`
were already wrong there. `sutra_6_3_138` in `kashika_6_3.rs` tests only the
upapada stems `daDyac` and `maDvac`, built with `require`.

## Reproduce

```python
from vidyut.prakriya import Vyakarana, Pada, Pratipadika, Dhatu, Gana, Krt, Linga, Vibhakti, Vacana

v = Vyakarana()
anc = Dhatu.mula("ancu~", Gana.Bhvadi)
for pre in ("pra", "prati", "ava", "ud", "sam"):
    stem = Pratipadika.krdanta(anc.with_prefixes([pre]), Krt.kvin)
    for linga, vibhakti, vacana in [(Linga.Pum, Vibhakti.Dvitiya, Vacana.Bahu),
                                    (Linga.Pum, Vibhakti.Trtiya, Vacana.Eka),
                                    (Linga.Stri, Vibhakti.Prathama, Vacana.Eka)]:
        pada = Pada.Subanta(pratipadika=stem, linga=linga, vibhakti=vibhakti, vacana=vacana)
        print(pre, linga, vibhakti, vacana, sorted({p.text for p in v.derive(pada)}))
```

## Grammar (Siddhantakaumudi, SARIT edition)

- SK 416 to 417, 6.4.138 *acaḥ* and 6.3.138 *cau*: "प्राचः । प्राचा ...
  प्रतीचः । प्रतीचा".
- SK 420, 6.4.139 *uda īt*: "उदीचः । उदीचा".
- SK 421, 6.3.93 *samaḥ sami*: "सम्यङ् । सम्यञ्चौ ... समीचः । समीचा".
- SK 455, 4.1.6 *ugitaś ca*, on dhatus: "अञ्चतेस्तु स्यादेव । प्राची । प्रतीची".

`tiras` + añc (6.3.94, `tiryaN`) was not checked, because the WASM kṛdanta
input has no upapada field.

## Corpus evidence (DCS, Oliver Hellwig, CC BY 4.0)

1,479 tokens, most from Vedic prose but all of them the classical forms:
feminines `prācī`, `prācīm`, `prācyām` (476), `pratīcī` (253), `udīcī` (252),
`samīcī` (53), `avācī`, `anvācī`; weak cases `prācaḥ` (AB 6.22, sent 664736),
`udīcaḥ` (AB 6.22, sent 664737), `pratīcaḥ`, 226 tokens; strong and neuter
forms of `tiryañc` and `samyañc` (`tiryak`, `samyak`), 113 tokens.
