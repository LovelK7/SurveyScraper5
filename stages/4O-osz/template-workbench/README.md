# osz-template — radionica za OSZ predložak

Sve što se tiče **Word predloška Osnovnog speleološkog zapisnika**: verzije
predloška, alati za inspekciju i provjeru, tekstovi placeholdera i ogledni
ispunjeni primjerci. Dio featurea [cave-dossier](../README.md) (dio 2.2
cjevovoda — OSZ builder), ali odvojen jer je ovo rad na dokumentu, a ne na kodu.

```
templates/   Zapisnik_OSZ_v10.docx      ← izvornik na kojem se radi (nezaključan)
             Zapisnik_OSZ_v10.dotx      ← PREPORUČENO za recordere: dvoklik = novi dokument
             Zapisnik_OSZ_v10_gdocs.docx ← inačica za one koji rade u Google Docsu
             archive/                   ← snimke ranijih iteracija istog dana
docs/        placeholders.md            ← tekstovi placeholdera + zašto
             audit-v10.2.md             ← zadnja provjera (završna varijanta v10)
             audit-v10.1.md, audit-v10.0.md ← ranije varijante (povijesno)
             conformance-v10.2.txt      ← izlaz check_conformance.py
             google-docs-compatibility.md ← što puca u Google Docsu i zašto
             zastita-predloska.md       ← kako spriječiti prepisivanje predloška
tools/       inspect_osz.py             ← struktura dokumenta
             lock_template.py           ← zaključana .dotx inačica za dijeljenje
             check_conformance.py       ← provjera prema CroSpeleo/SpeleoFlow
             flatten_for_gdocs.py       ← Word verzija → verzija za Google Docs
             check_gdocs_roundtrip.py   ← usporedba prije/poslije Google Docsa
             make_mockup.py             ← generira ispunjeni ogledni zapisnik
mockups/     v10.2_primjer_811.*        ← kako izgleda popunjen (ranije: v10.0, v10.1)
```

## Radni ciklus

Nakon svake izmjene predloška u Wordu:

```bash
cd features/cave-dossier/osz-template

# 1. što je unutra — kvačice po grupama, zastavice tekstualnih kontrola
python tools/inspect_osz.py templates/Zapisnik_OSZ_v10.docx --mode controls

# 2. slaže li se s CroSpeleo vokabularom, parserom i higijenom kontrola
python tools/check_conformance.py templates/Zapisnik_OSZ_v10.docx | tee docs/conformance-v10.2.txt

# 3. kako izgleda popunjen
python tools/make_mockup.py templates/Zapisnik_OSZ_v10.docx mockups/v10.2_primjer_811.docx

# 4. verzija koja radi i u Google Docsu
python tools/flatten_for_gdocs.py templates/Zapisnik_OSZ_v10.docx templates/Zapisnik_OSZ_v10_gdocs.docx

# 5. zaključana .dotx inačica za dijeljenje (dvoklik otvara novi dokument)
python tools/lock_template.py templates/Zapisnik_OSZ_v10.docx templates/Zapisnik_OSZ_v10.dotx        --lock-controls --read-only-rec --dotx --strip-fonts
```

**Obje inačice ostaju u upotrebi.** Recorderima se preporučuje **izvorna Word
inačica** — kvačice se klikću, uputa nestane čim se počne tipkati, ništa ne
zaostaje u tekstu. Inačica `_gdocs` je za one koji zapisnik otvaraju s Drivea u
Google Docsu, jer Docs Wordove kontrole baca. Detalji i pravila:
[docs/google-docs-compatibility.md](docs/google-docs-compatibility.md).

Alat je idempotentan i smije se pokrenuti nad samom `_gdocs` datotekom (isti
put kao ulaz i izlaz) — tako se popravi inačica koja je ručno dorađena u Wordu.

`inspect_osz.py --mode index` ispisuje adrese `table[t].row[r].cell[c]` — to su
koordinate koje `make_mockup.py` koristi. Kad se preraspored redaka promijeni,
prvo pokreni `--mode index`, pa popravi koordinate u generatoru.

## Zašto vlastiti alati, a ne python-docx

Word content controls (`w:sdt`) su python-docx-u **nevidljivi** — ni
`paragraph.text`, ni `cell.text`, ni `document.paragraphs` ne vraćaju njihov
sadržaj, a kontrola na razini ćelije sakrije i cijeli `w:tc` iz `row.cells`.
Svi alati ovdje rade izravno na `word/document.xml` preko lxml. Isto vrijedi i
za budući fetcher u `crospeleo-automation` — detalji u
[docs/placeholders.md](docs/placeholders.md) §A.

## Naučene zamke pri generiranju .docx

- **Plain-text kontrola ne smije sadržavati drugi `w:p`.** Word odbija datoteku
  („The file appears to be corrupted”) čak i kad je `w:text multiLine="1"`.
  Za više redaka koristi `<w:br/>` unutar jednog odlomka.
- **`w14:paraId` mora biti jedinstven** u dokumentu; kopiranje odlomka bez
  brisanja tog atributa također ruši datoteku.
- Kvačica se pali s `w14:checked w14:val="1"` **i** promjenom simbola u runu
  (`w:sym w:char="F052"` za Wingdings 2), inače ostane vizualno prazna.
- Kod popune preuzmi `rPr` iz `sdtPr` ili iz oznake odlomka — ne iz sivog
  placeholder runa, jer taj nosi `w:color 808080`.

## Vanjske ovisnosti

`check_conformance.py` po potrebi importa `OSZParser` iz read-only repozitorija
`../../../../crospeleo-automation` (putanja se mijenja s `--crospeleo`). Ako
tamošnji interpreter/ovisnosti nisu dostupni, provjera aliasa se preskače, a
ostale dvije provjere rade. **U tom repozitoriju se ništa ne mijenja.**

Vokabulari u `check_conformance.py` prepisani su iz
`docs/ui_reference/**/fields_inventory.md`; ako CroSpeleo doda opciju, treba ih
osvježiti ručno.
