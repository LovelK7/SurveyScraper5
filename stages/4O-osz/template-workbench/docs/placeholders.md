# OSZ template — placeholder texts for the plain-text content controls

> Stanje predloška i što je od preporuka ispod već napravljeno:
> [audit-v10.2.md](audit-v10.2.md).

Drafted 2026-08-23 for the OSZ template rewrite (successor of
`!Zapisnik_OSZ_v10.docx`). Grounded in the read-only reference repo
`../crospeleo-automation`: the field specs in `services/osz_parser.py`, the
field-level rule book `RULES.md`, the CroSpeleo control inventories in
`docs/ui_reference/02_opazanja_tab/fields_inventory.md`, the calibration docs
for the Opasnosti / Zagađenost heuristics, and the three archived OSZ samples
in `tests/test_input/{502,795,811}/`.

Each placeholder is written so that the recorder is prompted for exactly the
data the CroSpeleo controls need — including the fields SpeleoFlow currently
leaves empty because the OSZ never captured them (mjerne točke, strujanje
zraka, zapremnina otpada, stanje otpada).

---

## 1. Položaj i pristup objektu

> Položaj: gdje objekt leži u reljefu (padina, dno vrtače, korito, stijena), udaljenost u metrima i smjer od prepoznatljive točke (ceste, naselja, susjednog objekta), okolna vegetacija i koliko se ulaz ističe u prostoru.
> Pristup: odakle se dolazi i gdje se parkira, ruta hoda s udaljenostima u metrima i stranama svijeta, procjena trajanja i prohodnosti terena. Ako postoji više varijanti pristupa, opiši ih redom.
> Primjer: „Ponor se nalazi 20 m od ceste Rašpor – Račja Vas, 230 m od ulaza u Jamu kod Rašpora. Parkirati uz cestu, prići vrtači sa sjeveroistočne strane i hodati koritom do pukotinastog ulaza.”

Feeds CroSpeleo *Položaj i zaštita objekta → Položaj i pristup objektu*
verbatim (obavezno polje, `*#` u protokolu v6). Protokol izričito traži da se
kod prepisivanja iz starijeg zapisnika zadrži „duh vremena” ovog polja.

## 2. Osnovni opis s tehničkim podacima

> Opiši objekt redom kojim se prolazi: neposredna okolica i ulaz (oblik, dimenzije u m, vidljivost, stanje), zatim unutrašnjost — kanali i dvorane s dimenzijama, vertikale s dubinama, sediment, sige, dno i suženja.
> Na kraju tehnički podaci za opremanje: broj i dubina vertikala, potrebna duljina užeta, sidrišta, oprema i preporučen broj ljudi.
> Sve što se odnosi na ulaz drži u zasebnim rečenicama — one se prenose u Napomenu ulaza.

Feeds CroSpeleo *Osnovni opis s tehničkim podacima* (obavezno). Rečenice koje
spominju ulaz automatika izdvaja u *Napomena ulaza*
(`extract_entrance_lead_from_technical`), pa zasebne rečenice o ulazu daju
čišći rezultat.

## 3. Speleomorfološki, geološki i hidrogeološki

> Morfogeneza i tip prostora (pukotinski, freatski, vadozni, urušni), pružanje i pad slojeva ili pukotina u stupnjevima i stranama svijeta, litologija i starost stijena s izvorom podatka (npr. OGK 1:100 000, list, autor i godina), sedimenti i sigasti oblici, tragovi voda i visokih voda te uloga objekta u hidrogeološkom sustavu i moguća veza s izvorima ili ponorima. Ako nije obrađeno, upiši „Nije obrađeno.”
> Primjer: „Prema OGK 1:100 000, list Ilirska Bistrica (Šikić, 1972), područje je građeno od dolomitne i vapnene breče gornje krede; donji dio objekta prati strmi pad slojeva u smjeru SZ–JI.”

## 4. Mikroklimatski

> Mjerna točka: mjesto i udaljenost od ulaza, datum mjerenja, temperatura zraka u °C, relativna vlažnost u %, temperatura vode i sedimenta ako su mjerene, te instrument (npr. „na −20 m, 12.5.2025., temperatura zraka 6,7 °C, vlažnost zraka 95 %, Testo 175”).
> Strujanje zraka: gdje je zamijećeno (u objektu, na ulazu), smjer (prema van / prema unutra, uzlazno / silazno) i je li stalno, povremeno ili sezonsko.
> Snijeg i led: prisutnost i trajnost (stalno / povremeno), dubina pojave od ulaza, najveća debljina i procijenjena površina.
> Povišen CO₂: procijenjeno osjetilno ili izmjereno, vrijednost i instrument.
> Ako ništa nije mjereno, upiši „Nije mjereno.”

Jedino polje koje hrani cijelu *Mikroklimatska mjerenja* sekciju: 8-labelni
matriks snijeg/led, dva Strujanje dropdowna + smjer, i karticu *Mjerna točka*
(temperatura zraka −10..30 °C, vlažnost 0..100 %, temperatura vode i
sedimenta). Zarez kao decimalni znak je u redu — parser ga prihvaća.

⚠ Ovaj placeholder sadrži riječi na koje heuristike reagiraju — vidi
[§ Rizik od curenja placeholdera](#c-rizik-od-curenja-placeholdera).

## 5. Biospeleološki

> Opažena fauna: skupine i približna brojnost te gdje su u objektu opažene; šišmiši (vrsta ako je poznata, pojedinačne jedinke ili kolonija, guano); ostali tragovi života (kosti, gnijezda, mreže).
> Uzorkovanje: tko je uzorkovao, kada, na kojem mjestu i kojom metodom, oznaka uzorka i kome je predan na determinaciju.
> Ako nije uzorkovano, upiši „Nije uzorkovano.” i navedi što je opaženo golim okom.

## 6. Arheološki i paleontološki

> Vrsta nalaza (keramika, ognjište, alat, kosti), točno mjesto i dubina u objektu, sloj i procijenjeno razdoblje, stanje nalaza (in situ, poremećen, iskopan), tko ga je utvrdio i je li obaviještena nadležna ustanova (konzervatorski odjel ili muzej).
> Nalaze koji nisu arheološki nego recentni ne opisuj ovdje — oni idu u polje Zagađenost i antropogeni utjecaji, a sumnju na recentne posmrtne ostatke odmah prijavi policiji.
> Ako nema nalaza, upiši „Nema opaženih nalaza.”

Razdvajanje prapovijesnih od recentnih ostataka je isto razgraničenje koje
automatika čuva čuvarom nad CroSpeleo poljem *Recentni ljudski ostaci*.

## 7. Zagađenost i antropogeni utjecaji

> Za svaku kvačicu iz popisa gore opiši: što je točno zatečeno, gdje u objektu i na kojoj dubini, procijenjena količina u m³ i je li objekt ranije čišćen (kada i tko).
> Navedi vjerojatan izvor i put dospijeća (blizina prometnice, naselja, poljoprivrednih površina, industrije, vojne djelatnosti) te zahvate u neposrednoj okolici (šumarski radovi, kamenolom, gradnja, zahvat na vodi).
> Opiši i način korištenja objekta: uređeno posjećivanje ili nekontrolirani dolasci, tragovi boravka i devastacije.
> Recentne ljudske ostatke navedi izričito i prijavi ih nadležnima.
> Ako objekt nije zagađen i nema tragova ljudskog utjecaja, upiši „Nije zagađen.”

Jedno polje hrani 30 kvadratića (*Antropogene aktivnosti* 15, *Korištenje
objekta* 2, *Klasifikacija onečišćenja* 13) i tri padajuća izbornika:
*Stanje otpada* (`očišćen` / `nije očišćen` / `djelomično očišćen`),
*Zapremnina otpada* (`manje od 1` / `1-5` / `5-10` / `više od 10` m³) i
*Recentni ljudski ostaci*. Zato placeholder traži količinu u m³ i podatak o
ranijem čišćenju — to su jedina dva podatka koja danas nemaju izvor u OSZ-u.

⚠ Sadrži riječi na koje heuristike reagiraju — vidi
[§ Rizik od curenja placeholdera](#c-rizik-od-curenja-placeholdera).

## 8. Opasnosti

> Za svaku označenu opasnost napiši gdje se nalazi (dio objekta, dubina u m), u kojim je uvjetima izraženija (nakon kiše, u topljenju snijega, zimi) i što je potrebno za siguran prolaz (osiguranje, oprema, oprez, broj ljudi).
> Ako je opasnost mjerena ili procijenjena, navedi vrijednost, način mjerenja i instrument.
> Zatečena ubojna sredstva ne dirati — opiši mjesto i prijavi nadležnima.
> Ako ništa nije uočeno, upiši „Nema uočenih opasnosti.”

Uz 13-labelni matriks, CroSpeleo ima i tri prateća polja uz *povišena
koncentracija CO2* (metoda: `izmjereno` / `subjektivno (osjetilno)`,
izmjerena vrijednost, mjerni instrument) — otud druga rečenica.

## 9. Perspektiva daljnjeg istraživanja

> Što je ostalo neistraženo i gdje točno (dio objekta, dubina), što je potrebno da se do toga dođe (oprema, ljudi, dozvola, radovi na suženju, tehnika užeta, ronjenje) i kolika je procjena izgleda.
> Navedi naznake na kojima temeljiš procjenu (gibanje zraka, naplavine, zvuk bačenog kamena, pružanje slojeva) i moguću vezu s drugim objektima.
> Ako je objekt dovršen, upiši „Objekt je potpuno istražen.”

## 10. Povijesni podaci

> Ranija istraživanja i posjeti: godina ili datum, tko je sudjelovao (imena i udruge) i što je tada napravljeno (pronalazak, prvi ulazak, mjerenje, raniji nacrt, radovi).
> Navedi i ranije nazive objekta te odakle ime potječe (od mještana, s karte, iz objavljenog izvora), kao i ranije zapisnike i arhivske izvore.
> Ako nema poznatih ranijih podataka, upiši „Nepoznato.”

`Nepoznato` / `Nije poznato` / `/` su tri sentinela koje parser prepoznaje kao
„nema sadržaja” (`_NO_CONTENT_SENTINELS`), pa polje neće završiti kao lažni
tekst u CroSpeleo Napomeni.

## 11. Literatura

> Svaki izvor u zasebnom retku, po obrascu: PREZIME, Inicijal. Naslov. Izdanje ili časopis, svezak, stranice, godina. Navedi i karte, izvještaje i interne zapisnike (s katastarskim brojem), a poveznicu ili DOI stavi na kraj retka.
> Primjer: „ŠIKIĆ, D.; PLENIČAR, M.; ŠPARICA, M. Osnovna geološka karta SFRJ, list Ilirska Bistrica, 1:100 000. Savezni geološki zavod, Beograd, 1972.”
> Ako izvora nema, upiši „/”.

---

## Prije nego što se predložak pusti u rad

### A. Sadržaj kontrola je današnjem parseru nevidljiv

Provjereno na python-docx 1.2.0 (verzija koju `crospeleo-automation` zaključava
u `pyproject.toml`): tekst unutar `w:sdt` kontrole **ne vidi se** ni kroz
`paragraph.text`, ni kroz `cell.text`, ni kroz `document.paragraphs` — bilo da
je kontrola *inline* u odlomku, da omata cijeli odlomak, ili da omata ćeliju
(`w:tc`, kao u v10 kod polja *Speleomorfološki, geološki i hidrogeološki*).
Ćelijska varijanta je najgora: `row.cells` tu ćeliju uopće ne vrati, pa se
mijenja i oblik retka koji parser čita.

Posljedica: svako polje koje u novom predlošku bude unutar kontrole parser će
pročitati kao prazno. Popravak je malen — tekst vaditi preko XML-a
(`.//w:sdtContent//w:t`) umjesto preko `paragraph.text`, uz preskakanje
kontrola koje nose `w:showingPlcHdr`.

### B. Placeholder je u document.xml — čuvar `w:showingPlcHdr` je obavezan

Netaknuta kontrola drži svoj placeholder kao pravi tekst u `document.xml`
(u v10 se to već vidi na geološkom polju). Ako parser počne čitati sadržaj
kontrola bez provjere `w:showingPlcHdr`, svaki nepopunjeni placeholder ući će
u dosje i završiti u CroSpeleo *Napomeni*, a heuristike će na njemu okinuti
kvačice.

### C. Rizik od curenja placeholdera

Gornji tekstovi su provjereni tako da su propušteni kroz stvarne mapere
(`map_opasnosti`, `map_zagadenost_ljudski`, `map_perspektiva`,
`map_snijeg_led`, `map_temperatura_zraka`, `map_vlaznost_zraka`,
`map_strujanje_zraka`), svaki kroz onaj koji doista čita to polje:

| Polje | Ako placeholder procuri |
|---|---|
| Položaj, Osnovni opis, Speleomorfološki, Biospeleološki, Arheološki, Opasnosti, Perspektiva, Povijesni, Literatura | čisto — nijedna kvačica ne okida |
| **Mikroklimatski** | okida `led - stalno`, `snijeg - stalno`, temperatura 6,7 °C, vlažnost 95 %, strujanje `povremeno` / `prema van` |
| **Zagađenost** | okida 4 antropogene aktivnosti, `neregulirano posjećivanje`, `otpadne vode poljoprivredne`, `nije očišćen otpad`, `recentni ljudski ostaci = da` |

Dakle: uz čuvar iz točke B sve je u redu. Ako čuvara nema, za ta dva polja
koristi ove „tihe” varijante (provjereno: ne okidaju ništa), po cijenu
neodređenijeg teksta:

**Mikroklimatski (tiha varijanta)**

> Mjerna točka: mjesto i udaljenost od početka objekta, datum, izmjerene vrijednosti s jedinicama i instrument kojim je mjereno.
> Gibanje zraka: gdje je zamijećeno, u kojem smjeru i je li trajno ili sezonsko.
> Zimske pojave u objektu: što je zamijećeno, koliko se zadržava, na kojoj udaljenosti od početka objekta, procjena debljine i površine.
> Plinovi: ako su procijenjeni osjetilno ili mjereni, navedi vrijednost i instrument.
> Ako ništa nije mjereno, upiši „Nije mjereno.”

**Zagađenost (tiha varijanta)**

> Za svaku kvačicu iz popisa gore opiši: što je točno zatečeno, gdje u objektu i na kojoj dubini, procijenjena količina u m³ te je li stanje ranije sanirano (kada i tko).
> Navedi vjerojatno podrijetlo i put dospijeća u objekt, kao i zahvate u neposrednoj okolici koji na objekt utječu.
> Opiši koliko se u objekt dolazi i je li dolazak kontroliran, uz tragove boravka.
> Ako je zatečeno nešto što treba prijaviti nadležnima, opiši i navedi kome je prijavljeno.
> Ako objekt nije zagađen i nema tragova ljudskog utjecaja, upiši „Nije zagađen.”

### D. Stavi `w:tag` na svaku kontrolu

Kontrola nosi i `w:tag` i `w:alias`, oba čitljiva iz XML-a. Ako svaka kontrola
dobije `w:tag` jednak kanonskom imenu polja u parseru, parser prestaje ovisiti
o tekstu naslova (koji se mijenja iz verzije u verziju) i dobiva `template_version`
signal koji `TODO` predviđa:

| Polje u zapisniku | `w:tag` |
|---|---|
| Položaj i pristup objektu | `location_access_text` |
| Osnovni opis s tehničkim podacima | `technical_description` |
| Speleomorfološki, geološki i hidrogeološki | `expert_geology_hydrogeology` |
| Mikroklimatski | `expert_meteorology` |
| Biospeleološki | `expert_biology` |
| Arheološki i paleontološki | `expert_archaeology_paleontology` |
| Zagađenost i antropogeni utjecaji | `expert_pollution_anthropogenic` |
| Opasnosti | `expert_hazards` |
| Perspektiva daljnjeg istraživanja | `future_exploration_perspective` |
| Povijesni podaci | `historical_data` |
| Literatura | `literature` |

### E. Naslovi u v10 koje parser danas ne prepoznaje

Provjereno pozivom `OSZParser._canonical_key` na naslove iz
`!Zapisnik_OSZ_v10.docx`:

- `Prirodne opasnosti` → nema alias (alias je samo `opasnosti`) — cijela
  sekcija opasnosti ispada iz dosjea
- `Nacrt uredio` → nema alias (polje koje `TODO` traži za CroSpeleo *Nacrt
  uredili*; danas se vadi iz PDF-a nacrta)
- `Datum ili razdoblje istraživanja`, `Istražile udruge`, `Stanje ulaza`,
  `Širina ulaza`, `Visina/duljina ulaza`, `Koordinate ulaza (HTRS96/TM)`,
  `Duljina (m)` → nema alias (`Dubina (m)` prolazi, `Duljina (m)` ne)

Uz `w:tag` iz točke D ovo prestaje biti problem; bez toga treba dopuniti
`_BASE_FIELD_SPECS`.

### F. Tekst kvačica curi u susjedna polja

Parsiranje praznog v10 predloška vraća samo tri polja, i dva od njih su kriva:
`nearest_place` i `locality` dobiju cijeli vokabular *Podrijetla imena*
(`smišljeno novo smišljeno prema toponimu preuzeto iz literature …`), jer redak
s kvačicama nema svoj ključ pa ga logika „nastavka retka” pripiše prethodnom
polju. Čitanje `w14:checkbox/w14:checked` (stanje kvačice je uredno zapisano u
XML-u) rješava i ovo i daje strukturirane vrijednosti koje `TODO` §„OSZ
template overhaul” traži.
