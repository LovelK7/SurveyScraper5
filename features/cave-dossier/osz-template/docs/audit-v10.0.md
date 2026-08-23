# OSZ predložak, varijanta v10.0 — provjera (2026-08-23, 14:17)

> Povijesno. Završna provjera: [audit-v10.2.md](audit-v10.2.md).

Provjera stanja `!Zapisnik_OSZ_v10.docx` (verzija od 2026-08-23, 14:17) protiv:
`services/osz_parser.py`, `services/readiness_validator.py` (Tablica 2),
`docs/ui_reference/**/fields_inventory.md` i
`docs/protocol_katastar_speleoloskih_objekata_RH_v6.md` u read-only repozitoriju
`../crospeleo-automation`. Prateći dokument s tekstovima placeholdera:
[placeholders.md](placeholders.md).

**Stanje kontrola:** 56 content controlsa — 42 checkboxa (5 grupa) i 14
plain-text kontrola.

---

## 1. Što je sada pokriveno

Sva **obvezna polja** iz `_REQUIRED_*_FIELDS` u `readiness_validator.py` imaju
svoje mjesto u zapisniku:

| Obvezno polje (Tablica 2) | Gdje je u predlošku |
|---|---|
| Ime objekta | `IME OBJEKTA` |
| Podrijetlo imena | checkbox grupa, 6 opcija |
| Položaj i pristup objektu | kontrola s placeholderom |
| Najbliže mjesto / Lokalitet | zasebna polja |
| Vrsta objekta | checkbox grupa, 8 opcija |
| Hidrogeološka funkcija | checkbox grupa, 10 opcija |
| Hidrološka karakteristika | checkbox grupa, 8 opcija |
| Osnovni opis s tehničkim podacima | kontrola s placeholderom |
| Izvor koordinata | slobodan tekst |
| Georef zapis | E / N koordinate |
| Interni katastarski broj | `Katastarski broj` |
| Zapisničar | potpisni redak |
| Perspektiva daljnjeg istraživanja | kontrola s placeholderom |
| Dubina, Horizontalna duljina | numerička rešetka |
| Širina ulaza, Visina/duljina ulaza | redak ulaza |
| Članovi ekipe | tri retka |

**Checkbox grupe se poklapaju s CroSpeleo vokabularom label-za-label** (jedina
razlika je opisana u §3):

| Grupa | Predložak | CroSpeleo | Status |
|---|---|---|---|
| Podrijetlo imena | 6 | 6 | ✅ |
| Stanje ulaza | 10 | 10 | ✅ |
| Hidrološka karakteristika | 8 | 8 | ✅ (bez `sniježnica/ledenica`, koju CroSpeleo odbija) |
| Hidrogeološka funkcija | 10 | 10 | ✅ (uklj. `anhijalini objekt`, `morski objekt`) |
| Vrsta objekta | 8 | dropdown | ⚠ vidi §3 |

Popravljeno u odnosu na raniju verziju: `Prirodne opasnosti` → `Opasnosti`
(parser prepoznaje samo `opasnosti`), dodan `Nacrt uredio` (polje koje
`TODO` traži godinama), `Širina ulaza` / `Visina/duljina ulaza` umjesto
`Dimenzije glavnog ulaza (m × m)` — to je upravo par koji CroSpeleo traži i
ukida dvostupanjsku heuristiku iz `RULES.md` §4.

---

## 2. Dvije greške u samim kontrolama

**(a) Nijedna od 14 tekstualnih kontrola ne dopušta više odlomaka.** Sve su
zapisane kao `<w:text/>` bez `multiLine`. Word tada blokira Enter unutar
kontrole — a placeholderi za Mikroklimatski, Zagađenost i Opasnosti su pisani
kao višeredni popisi. Provjereno: umetanje drugog `w:p` u takvu kontrolu Word
odbija s „The file appears to be corrupted”. Popravak: Developer → Properties →
**Allow carriage returns (multiple paragraphs)** na svakoj narativnoj kontroli.

**(b) Tri kontrole nemaju zadanu veličinu fonta.** `Povijesni podaci`,
`Literatura` i `Napomene` nemaju `w:sz` u `sdtPr`, pa tekst pada na
dokumentni default (11 pt) dok su ostala polja Arial 10 pt. Vidi se na
stranicama 3–4 priloženog mockupa. Popravak: postaviti Arial 10 pt kao i drugdje.

Uz to, kontrole su miješane: 9 ih je na razini ćelije (`w:sdt` omata `w:tc`), a
5 na razini odlomka (Arheološki, Opasnosti, Zagađenost, Povijesni, Literatura).
Oboje radi; ujednačavanje na razinu ćelije bi pojednostavilo budući fetcher.

---

## 3. Što je i dalje slobodan tekst, a CroSpeleo traži vokabular

Ovo je ostatak liste iz `TODO` § „OSZ template overhaul”. Nije greška — ali dok
ovih grupa nema u zapisniku, heuristike ostaju u igri sa svojim poznatim
stopama pogreške.

| CroSpeleo kontrola | Opcija | Danas u predlošku | Posljedica |
|---|---|---|---|
| **Perspektiva daljnjeg istraživanja** | 12 checkboxa | slobodan tekst | `map_perspektiva` prepoznaje 4 od 12 opcija; polje je **obvezno** |
| **Opasnosti** | 13 checkboxa | slobodan tekst | `map_opasnosti`, micro-F1 0,41 |
| **Antropogene aktivnosti / Korištenje objekta / Klasifikacija onečišćenja** | 15 + 2 + 13 | jedno polje slobodnog teksta | `map_zagadenost_ljudski`, micro-F1 0,36–0,48 |
| **Stanje otpada / Zapremnina otpada / Recentni ljudski ostaci** | 3 / 4 / 2 | isto polje | 65 % / 76 % / 93 % točnost, 0 TP na ostacima |
| **Prisutnost snijega i leda** | 8 (2×4) | nema polja | `map_snijeg_led` + regionalna inferencija |
| **Strujanje zraka u objektu / na ulazu + smjer** | 5 + 5 + 4 + 4 | proza u Mikroklimatskom | `map_strujanje_zraka`, detekcija → uvijek `povremeno` |
| **Mjerne točke** (temp. zraka, vlažnost, temp. vode, temp. sedimenta) | numerički | proza | regex ekstrakcija iz teksta |
| **Metoda mjerenja CO₂ / vrijednost / instrument** | 2 + tekst + tekst | proza | ne popunjava se |
| **Izvor koordinata** | 8 vrijednosti | slobodan tekst | `GPS`, `HOK 1:5000`, `LIDAR`, `TK 1:100000`, `TK 1:25000`, `geodetski određene`, `karta nepoznatog mjerila`, `referenca`; nepoznata vrijednost tiho pada na `GPS` |

**Vrsta objekta — `sa` vs `s`:** predložak ima `jama sa špiljskim ulazom`.
CroSpeleo koristi kratki prijedlog i za taj oblik; `normalize_object_type`
danas ima ručnu zakrpu samo za `špilja sa jamskim ulazom` →
`Špilja s jamskim ulazom`. Isti popravak treba i za oblik s jamom (`TODO`
§ „OSZ template fix: replace 'sa' with 's'”).

> Napomena o dokumentaciji u referentnom repou: `RULES.md` §2 navodi stari
> popis opcija za Izvor koordinata (`TK 1:5000`, `topografska karta`,
> `digitalna ortofoto karta`); mjerodavan je `_COORD_SOURCE_OPTIONS` u
> `osz_parser.py`, koji se slaže s `fields_inventory.md`.

---

## 4. Polja koja protokol traži, a predložak ih nema

| Polje | Oznaka u protokolu | Bilješka |
|---|---|---|
| **Otok** | `**` | Nema ga; obvezno kad objekt jest na otoku |
| **Sporedni ulazi** | `**$` | `Broj ulaza` postoji, ali nema bloka za podatke drugog ulaza (koordinate, dimenzije, stanje) — protokol traži sve iste podatke i za sporedne ulaze |
| **Stanje minsko-eksplozivnih sredstava** | `**` | Nema polja |
| **Nacrt — Autori** | `*#` | Predložak ima `Topografski snimili`, `Mjerili`, `Nacrt uredio`, ali ne i `Crtali`; SpeleoFlow autore nacrta danas uzima iz SB stupca, ne iz OSZ-a |
| **Nacrt / Fotografija — Izradile udruge** | `**` | Nema polja (može se izvesti iz `Istražile udruge`) |

Županija, Grad/općina i Kota ulaza CroSpeleo generira automatski iz koordinata
(protokol §6), pa su u zapisniku korisni samo za vlastitu arhivu.

---

## 5. Naslovi koje parser danas ne prepoznaje

Provjereno pozivom `OSZParser._canonical_key` na svih 45 naslova iz predloška:
29 prolazi, 16 ne. Za budući fetcher — ili dopuniti `_BASE_FIELD_SPECS`, ili
(bolje) staviti `w:tag` na svaku kontrolu:

```
Katastarski broj              Duljina (m)                  ← "Dubina (m)" prolazi, "Duljina (m)" ne
Broj pločice                  Datum ili razdoblje istraživanja
Županija                      Istražile udruge
Grad/općina                   Topografski snimili
Koordinate ulaza (HTRS96/TM)  Mjerili
Izvor kote ulaza              Nacrt uredio
Broj ulaza                    Stanje ulaza
Širina ulaza                  Visina/duljina ulaza
```

Uz to i dalje vrijedi nalaz iz [placeholders.md](placeholders.md):
**sadržaj content controlsa je današnjem parseru potpuno nevidljiv**
(python-docx ne čita `w:sdt`), pa fetcher treba čitati XML izravno i preskakati
kontrole s `w:showingPlcHdr`.

---

## 6. Mockup

[v10.0_primjer_811.docx](../mockups/v10.0_primjer_811.docx) /
[.pdf](../mockups/v10.0_primjer_811.pdf) — predložak popunjen podacima objekta
SUE 811 *Piccolo Bertarelli* iz zapisnika 2025. Mikroklimatska mjerenja,
zapremnina otpada, stanje ulaza i podrijetlo imena su **izmišljeni**, jer ih
dokument iz 2025. nije nosio — služe samo za provjeru izgleda. Napomene nose
oznaku „OGLEDNI PRIMJER”.

Generator: [../tools/make_mockup.py](../tools/make_mockup.py)
(`python make_mockup.py <predložak.docx> <izlaz.docx>`). Skripta popunjava
kontrole, kvačice i obične ćelije; korisna je i kao referentna implementacija
za pisanje OSZ-a iz `cave_dossier` builder-a.

Što se vidi na ispisu (4 stranice):

- Sve tri narativne stranice stanu bez prelijevanja; ćelije imaju fiksnu visinu
  pa kraći tekst ostavlja prazninu (Biospeleološki, Arheološki).
- Kvačice se ispisuju kao ☑ (Wingdings 2) i čitljive su u PDF-u.
- Razlika u veličini fonta iz §2(b) jasno se vidi na Povijesnim podacima,
  Literaturi i Napomenama.
- Okvir za isječak karte ostaje prazan — u stvarnom zapisniku tu ide slika.
