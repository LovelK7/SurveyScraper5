# OSZ predložak, varijanta v10.1 — provjera (2026-08-23, 16:05)

> Povijesno. Završna provjera: [audit-v10.2.md](audit-v10.2.md).

Predložak: [templates/Zapisnik_OSZ_v10.docx](../templates/Zapisnik_OSZ_v10.docx),
stanje od 16:05. Verzija samog zapisnika ostaje **v10** — oznake v10.0 / v10.1
koriste se samo za razlikovanje varijanti tijekom rada. Strojni izlaz:
[conformance-v10.1.txt](conformance-v10.1.txt) — `python tools/check_conformance.py`.
Prethodna provjera: [audit-v10.0.md](audit-v10.0.md).

**Stanje kontrola:** 80 content controlsa — 65 kvačica u 8 grupa i 15 tekstualnih
kontrola (bilo: 42 + 14).

## Što je riješeno u odnosu na v10.0

| Nalaz iz audita v10.0 | Stanje |
|---|---|
| Kontrole ne dopuštaju Enter | ✅ `multiLine` uključen na svih 12 narativnih kontrola |
| Perspektiva samo slobodan tekst | ✅ svih 12 CroSpeleo opcija kao kvačice |
| Opasnosti samo slobodan tekst | ✅ 8 prirodnih opasnosti kao kvačice |
| Zagađenost samo slobodan tekst | ✅ dvije najvažnije kvačice (svjesno sužen opseg) |
| Nema polja za snijeg/led | ⚠ dodana jedna kvačica — vidi §3 |
| Nema mjesta za sporedne ulaze | ✅ polje `Sporedni ulazi` na prvoj stranici |
| `Crtali` ne postoji (bilo `Topografski snimili`) | ✅ preimenovano |
| Otok | ✅ odluka: izvodi se iz `Lokalitet` (zadatak za fetcher, §5) |

## 1. Vokabulari kvačica

| Grupa | Rezultat |
|---|---|
| Podrijetlo imena (6) | ✅ poklapa se u cijelosti |
| Stanje ulaza (10) | ✅ |
| Hidrološka karakteristika (8) | ✅ |
| Hidrogeološka funkcija (10) | ✅ |
| **Perspektiva daljnjeg istraživanja (12)** | ✅ svih 12 CroSpeleo labela, znak za znak |
| Prirodne opasnosti (8) | ⚠ 9/13 CroSpeleo labela — vidi dolje |
| Antropogene opasnosti i utjecaj (2) | ⚠ svjestan podskup — vidi dolje |
| Vrsta objekta (8) | ⚠ CroSpeleo dropdown; popis opcija nije nigdje u referentnoj dokumentaciji |

**Prirodne opasnosti — što od CroSpeleo popisa nedostaje:**

- `otpad u objektu` — pokriveno kvačicom `onečišćenje otpadom` iz antropogene
  grupe, ali **fetcher to mora eksplicitno preslikati**; u registru je to
  najčešća oznaka opasnosti uopće (568 objekata).
- `opasni otpad` (57 objekata) — nema kvačice ni u jednoj grupi; ostaje samo
  slobodan tekst.
- `minski sumnjivo područje u kojem je objekt` (19 objekata) — nije isto što i
  `minsko-eksplozivna sredstva` (područje vs. nalaz); trenutno nepokriveno.
- `električni vodovi` (3 objekta) — zanemarivo, može ostati u tekstu.

**Antropogene:** 1 od 15 labela grupe *Antropogene aktivnosti*. Posljedica je da
CroSpeleo kontrole *Antropogene aktivnosti* (14 preostalih labela),
*Korištenje objekta* (2), *Klasifikacija onečišćenja* (13) i tri padajuća
izbornika (*Stanje otpada*, *Zapremnina otpada*, *Recentni ljudski ostaci*)
ostaju bez strukturiranog izvora — puni ih heuristika `map_zagadenost_ljudski`
(micro-F1 0,36–0,48) iz slobodnog teksta. To je prihvatljiv kompromis dok
placeholder traži količinu u m³, stanje čišćenja i način posjećivanja, jer
upravo te tri stavke heuristika najgore pogađa.

**Vrsta objekta:** predložak sada piše `jama s špiljskim ulazom`. Kanonski oblik
za drugu opciju znamo (`Špilja s jamskim ulazom`, iz `_OBJECT_TYPE_FIXES`), ali
za jamsku varijantu nemamo potvrđen CroSpeleo string. Prije zaključavanja
predloška to treba pročitati s live dropdowna — pogrešan oblik znači da odabir
tiho ne prođe (`Element not found`).

## 2. Nova greška u izgledu — polje za datum

Redak potpisa: širina ćelije za datum pala je s **1851 na 250 twipsa** (~4 mm),
a labela `Zapisničar:` narasla s 2126 na 3727. Datum se zato lomi okomito
(`1 7 . 0 5 . 2 0 2 5 .`) i gura potpisni redak na **petu stranicu**.

Provjereno: vraćanjem širina na 1851 / 2126 mockup se vraća na 4 stranice.
Vidi zadnje dvije stranice [mockupa](../mockups/v10.1_primjer_811.pdf).

## 3. Snijeg i led — jedna kvačica za matricu od 8

CroSpeleo očekuje 2×4 matricu `{snijeg, led} × {da, ne, privremeno, stalno}`.
Jedna kvačica `prisutnost snijega i leda` ne kaže **što** je prisutno ni
**koliko traje**, a neoznačena kvačica ne znači `ne` (CroSpeleo razlikuje
izričito „ne” od praznog).

Prijedlog uz minimalno mjesta na papiru — dvije kvačice `snijeg` i `led`, a
trajnost iz teksta. Pravilo za fetcher onda može biti:

- kvačica označena → `<snijeg|led> - da`, pa ako tekst nosi `stalno`/`povremeno`
  nadogradi na `- stalno` / `- privremeno` (isto što `map_snijeg_led` već radi);
- kvačica neoznačena, a Mikroklimatski popunjen → `snijeg - ne`, `led - ne`
  (danas se to pogađa regionalnom inferencijom `infer_snow_ice_negative`);
- Mikroklimatski prazan → ne diraj polje.

Ako ostane jedna kvačica, fetcher može popuniti samo `snijeg - da` + `led - da`
zajedno, što je netočno u većini slučajeva.

## 4. Higijena kontrola

- `multiLine` nedostaje na 3 kontrole: dvije koordinatne (ispravno — jedan redak)
  i **`Sporedni ulazi`** (tu je vjerojatno svejedno jer placeholder upućuje na
  Napomene).
- Bez zadane veličine fonta i dalje: `Povijesni podaci`, `Literatura`,
  `Napomene` → ispisuju se 11 pt umjesto Arial 10 pt (vidljivo u mockupu).
- Nijedna od 15 kontrola nema `w:tag`. Preporuka iz
  [placeholders.md](placeholders.md) §D i dalje stoji: tag = kanonsko ime polja
  u parseru.

## 5. Što fetcher mora znati (za kasnije)

Mapiranje kvačica → CroSpeleo kontrole, uključujući netrivijalne slučajeve:

| Kvačica u zapisniku | CroSpeleo |
|---|---|
| Perspektiva (12) | Opažanja → Karakteristike objekta → Perspektiva, 1:1 |
| Prirodne opasnosti (8) | Opažanja → Opasnosti, 1:1 |
| `onečišćenje otpadom` | Antropogene aktivnosti #15 **+** Opasnosti `otpad u objektu` |
| `minsko-eksplozivna sredstva` | Opasnosti `minsko-eksplozivna sredstva` **+** Klasifikacija onečišćenja `minsko-eksplozivna sredstva` |
| `prisutnost snijega i leda` | Mikroklimatska → Prisutnost snijega i leda (vidi §3) |

Ostali zadaci za fetcher: izvesti **Otok** iz `Lokalitet` (gazetteer od ~125 000
mjesta već postoji u `crospeleo-automation`), parsirati **Sporedni ulazi** kao
slobodan tekst i eventualno iz njega otvoriti drugi zapis ulaza, te preslikati
`Crtali` → Nacrt *Autori* (danas se autori nacrta uzimaju iz SB stupca).

Naslovi koje `OSZParser._canonical_key` i dalje ne prepoznaje (27 od 50 prolazi):
`Prirodne opasnosti`, `Antropogene opasnosti i utjecaj`, `Crtali`, `Mjerili`,
`Nacrt uredio`, `Sporedni ulazi`, `Datum ili razdoblje istraživanja`,
`Istražile udruge`, `Stanje ulaza`, `Širina ulaza`, `Visina/duljina ulaza`,
`Duljina (m)`, `Izvor kote ulaza`, `Broj ulaza`, `Koordinate ulaza (HTRS96/TM)`,
`Katastarski broj`, `Broj pločice`, `Županija`, `Grad/općina` + tri naslova
sekcija. Popis se osvježava s `check_conformance.py`.

## 6. I dalje bez strukturiranog polja

Nije nužno za ovu verziju, ali ostaje na popisu: **Izvor koordinata** (8
vrijednosti, danas slobodan tekst — nepoznata vrijednost tiho pada na `GPS`),
**Strujanje zraka** u objektu / na ulazu + smjer (5+5+4+4),
**Mjerne točke** (temperatura zraka, vlažnost, temperatura vode i sedimenta kao
brojevi), **metoda i vrijednost CO₂**, te tri padajuća izbornika iz §1.

## 7. Mockup

[v10.1_primjer_811.docx](../mockups/v10.1_primjer_811.docx) /
[.pdf](../mockups/v10.1_primjer_811.pdf) — SUE 811 *Piccolo Bertarelli*, s
kvačicama: podrijetlo `smišljeno prema toponimu`, stanje ulaza
`zatvoren granjem/balvanima`, vrsta `špilja`, hidrologija `povremeni tok` +
`povremeni ponor`, perspektiva `potrebno proširivanje` + `nastavlja se`,
opasnost `mogućnost brzog potapanja kanala`, antropogeno `onečišćenje otpadom`.
Mikroklimatska mjerenja, zapremnina otpada i stanje ulaza su izmišljeni
(dokument iz 2025. ih nije nosio).

Što se vidi: sve grupe kvačica staju u dva stupca i ostaju čitljive; narativne
ćelije imaju fiksnu visinu pa kratki unosi (Biospeleološki, Arheološki) ostavljaju
prazninu, a `Osnovni opis` pola stranice; razlika u veličini fonta iz §4 i
slomljeni datum iz §2 jasno se vide.
