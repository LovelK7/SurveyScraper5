# Zaštita predloška od slučajnog prepisivanja

Problem: datoteka na Driveu koju netko otvori u Google Docsu **uređuje se na
licu mjesta**. Drive za `.docx` koristi Office-editing način rada, pa što god
recorder utipka odlazi natrag u istu datoteku — i predložak više nije prazan
predložak. Ista stvar se dogodi i u Wordu ako netko ispuni zapisnik pa slučajno
stisne Spremi umjesto Spremi kao.

**Kratak odgovor: dozvola na Driveu je dovoljna.** Ako je predložak podijeljen
kao *Viewer*, nitko ga ne može prepisati — ni iz Docsa ni iz Worda — jer nema
pravo pisanja u tu datoteku. Ostala dva sloja su jeftini dodaci protiv tipičnih
grešaka, ne zamjena za dozvolu.

## Sloj 1 — dozvole na Driveu (jedino što Docs poštuje)

Predložak drži u mapi u kojoj recorderi imaju **Viewer** (Preglednik), ne
Editor. Tada Docs nema što ponuditi osim *File → Make a copy* i *Download*;
original se ne može prepisati jer korisnik nema pravo pisanja.

Za one koji rade u Google Docsu najčišći je postupak:

1. Jednom pretvori `Zapisnik_OSZ_v10_gdocs.docx` u pravi Google dokument
   (Drive → Open with Google Docs → File → Save as Google Docs).
2. Podijeli ga kao **Viewer**.
3. Recorderima daj link kojemu je na kraju `/edit` zamijenjen s **`/copy`** —
   otvaranje takvog linka odmah nudi „Make a copy”, pa svatko dobije svoj
   primjerak, a izvornik ostaje netaknut.

Nijedna postavka unutar `.docx` datoteke ovo ne može zamijeniti.

## Sloj 2 — `.dotx` umjesto `.docx` (Word)

`templates/Zapisnik_OSZ_v10.dotx` je isti zapisnik, ali označen kao **Wordov
predložak**. Dvoklik u Exploreru otvara **novi dokument** izgrađen na predlošku;
sama `.dotx` datoteka nikad nije ono što se uređuje. To je mehanizam napravljen
točno za ovaj problem.

Provjereno lokalno: `Documents.Add` nad `.dotx` otvara `Document1` (nespremljen,
bez imena), predložak ostaje nedirnut; dokument ima svih 81 kontrolu i 4 stranice.

Na Driveu se očekuje da `.dotx` **ne** uđe u Office-editing način rada (Drive ga
podržava samo za `.docx`/`.xlsx`/`.pptx`), nego ponudi pretvorbu u kopiju — ali
to nije provjereno, pa vrijedi isprobati prije nego se osloniš na to.

## Sloj 3 — zaključavanje unutar datoteke (Word)

`.dotx` nosi dvije blage brave:

| Postavka | Što blokira | Provjereno |
|---|---|---|
| `w:lock w:val="sdtLocked"` na svih 81 kontrola | brisanje samog polja; sadržaj se i dalje uređuje | `ContentControls(1).Delete()` odbijeno ✔ |
| `writeProtection w:recommended="1"` | ništa — samo pita „otvoriti samo za čitanje?” kad se otvara sam predložak | — |

Unos radi normalno u sve tri vrste polja (provjereno na dokumentu izrađenom iz
predloška): obična ćelija `IME OBJEKTA` → `Test objekt`, tekstualna kontrola →
`proba`, kvačica → označena.

### Zašto NIJE uključena zaštita „samo polja za unos”

`documentProtection w:edit="forms"` zvuči kao pravo rješenje, ali u ovom
zapisniku **razbija formu**: od 31 ćelije za unos samo ih 4 imaju content
control. Ostalih 27 su obične ćelije tablice —

`Katastarski broj`, `Broj pločice`, `IME OBJEKTA`, `Sinonimi`, `Županija`,
`Grad/općina`, `Najbliže mjesto`, `Lokalitet`, `Kota ulaza`, `Izvor kote ulaza`,
`Broj ulaza`, `Izvor koordinata`, `Širina ulaza`, `Visina/duljina ulaza`,
`Duljina`, `Horizontalna duljina`, `Dubina`, `Datum ili razdoblje istraživanja`,
`Istražile udruge`, `Članovi ekipe`, `Crtali`, `Mjerili`, `Nacrt uredio`,
`Fotografirali`, `Autor fotografije ulaza`, `Zapisničar` …

— i uz tu zaštitu sve one postaju read-only. Ostane zapisnik u kojem se mogu
kliknuti kvačice i upisati stručni tekstovi, ali ne i ime objekta.

Zaštita se može uključiti tek kad i tih 27 ćelija dobije plain-text kontrole —
isti posao koji ionako stoji na popisu radi `w:tag` oznaka za fetcher. Dotad je
`--forms` isključen.

Lozinka (`--password`) sprema se kao ECMA-376 hash (SHA-512, 100 000 iteracija)
i brava je samo na *Review → Restrict Editing → Stop Protection*, ne šifriranje
datoteke. Bez `--forms` nema što zaključati, pa je i ona bespredmetna.

## Što Google Docs poštuje od svega ovoga

Ništa. `documentProtection`, `writeProtection` i *Mark as Final* nemaju
ekvivalent u Docsu i pri uvozu se tiho ignoriraju. Jedina zaštita koja tamo
vrijedi je dozvola s Drivea (sloj 1).

Jedini način da datoteka bude neotvoriva u Docsu jest **šifriranje lozinkom za
otvaranje** (Word: File → Info → Protect Document → Encrypt with Password) —
Docs takvu datoteku ne može ni prikazati. To rješava problem, ali onda svaki
recorder mora znati lozinku i upisati je u Wordu, pa je gore od dozvola.

## Kako se generira predložak za dijeljenje

```bash
python tools/lock_template.py \
    templates/Zapisnik_OSZ_v10.docx \
    templates/Zapisnik_OSZ_v10.dotx \
    --lock-controls --read-only-rec --dotx --strip-fonts
```

Izvorni `Zapisnik_OSZ_v10.docx` ostaje **nezaključan** — to je datoteka na kojoj
se radi. `.dotx` je ono što se dijeli. `--strip-fonts` izbaci ugrađene fontove
(4,5 MB → 48 KB).

## Sažetak — što komu dati

| Tko | Datoteka | Zaštita |
|---|---|---|
| Ispunjava u Wordu | `Zapisnik_OSZ_v10.dotx` | dvoklik radi novi dokument; polja se ne mogu obrisati |
| Ispunjava u Google Docsu | Google-doc inačica, `/copy` link | Viewer dozvola na Driveu |
| Uređuje sam predložak (ti) | `Zapisnik_OSZ_v10.docx` | nema — pa se onda regenerira `.dotx` i `_gdocs` |
