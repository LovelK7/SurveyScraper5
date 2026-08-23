# OSZ v10 — završna provjera predloška (2026-08-23)

Predložak: [templates/Zapisnik_OSZ_v10.docx](../templates/Zapisnik_OSZ_v10.docx),
stanje od 16:32 — **završna varijanta v10**. Strojni izlaz:
[conformance-v10.2.txt](conformance-v10.2.txt). Ranije provjere:
[v10.1](audit-v10.1.md), [v10.0](audit-v10.0.md).

**Stanje kontrola:** 81 content control — 66 kvačica u 9 grupa, 15 tekstualnih.

## Riješeno u ovoj varijanti

| Nalaz iz v10.1 | Stanje |
|---|---|
| Ćelija za datum stisnuta na 250 twipsa, potpis pada na 5. stranicu | ✅ širina 2402; mockup je opet **4 stranice** |
| Snijeg/led kao jedna kvačica | ✅ razdvojeno na `prisutnost snijega` i `prisutnost leda` |
| `jama s špiljskim ulazom` — neprovjeren oblik | ✅ potvrđeno prema CroSpeleu: `jama sa špiljskim ulazom` (uz `špilja s jamskim ulazom`) |
| `Povijesni podaci` bez zadane veličine fonta | ✅ Arial 10 pt |

Trajnost pojave (stalno / sezonski) ostaje u tekstu Mikroklimatskog polja —
odluka 2026-08-23: u praksi se bilježi stalna pojava, a jednokratni zimski
snijeg nije podatak vrijedan zapisa.

## Vokabulari — završno stanje

| Grupa | Rezultat |
|---|---|
| Podrijetlo imena (6) | ✅ potpuno |
| Stanje ulaza (10) | ✅ potpuno |
| Hidrološka karakteristika (8) | ✅ potpuno |
| Hidrogeološka funkcija (10) | ✅ potpuno |
| Perspektiva daljnjeg istraživanja (12) | ✅ potpuno, znak za znak |
| Vrsta objekta (8) | ✅ svi oblici potvrđeni prema CroSpeleu (popis dropdowna nije iscrpno poznat) |
| Prirodne opasnosti (8) | ⚠ 9/13 CroSpeleo labela |
| Antropogene opasnosti i utjecaj (2) | ⚠ svjestan podskup |
| Prisutnost snijega / leda (2) | ⚠ prisutnost da, trajnost iz teksta |

Preostalo nepokriveno u opasnostima: `opasni otpad` (57 objekata u registru),
`minski sumnjivo područje u kojem je objekt` (19), `električni vodovi` (3).
`otpad u objektu` (568 — najčešća oznaka u registru) pokriva se kvačicom
`onečišćenje otpadom`, ali samo ako fetcher napravi to preslikavanje.

## Pravila preslikavanja za fetcher

| Kvačica u zapisniku | CroSpeleo |
|---|---|
| Perspektiva (12) | Opažanja → Perspektiva daljnjeg istraživanja, 1:1 |
| Prirodne opasnosti (8) | Opažanja → Opasnosti, 1:1 |
| `onečišćenje otpadom` | Antropogene aktivnosti #15 **+** Opasnosti `otpad u objektu` |
| `minsko-eksplozivna sredstva` | Opasnosti `minsko-eksplozivna sredstva` **+** Klasifikacija onečišćenja `minsko-eksplozivna sredstva` |
| `prisutnost snijega` | `snijeg - da`; ako tekst nosi `stalno` → `snijeg - stalno`, ako `sezonski`/`povremeno` → `snijeg - privremeno` |
| `prisutnost leda` | isto pravilo za `led - *` |
| nijedna od te dvije, a Mikroklimatski popunjen | `snijeg - ne` + `led - ne` (zamjenjuje regionalnu inferenciju `infer_snow_ice_negative`) |

Ostali zadaci: **Otok** izvesti iz `Lokalitet` (gazetteer od ~125 000 mjesta
postoji u `crospeleo-automation`), `Sporedni ulazi` parsirati kao slobodan tekst,
`Crtali` → Nacrt *Autori* (danas iz SB stupca), `Izvor koordinata` normalizirati
na 8 vrijednosti (`GPS`, `HOK 1:5000`, `LIDAR`, `TK 1:100000`, `TK 1:25000`,
`geodetski određene`, `karta nepoznatog mjerila`, `referenca`).

I dalje vrijedi glavni nalaz: **sadržaj content controlsa današnji parser ne
vidi** — čitanje mora ići kroz `w:sdtContent//w:t`, uz preskakanje kontrola s
`w:showingPlcHdr`, a stanje kvačice kroz `w14:checkbox/w14:checked`.

Naslovi koje `OSZParser._canonical_key` ne prepoznaje (27 od 50 prolazi):
`Prirodne opasnosti`, `Antropogene opasnosti i utjecaj`, `Crtali`, `Mjerili`,
`Nacrt uredio`, `Sporedni ulazi`, `Stanje ulaza`, `Širina ulaza`,
`Visina/duljina ulaza`, `Duljina (m)`, `Izvor kote ulaza`, `Broj ulaza`,
`Koordinate ulaza (HTRS96/TM)`, `Datum ili razdoblje istraživanja`,
`Istražile udruge`, `Katastarski broj`, `Broj pločice`, `Županija`,
`Grad/općina` + naslovi sekcija. Uz `w:tag` na kontrolama ovo prestaje biti
problem.

## Sitnice koje su ostale

- `Literatura` i `Napomene` još nemaju zadanu veličinu fonta → ispisuju se 11 pt
  umjesto Arial 10 pt (vidljivo na 4. stranici mockupa).
- Nijedna kontrola nema `w:tag`.
- Bez strukturiranog polja i dalje: **Izvor koordinata**, **Strujanje zraka**
  (u objektu / na ulazu + smjer), **Mjerne točke** kao brojevi, **metoda i
  vrijednost CO₂**, te *Stanje otpada* / *Zapremnina otpada* /
  *Recentni ljudski ostaci*. Sve to ostaje na heuristikama iz slobodnog teksta.

## Mockup

[v10.2_primjer_811.docx](../mockups/v10.2_primjer_811.docx) /
[.pdf](../mockups/v10.2_primjer_811.pdf) — SUE 811 *Piccolo Bertarelli*,
4 stranice. Kvačice: `smišljeno prema toponimu`, `zatvoren granjem/balvanima`,
`špilja`, `povremeni tok`, `povremeni ponor`, `potrebno proširivanje`,
`nastavlja se`, `mogućnost brzog potapanja kanala`, `onečišćenje otpadom`;
snijeg i led nisu označeni jer ih objekt nema. Mikroklimatska mjerenja,
zapremnina otpada i stanje ulaza su izmišljeni — dokument iz 2025. ih nije nosio.
