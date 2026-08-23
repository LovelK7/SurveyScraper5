# osz-template — radionica za OSZ predložak

Sve što se tiče **Word predloška Osnovnog speleološkog zapisnika**: verzije
predloška, alati za inspekciju i provjeru, tekstovi placeholdera i ogledni
ispunjeni primjerci. Dio featurea [cave-dossier](../README.md) (dio 2.2
cjevovoda — OSZ builder), ali odvojen jer je ovo rad na dokumentu, a ne na kodu.

```
templates/   Zapisnik_OSZ_v10.docx      ← radna verzija (verzija predloška ostaje v10)
             archive/                   ← snimke ranijih iteracija istog dana
docs/        placeholders.md            ← tekstovi placeholdera + zašto
             audit-v10.2.md             ← zadnja provjera (završna varijanta v10)
             audit-v10.1.md, audit-v10.0.md ← ranije varijante (povijesno)
             conformance-v10.2.txt      ← izlaz check_conformance.py
tools/       inspect_osz.py             ← struktura dokumenta
             check_conformance.py       ← provjera prema CroSpeleo/SpeleoFlow
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
```

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
