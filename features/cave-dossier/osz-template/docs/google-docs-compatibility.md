# Kako OSZ predložak preživi Google Docs

Zapisnik se često ispunjava tako da se datoteka otvori s Google Drivea u Google
Docsu. Google Docs **ne podržava Wordove content controlse**, pa se predložak
napravljen preko kartice Developer tamo raspadne. Ovaj dokument popisuje što
točno puca, koje je pravilo za svaki slučaj, i kako se iz izvorne Word inačice
generira paralelna inačica za Google Docs. **Obje se održavaju**; Word inačica
je ona koja se preporučuje.

## Što Google Docs radi s Wordovim mehanizmima

| Mehanizam | Kako se ponaša u Google Docsu | Pravilo |
|---|---|---|
| **Checkbox content control** (`w14:checkbox`) | Kontrola nestaje, ostane goli znak iz fonta *Wingdings 2* (`F0A3`). Google nema taj font pa nacrta nasumičan kvadratić; kvačica se više ne može kliknuti. | Piši `[ ]` kao običan tekst; označava se upisivanjem `x` → `[x]` |
| **Plain-text content control** (`w:text`) | Kontrola nestaje, a **placeholder postaje pravi sivi tekst**. Čim korisnik snimi, uputa je sadržaj dokumenta i ide u dosje kao da ju je netko upisao. | Nema kontrole; uputa je **običan crni tekst** omeđen `⟨ … ⟩`, pa je fetcher može odbaciti (zašto ne siva — vidi niže) |
| **Plutajuća tablica** (`w:tblpPr`) | Sidrenje se gubi ili pomiče, tablica sklizne na krivu stranicu i povuče prijelome za sobom. | Tablica mora biti u normalnom toku teksta |
| **Ugrađeni fontovi** (`word/fonts/*.odttf`) | Ignoriraju se u cijelosti. U ovom predlošku su bili **8,5 MB od 4,5 MB datoteke**. | Isključi *Embed fonts in the file*; datoteka padne na ~30 KB |
| **Fiksne visine redaka** (`w:trHeight`, `hRule` neodređen = `atLeast`) | Poštuje se približno; Docs računa visine drukčije pa se prijelomi mogu pomaknuti za redak. | Ne oslanjaj se na točnu visinu za izgled; ostavi zraka na dnu stranice |
| **Spojene ćelije** (`vMerge`), sjenčanje, obrubi, slike | Prolaze uredno. | — |

## Dvije inačice, jedna preporučena

Obje inačice se održavaju i dijele:

| Inačica | Kome | Zašto |
|---|---|---|
| `Zapisnik_OSZ_v10.docx` (**preporučena**) | svima koji ispunjavaju u Wordu | prave kvačice na klik, placeholder nestane čim se počne tipkati, nikakav trag upute ne ostaje u podacima |
| `Zapisnik_OSZ_v10_gdocs.docx` | onima koji otvaraju s Drivea u Google Docsu | Docs Wordove kontrole baca, pa ova inačica nema nijednu |

U zaglavlju/podnožju `_gdocs` inačice stoji linija koja upućuje na izvornu
Word inačicu, da nitko ne završi u slabijoj varijanti bez potrebe.

### Kako se radi `_gdocs` inačica

```bash
python tools/flatten_for_gdocs.py \
    templates/Zapisnik_OSZ_v10.docx \
    templates/Zapisnik_OSZ_v10_gdocs.docx
```

Skripta radi pet stvari: 66 kvačica → `[ ]`, 15 tekstualnih kontrola →
`⟨ … ⟩` uputa (ako je placeholder netaknut) ili čist upisani tekst (ako je polje
popunjeno), plutajuća tablica → normalni tok, ugrađeni fontovi → van, i linija
u podnožju koja upućuje na Word inačicu (`--no-note` je isključuje). Rezultat je
~30 KB umjesto 4,5 MB i otvara se jednako u Wordu, Google Docsu i LibreOfficeu.

Skripta je **idempotentna** i smije se pozvati s istim putem kao ulaz i izlaz,
pa se `_gdocs` inačica koja je ručno dorađena u Wordu popravi na mjestu bez
ponovnog generiranja (i bez gubitka tih ručnih ispravaka).

> **Upute nisu sive ni kurzivne.** U Word inačici placeholder nestane čim
> recorder počne tipkati, pa sivilo ništa ne košta. Ovdje kontrole nema — tekst
> se prepisuje preko upute, a novi tekst naslijedi formatiranje onoga što je
> zamijenio. Siva uputa znači sivi odgovor, jer nitko neće ručno prebacivati
> boju natrag u crno. Zato je uputa običan crni tekst, a prepoznaje se po
> `⟨ ⟩` oznakama.

> **Word pri svakom snimanju vraća ugrađene fontove** (datoteka naraste na ~3 MB)
> ako je u predlošku uključen *Embed fonts in the file*. Ili isključi tu opciju
> u izvorniku (File → Options → Save), ili nakon svakog uređivanja u Wordu opet
> pokreni skriptu nad `_gdocs` datotekom.

## Provjera round-tripa (2 minute)

1. Uploadaj `Zapisnik_OSZ_v10_gdocs.docx` na Drive i otvori ga u Google Docsu.
2. File → Download → Microsoft Word (.docx).
3. Usporedi:

```bash
python tools/check_gdocs_roundtrip.py \
    templates/Zapisnik_OSZ_v10_gdocs.docx \
    ~/Downloads/Zapisnik_OSZ_v10_gdocs.docx
```

Skripta uspoređuje broj `[ ]` kvačica i `⟨ ⟩` uputa, geometriju svih tablica,
sve nazive polja, te javlja zaostale kontrole/Wingdings znakove/plutajuće
tablice i koliko je Google iscjepkao tekst na runove. `PASS` znači da fetcher
može oba oblika čitati istim kodom.

Datoteku koju Google vrati **sačuvaj** kao fixture za razvoj fetchera — to je
najgori realni slučaj koji parser mora podnijeti.

## Što ovo znači za fetcher

Dobra vijest: bez kontrola je parsiranje **jednostavnije**, i identično bez
obzira je li zapisnik ispunjen u Wordu ili u Docsu.

- Kvačica je označena ako token prije naziva opcije nije `[ ]` — prihvati
  `[x]`, `[X]`, `[✓]`, `[✔]`.
- Vrijednost polja se odbacuje ako je omeđena s `⟨ … ⟩` (netaknuta uputa).
  Sentinel je pouzdaniji od uspoređivanja s popisom uputa jer preživi i ako
  netko malo prepravi tekst.
- **Nikad ne matchaj na pojedini `w:r`.** Google drukčije dijeli runove; tekst
  odlomka treba prvo spojiti (`''.join` po `w:t` unutar `w:p`), pa onda
  regexirati. Ista disciplina vrijedi i za `[ ]` — Word ga zna razbiti na dva
  runa.
- Tablice ostaju iste, pa dohvat po `table[t].row[r].cell[c]` i dalje radi;
  `tools/inspect_osz.py --mode index` ispisuje te adrese za oba oblika.

## Zaostalo

- Spljoštena verzija popunjenog zapisnika je **5 stranica** umjesto 4 —
  tablica *Karakteristike objekta* više ne pluta pa zauzme normalan prostor.
  Vratit će se na 4 ako se smanje fiksne visine praznih ćelija
  (Biospeleološki i Arheološki drže po pola stranice bjeline).
- Fusnote/endnote dijelovi (`footnotes.xml`, `endnotes.xml`) ostaju u datoteci,
  prazni su i bezopasni.
