// Speleo nadzorna ploča – the texts behind every "?" (app.js: helpBtn).
// Written for someone who has never seen the tools: what the part is for,
// then what to do, in a few short lines. t = title, d = what it is,
// s = what to do (a list), n = one closing hint.
"use strict";

const HELP = {
  // ── top bar + console ──────────────────────────────────────────────
  "top-sb": {
    t: "Speleo baza (SB)",
    d: "SB je glavna Excel tablica registra sa svim objektima. Oznaka pokazuje koju kopiju alati upravo čitaju.",
    s: ["LIVE – živa SB s Drivea. Tako treba biti.",
        "FALLBACK – živa SB je zauzeta (najčešće otvorena u Excelu), pa alati čitaju zadnju dobru kopiju. Zatvori Excel i pritisni Osvježi.",
        "SANDBOX – probna kopija, ne prava SB."],
    n: "Alati SB nikad ne mijenjaju sami – prijedloge izmjena daju kao CSV koji ručno preneseš u Excel.",
  },
  "top-cave": {
    t: "Objekt",
    d: "Špilja ili jama na kojoj radiš. Kad je odabrana, sve kartice i naredbe rade na njoj.",
    s: ["Upiši Redni broj iz SB-a ili dio imena i odaberi s popisa.",
        "Mapa otvara mapu objekta na Driveu, ✕ miče odabir."],
    n: "Novi objekt: upiši njegov Redni broj – mapa još ne mora postojati.",
  },
  "console": {
    t: "Ispis",
    d: "Ovdje se vidi što pokrenuta naredba radi, redak po redak.",
    s: ["Svaki pokrenuti posao dobiva svoju karticu u traci.",
        "Ako program nešto pita, odgovor upiši u polje na dnu i pritisni Pošalji.",
        "Zaustavi prekida posao; Zapis otvara spremljeni ispis."],
    n: "Klik na naslov Ispis otvara, povećava i zatvara ovaj prozor.",
  },

  // ── Pregled ────────────────────────────────────────────────────────
  "home": {
    t: "Pregled",
    d: "Početna stranica: stanje odabranog objekta i alata na jednom mjestu.",
    s: ["Gore desno odaberi objekt.",
        "U kartici objekta pronađi korak označen SADA i pritisni njegov gumb.",
        "Lijevi izbornik vodi na pojedine faze, redom kojim se rade."],
  },
  "cave": {
    t: "Tijek rada objekta",
    d: "Svi koraci za ovaj objekt, od terena do predaje, redom kojim se rade.",
    s: ["Zeleno ✓ – gotovo.",
        "SADA – sljedeći korak. Gumb ga pokreće odmah, sa zadanim postavkama.",
        "Narančasto – zastarjelo: nešto se promijenilo, ponovi korak.",
        "Sivo – čeka prethodni korak ili nije obavezno."],
    n: "Oznaka na kraju retka (npr. 3N) otvara karticu tog koraka s više mogućnosti.",
  },
  "sb-card": {
    t: "Speleo baza",
    d: "Koja je verzija SB-a živa i koju kopiju alati sada čitaju.",
    s: ["Otvori SB u Excelu – za ručni unos podataka.",
        "Prije pokretanja naredbi zatvori Excel, inače alati čitaju stariju kopiju."],
  },
  "drive": {
    t: "Mape na Driveu",
    d: "Prečaci do zajedničkih mapa registra na Google Driveu.",
    s: ["Klik otvara mapu u Exploreru.",
        "Siv gumb znači da mapa ne postoji ili Drive nije spojen.",
        "Radni prostor su lokalne mape alata (zapisi, preuzeti podaci)."],
  },
  "machine": {
    t: "Ovo računalo",
    d: "Gdje su na ovom računalu radni prostor, Drive, alati za nacrt i cSurvey.",
    n: "Ako nešto „nije pronađeno”, naredbe koje to trebaju neće raditi – javi se onome tko je postavio alate.",
  },
  "queue": {
    t: "Fotografije u redu čekanja",
    d: "Fotografije ulaza u zajedničkoj mapi …za istražit koje već nose broj objekta (SB_<broj>_).",
    s: ["Otvori – prelazi na Fotografije (4F) za taj objekt.",
        "Tamo ih povuci u mapu objekta, pa obradi."],
  },
  "unprefixed": {
    t: "Mape bez SB_ prefiksa",
    d: "Mape s terena koje još nisu povezane s redom u SB-u, pa ih birač objekata ne vidi.",
    s: ["Poveži u 1T predlaže Redni broj za svaku mapu.",
        "Kad je prijedlog dobar, pokreni ponovno s kvačicom Preimenuj mape."],
  },
  "dups": {
    t: "Redni broj nije jedinstven",
    d: "Isti Redni broj stoji u više redova SB-a, pa alati ne znaju koji je objekt pravi.",
    s: ["Otvori SB i daj svakom objektu njegov broj.",
        "Spremi, zatvori Excel i pritisni Osvježi."],
  },

  // ── ★ Brze radnje ──────────────────────────────────────────────────
  "fast": {
    t: "Brze radnje",
    d: "Gotovi nizovi koraka koji se za odabrani objekt pokreću jednim klikom.",
    s: ["Odaberi objekt gore desno.",
        "Odznači korake koje ne želiš.",
        "Pokreni sve – napredak se vidi u Ispisu dolje."],
    n: "Ono što već postoji se preskače, pa je ponavljanje sigurno. „piše” znači da korak mijenja datoteke.",
  },
  "recipe:novi-objekt": {
    t: "Novi objekt u jednom potezu",
    d: "Za objekt koji je tek upisan u SB: mapa, isječak karte, OSZ i fotografije ulaza.",
    n: "Prvi izbor za svaki novi objekt.",
  },
  "recipe:spoji": {
    t: "Spoji nakon izmjere",
    d: "Kad je nacrt ispisan (3N KORAK 3b): duljina i dubina idu u OSZ, a Nacrt se slaže iznova.",
  },
  "recipe:provjera": {
    t: "Provjeri objekt",
    d: "Ništa ne mijenja. Pokazuje red u SB-u, je li objekt spreman za predaju i imaju li autori izjave.",
    n: "Dobar prvi korak kad ne znaš što objektu još nedostaje.",
  },

  // ── stage tabs ─────────────────────────────────────────────────────
  "1T": {
    t: "Teren",
    d: "Svaki objekt ima mapu pod !Za digitalizirat na Driveu, s imenom SB_<broj>_<Ime>. Tu idu podaci s terena.",
    s: ["Napravi mapu objekta – za novi objekt.",
        "Poveži mape s SB-om – za stare mape bez SB_ na početku imena."],
    n: "Bez mape alati ne vide datoteke objekta.",
  },
  "2B": {
    t: "Speleo baza",
    d: "Pregled SB-a i traženje grešaka u njoj. Ništa se ne mijenja.",
    s: ["Red objekta u SB-u – svi podaci odabranog objekta.",
        "Revizije – redovi koje treba ručno ispraviti u Excelu."],
  },
  "4G": {
    t: "Geo",
    d: "Iz koordinata ulaza određuje županiju, općinu, najbliže mjesto i kotu, i uspoređuje ih sa SB-om.",
    s: ["Odaberi objekt i pokreni Lokalitet ili Kotu.",
        "Razlike prema SB-u, ako su ispravne, prepiši ručno u SB."],
    n: "Preuzmi geo podatke treba samo jednom, na novom računalu. Pripremi OSZ (4O) ovo radi sam.",
  },
  "4I": {
    t: "Isječak karte",
    d: "Sprema isječak topografske karte s ucrtanim ulazom (s georef.hr), za OSZ.",
    s: ["Odaberi objekt i pokreni.",
        "Slika se sprema u !!Isječci karte i prikazuje se ispod."],
    n: "Svako pokretanje stvara točku na georef.hr – ne ponavljaj bez potrebe.",
  },
  "4O": {
    t: "OSZ – Osnovni speleološki zapisnik",
    d: "Word zapisnik objekta. Alat ga popunjava iz SB-a, karte i izmjere, a ostalo dopisuješ ručno.",
    s: ["Pripremi / osvježi OSZ – napravi ga ili osvježi (upisano ostaje).",
        "Dopiši ostalo u Wordu.",
        "Provjeri obvezna polja – što još nedostaje.",
        "Iz popunjenog OSZ-a u SB – prijedlog dopuna SB-a kao CSV."],
    n: "Zatvori OSZ u Wordu prije pokretanja.",
  },
  "3N": {
    t: "Nacrt",
    d: "Od TopoDroid izmjere (.csx) do gotovog nacrta SB_<broj>_nacrt.pdf, preko cSurveya.",
    s: ["KORAK 1, pa u cSurveyu otvori i spremi.",
        "KORAK 2, pa u cSurveyu ispravi skicu i spremi.",
        "KORAK 3a → 3b → 3c – završni nacrt.",
        "KORAK 4 – izmjere u OSZ."],
    n: "Koraci idu redom; sljedeći je označen SADA.",
  },
  "4S": {
    t: "Sastavnica",
    d: "Naslovni blok s podacima o objektu, za nacrt koji se crta u Illustratoru.",
    n: "Na uobičajenoj cSurvey ruti ne treba – KORAK 3c u 3N ga slaže sam.",
  },
  "4F": {
    t: "Fotografije ulaza",
    d: "Premještanje fotografija ulaza u mapu objekta i obrada na propisano ime i veličinu.",
    s: ["Povuci iz reda čekanja – ako ih ima.",
        "Obradi fotografije – preimenuje ih i smanjuje."],
    n: "Kvačica Samo plan pokaže što bi se dogodilo, bez ikakve promjene.",
  },
  "5O": {
    t: "Osobe i izjave",
    d: "Svaki autor nacrta mora imati potpisanu izjavu. Ovdje se provjerava ima li je i pokriva li ovaj objekt.",
    s: ["Izjave za ovaj objekt – autori odabranog objekta.",
        "Cijeli registar – tko nema izjavu i čije izjave nemaju osobu."],
  },
  "5D": {
    t: "Dosje",
    d: "Sve o objektu na jednom mjestu i odgovor je li spreman za predaju.",
    s: ["Prag 1 (SUE) i prag 2 (CroSpeleo) – zeleno znači spremno.",
        "BLOKIRA – mora se riješiti prije predaje.",
        "UPOZORENJE – provjeri, ali ne priječi predaju."],
    n: "Osvježi dosje nakon promjene u SB-u ili OSZ-u.",
  },
  "6P": {
    t: "Predaja",
    d: "Zadnji korak: isporuka u arhivske mape i upis u SB. Još nije napravljen – gumbi su samo prikaz.",
  },
  "osobe": {
    t: "Osobe · izjave",
    d: "Autori ovog objekta iz SB-a i stanje njihovih izjava.",
    s: ["✓ izjava pokriva ovaj objekt",
        "~ izjava postoji, ali ne pokriva ovaj objekt",
        "✗ nema izjave",
        "? osoba nije u registru osoba"],
    n: "Izjave su u !!Izjave za katastar RH na Driveu.",
  },
  "dosje-sources": {
    t: "Izvori",
    d: "Iz čega je dosje složen: SB, OSZ, izmjera, fotografije… ✓ znači prikupljeno, · još nije.",
  },
  "dosje-sb": {
    t: "SB red",
    d: "Podaci o ovom objektu kako stoje u SB-u. Ispravci idu ručno u Excel.",
  },

  // ── 0P udruge ──────────────────────────────────────────────────────
  "udruge": {
    t: "Udruge",
    d: "Popis speleoloških udruga i njihovih kratica, da alati prepoznaju različite zapise istog imena.",
    s: ["Upiši dio imena, kraticu ili mjesto."],
    n: "Udruga nedostaje ili je krivo zapisana? Upute su u README-u.",
  },

  // ── 3N Mapiranje simbola (mapping.js) ──────────────────────────────
  "map3n": {
    t: "Mapiranje simbola",
    d: "Kako TopoDroid simboli, linije i površine postaju cSurvey znakovi i kako nacrt izgleda.",
    s: ["Zadano vrijedi za sve objekte.",
        "Izmjena ovdje vrijedi samo za odabrani objekt – Spremi za SB <broj>.",
        "Nakon spremanja ponovi KORAK koji kartica gore navodi."],
    n: "Vrati na zadano briše prilagodbu ovog objekta.",
  },
  "map-theme": {
    t: "Tema",
    d: "Izgled znakova, linija i površina na nacrtu – u boji ili crno-bijelo.",
    n: "Bez teme nacrt koristi cSurveyev ugrađeni izgled.",
  },
  "map-symbols": {
    t: "Simboli, linije i površine",
    d: "Lijevo TopoDroidov alat, desno što od njega postaje u cSurveyu.",
    n: "Djeluje u KORAKU 1 – nakon izmjene ponovi KORAK 1.",
  },
  "map-centerline": {
    t: "Poligon",
    d: "Izgled poligona – linije između mjernih točaka – i oznaka točaka.",
    n: "Djeluje u KORAKU 2 – nakon izmjene ponovi KORAK 2.",
  },
  "map-sizes": {
    t: "Veličine i uvoz",
    d: "Veličine znakova i oznaka te postavke uvoza u cSurvey.",
    n: "Djeluje u KORAKU 2 – nakon izmjene ponovi KORAK 2.",
  },
};

// The closing line of every stage tab that has commands.
const HELP_ACTIONS = "Pokreni izvodi naredbu; „piše” znači da mijenja datoteke, pa najprije pita. Kopiraj daje istu naredbu za terminal.";
