# -*- coding: utf-8 -*-
"""Fill the OSZ template with a worked example so the layout can be eyeballed.

Data: SUE 811 "Piccolo Bertarelli" as recorded in the 2025 OSZ
(tests/test_input/811 in crospeleo-automation), extended with plausible
values for the fields the new template asks for and the 2025 document
did not carry (microclimate measurements, waste volume, entrance state).
"""
import copy
import shutil
import sys
import zipfile
from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'

SRC, DST = sys.argv[1], sys.argv[2]

zin = zipfile.ZipFile(SRC)
doc_xml = zin.read('word/document.xml')
root = etree.fromstring(doc_xml)
body = root.find(W + 'body')
tables = body.findall(W + 'tbl')


# ── helpers ──────────────────────────────────────────────────────────
def row_nodes(tbl, ri):
    tr = tbl.findall(W + 'tr')[ri]
    return [n for n in tr if n.tag in (W + 'tc', W + 'sdt')]


def first_run_rpr(tc):
    r = tc.find('.//' + W + 'r')
    if r is None:
        return None
    rpr = r.find(W + 'rPr')
    if rpr is None:
        return None
    rpr = copy.deepcopy(rpr)
    for bad in ('b', 'bCs', 'i', 'rStyle'):
        for el in rpr.findall(W + bad):
            rpr.remove(el)
    return rpr


def make_run(text, rpr):
    r = etree.SubElement(etree.Element(W + 'tmp'), W + 'r')
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = etree.SubElement(r, W + 't')
    t.text = text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return r


def fill_plain(tbl_i, row_i, cell_i, text, style_from=0):
    """Write text into a plain (non-control) table cell."""
    cells = row_nodes(tables[tbl_i], row_i)
    tc = cells[cell_i]
    rpr = first_run_rpr(cells[style_from]) if style_from is not None else None
    p = tc.find(W + 'p')
    if p is None:
        p = etree.SubElement(tc, W + 'p')
    for r in p.findall(W + 'r'):
        p.remove(r)
    p.append(make_run(text, rpr))


def _clear_placeholder(sdt):
    pr = sdt.find(W + 'sdtPr')
    if pr is not None:
        for el in pr.findall(W + 'showingPlcHdr'):
            pr.remove(el)
        # A plain-text control is single-paragraph unless multiLine is set;
        # writing a second w:p into it otherwise makes Word reject the file.
        txt = pr.find(W + 'text')
        if txt is not None:
            txt.set(W + 'multiLine', '1')
    # drop the grey PlaceholderText character style
    for rstyle in sdt.findall('.//' + W + 'rStyle'):
        if rstyle.get(W + 'val') == 'PlaceholderText':
            rstyle.getparent().remove(rstyle)


def fill_sdt(sdt, paragraphs, rpr=None):
    """Fill a plain-text content control with one or more paragraphs."""
    _clear_placeholder(sdt)
    content = sdt.find(W + 'sdtContent')
    inner_tc = content.find(W + 'tc')
    holder = inner_tc if inner_tc is not None else content
    ps = holder.findall(W + 'p')
    if ps:
        template_p = ps[0]
        # Take the paragraph mark's rPr (Arial 10 pt) rather than the grey
        # placeholder run's, so filled text renders as normal body text.
        base_rpr = rpr
        if base_rpr is None:
            ppr = template_p.find(W + 'pPr')
            mark_rpr = ppr.find(W + 'rPr') if ppr is not None else None
            if mark_rpr is not None:
                base_rpr = copy.deepcopy(mark_rpr)
                for bad in ('rStyle', 'color', 'b', 'bCs', 'i'):
                    for el in base_rpr.findall(W + bad):
                        base_rpr.remove(el)
        if base_rpr is None:
            base_rpr = first_run_rpr(inner_tc if inner_tc is not None else template_p)
        for extra in ps[1:]:
            holder.remove(extra)
        for r in template_p.findall(W + 'r'):
            template_p.remove(r)
        # One paragraph with <w:br/> separators: a plain-text control may
        # not contain a second w:p — Word rejects the file outright.
        run = make_run(paragraphs[0], base_rpr)
        for line in paragraphs[1:]:
            etree.SubElement(run, W + 'br')
            t = etree.SubElement(run, W + 't')
            t.text = line
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        template_p.append(run)
    else:  # inline run-level control
        rs = content.findall(W + 'r')
        # Style from the control's own rPr (what Word applies when the
        # operator types), NOT from the grey placeholder run.
        sdt_pr = sdt.find(W + 'sdtPr')
        base_rpr = sdt_pr.find(W + 'rPr') if sdt_pr is not None else None
        if base_rpr is None and rs:
            base_rpr = rs[0].find(W + 'rPr')
        if base_rpr is not None:
            base_rpr = copy.deepcopy(base_rpr)
            for bad in ('rStyle', 'color'):
                for el in base_rpr.findall(W + bad):
                    base_rpr.remove(el)
        for r in rs[1:]:
            content.remove(r)
        if rs:
            content.remove(rs[0])
        content.append(make_run(' '.join(paragraphs), base_rpr))


def cell_sdt(tbl_i, row_i, cell_i):
    node = row_nodes(tables[tbl_i], row_i)[cell_i]
    assert node.tag == W + 'sdt', 'not a cell-level control'
    return node


def inline_sdt(tbl_i, row_i, cell_i):
    tc = row_nodes(tables[tbl_i], row_i)[cell_i]
    for sdt in tc.iter(W + 'sdt'):
        pr = sdt.find(W + 'sdtPr')
        if pr is not None and pr.find(W + 'text') is not None:
            return sdt
    raise AssertionError('no text control in cell')


# ── checkboxes ───────────────────────────────────────────────────────
def checkbox_label(sdt):
    """Text that follows a checkbox control inside its paragraph."""
    p = sdt.getparent()
    while p is not None and p.tag != W + 'p':
        p = p.getparent()
    if p is None:
        return ''
    collected, seen = [], False
    for node in p:
        if node is sdt:
            seen = True
            continue
        if not seen:
            continue
        if node.tag == W + 'sdt':
            break
        if node.tag == W + 'r':
            collected.append(''.join(t.text or '' for t in node.findall(W + 't')))
    return ' '.join(''.join(collected).split()).strip()


def tick(labels):
    """Tick every checkbox whose trailing label is in `labels`."""
    hit = set()
    for sdt in root.iter(W + 'sdt'):
        pr = sdt.find(W + 'sdtPr')
        if pr is None or pr.find(W14 + 'checkbox') is None:
            continue
        label = checkbox_label(sdt)
        if label not in labels:
            continue
        chk = pr.find(W14 + 'checkbox')
        checked = chk.find(W14 + 'checked')
        if checked is None:
            checked = etree.SubElement(chk, W14 + 'checked')
        checked.set(W14 + 'val', '1')
        state = chk.find(W14 + 'checkedState')
        char = state.get(W14 + 'val') if state is not None else '0052'
        font = state.get(W14 + 'font') if state is not None else 'Wingdings 2'
        for sym in sdt.findall('.//' + W + 'sym'):
            sym.set(W + 'char', 'F0' + char[-2:])
            sym.set(W + 'font', font)
        hit.add(label)
    missing = set(labels) - hit
    if missing:
        print('  !! checkbox label not found:', missing)


# ── content ──────────────────────────────────────────────────────────
POLOZAJ = [
    u"Ponor se nalazi 20 m od ceste Rašpor – Račja Vas, na polju jugoistočno od sela Rašpor i "
    u"230 m od ulaza u Jamu kod Rašpora. Leži na dnu plitke vrtače u koritu povremenog toka, "
    u"okolica je travnata i ulaz se u pukotini gotovo ne primjećuje dok se ne priđe vrtači.",
    u"Pristup: cestom Rašpor – Račja Vas do polja, parkirati uz cestu 20 m od objekta. Vrtači "
    u"prići sa sjeveroistočne strane i hodati po koritu do pukotinastog ulaza. Od automobila "
    u"do ulaza je 2 minute hoda po ravnom, prohodnom terenu.",
]

OPIS = [
    u"Ponor je sitasti, lijevkastog oblika, s dvije pukotine koje sijeku vrtaču u smjeru SZ–JI. "
    u"Prema JI pukotina nije prolazna (Piccolissimo Bertarelli), dok je pukotina na SZ strani "
    u"proširena do dimenzija speleološkog objekta. Ulaz je pukotinast, širine 0,4 m i visine 1 m, "
    u"zabarikadiran granjem i kamenjem radi sprječavanja naplavljivanja.",
    u"Pukotina ima koljenasti zavoj udesno, zatim ponovo ulijevo, i postupno dobiva na dubini. "
    u"Cijelom je dužinom proširivana. Dno je suženje u pukotini, na 4 m dubine, s perspektivom "
    u"nastavka. Ukupna duljina iznosi 9 m, horizontalna 8 m.",
    u"Za obilazak nije potrebna vertikalna oprema; dovoljna su dva speleologa i osnovna oprema, "
    u"uz opremu za proširivanje ako se nastavlja rad na suženju.",
]

GEO = [
    u"Stijene vrtače i pukotine su u flišu/laporu. Na ulazu se vidi ljuskavost, dublje je stijena "
    u"kompaktna. Pukotine se pružaju SZ–JI, s padom oko 70° prema JI.",
    u"Prema trenutno viđenoj situaciji, pukotina predstavlja mjesto prelijevanja visokih voda koje "
    u"sitasti ponor ne uspijeva progutati — vidljivo po granju i naplavljenom materijalu koji "
    u"zaostaje po stijenama i u vrtači. Objekt djeluje kao povremeni ponor u zaleđu izvora u dolini.",
]

MIKRO = [
    u"Mjerna točka: 5 m od ulaza, 10.5.2025. u 11:30, temperatura zraka 9,8 °C, relativna vlažnost "
    u"92 %, temperatura vode nije mjerena, instrument Testo 175-H1.",
    u"Strujanje zraka: pukotina se ponaša kao gornji ulaz potencijalnog sustava — zimi izbacuje "
    u"zrak (smjer prema van), povremeno. Jednako je primijećeno i na pukotini Piccolissimo Bertarelli.",
    u"Snijeg i led: nije zabilježeno ni u jednom posjetu.",
    u"Povišen CO₂: nije zamijećen niti mjeren.",
]

BIO = [
    u"Nije uzorkovano. Golim okom opaženo nekoliko jedinki paukova i dvojenoga u ulaznoj pukotini; "
    u"šišmiši nisu opaženi, guana nema.",
]

ARHEO = [u"Nema opaženih nalaza."]

OPASNOSTI = [
    u"Stijena je nakon ulaznog dijela kompaktna, dno bez trusnog materijala — u samom objektu nema "
    u"opasnosti od odrona.",
    u"Nakon jakih kiša pukotina prima vodu prelijevanjem iz korita i cijeli prostor može se brzo "
    u"potopiti, pa se ulazak ne preporučuje za visokih voda (otud kvačica gore). Ulazna pukotina je "
    u"uska (0,4 m) pa je za izlazak potrebna pomoć druge osobe.",
]

ZAGADENOST = [
    u"Na dnu vrtače, oko 3 m od ulaza, zakopan je stari šparhet, a pod granjem i humusom vjerojatno "
    u"ima još kućnog otpada; procijenjena zapremnina manja od 1 m³. Objekt nije čišćen.",
    u"Ponor je 20 m od ceste Rašpor – Račja Vas, pa je ugrožen otjecanjem s prometnice i "
    u"odlaganjem otpada s ceste. U neposrednoj okolici nema šumarskih ni građevinskih zahvata.",
    u"Objekt se posjećuje neregulirano, uglavnom od strane speleologa. Recentnih ljudskih ostataka nema.",
]

PERSPEKTIVA = [
    u"Nastavak se očekuje na dnu, u suženju pukotine na 4 m dubine — potrebno je proširivanje, uz "
    u"osnovnu opremu za kopanje i dva do tri speleologa.",
    u"Postoje naznake o vezi s Neprospavanim kanalom Jame kod Rašpora: naplavina, pružanje pukotine "
    u"i cirkulacija zraka upućuju na isti sustav.",
]

POVIJEST = [
    u"SU Estavela započela je kopanje 2014. (Goran Nikolić i Lovel Kukuljan), no moguće je da je "
    u"bilo i ranijih pokušaja (Ivan Glavaš, SU Spelunka). Rad se nastavio 2023. (Ivan Glavaš, "
    u"Dino Grozić, Luka Peloza), a 2025. je objekt po prvi put nacrtan.",
    u"Ime je izvedeno iz naziva susjedne Jame kod Rašpora (Abisso Bertarelli); raniji radni naziv "
    u"bio je Ponor kraj Rašpora.",
]

LITERATURA = [
    u"Šikić, D.; Pleničar, M.; Šparica, M., (1972): Osnovna geološka karta SFRJ, list Ilirska "
    u"Bistrica, 1:100 000. Savezni geološki zavod, Beograd.",
]

NAPOMENE = [
    u"OGLEDNI PRIMJER — ispuna služi samo za provjeru izgleda predloška.",
    u"Ulaz je zabarikadiran granjem i kamenjem kako bi se spriječilo naplavljivanje i zatrpavanje "
    u"ulaza vodom.",
]

# ── fill: header + identification ────────────────────────────────────
fill_plain(0, 0, 1, u'811')
fill_plain(0, 1, 1, u'051-683')

fill_plain(1, 0, 1, u'Piccolo Bertarelli')
fill_plain(1, 1, 1, u'Ponor kraj Rašpora')
fill_plain(1, 3, 1, u'Istarska')
fill_plain(1, 4, 1, u'Lanišće')
fill_plain(1, 5, 1, u'Rašpor')
fill_plain(1, 6, 1, u'Ćićarija')

# coordinates + entrance
fill_sdt(cell_sdt(2, 2, 2), [u'310620'])
fill_sdt(cell_sdt(2, 2, 4), [u'5035782'])
fill_plain(2, 4, 2, u'680', style_from=1)
fill_plain(2, 4, 4, u'LIDAR', style_from=3)
fill_plain(2, 5, 2, u'1', style_from=1)
fill_plain(2, 5, 4, u'LIDAR', style_from=3)
fill_plain(2, 6, 2, u'0,4', style_from=1)
fill_plain(2, 6, 4, u'1', style_from=3)
fill_sdt(cell_sdt(2, 9, 2), [u'/'])

# narrative blocks
fill_sdt(cell_sdt(3, 0, 1), POLOZAJ)
fill_sdt(cell_sdt(4, 7, 0), OPIS)
fill_sdt(cell_sdt(5, 2, 0), GEO)
fill_sdt(cell_sdt(5, 5, 0), MIKRO)
fill_sdt(cell_sdt(5, 7, 0), BIO)
fill_sdt(inline_sdt(5, 9, 0), ARHEO)
fill_sdt(inline_sdt(5, 11, 0), OPASNOSTI)
fill_sdt(inline_sdt(6, 2, 0), ZAGADENOST)
fill_sdt(cell_sdt(4, 9, 0), PERSPEKTIVA)
fill_sdt(inline_sdt(6, 4, 0), POVIJEST)
fill_sdt(inline_sdt(6, 6, 0), LITERATURA)
fill_sdt(cell_sdt(6, 21, 1), NAPOMENE)

# dimensions
fill_plain(4, 3, 0, u'9', style_from=None)
fill_plain(4, 3, 1, u'8', style_from=None)
fill_plain(4, 3, 2, u'4', style_from=None)
fill_plain(4, 3, 3, u'4', style_from=None)

# survey metadata
fill_plain(6, 8, 1, u'10.05.2025.')
fill_plain(6, 9, 1, u'SU Spelunka, SU Estavela')
fill_plain(6, 11, 1, u'Luka Peloza, Tin Tepavac, Lovel Kukuljan, Ivana Dujmović, Erik Lukić,')
fill_plain(6, 12, 1, u'Sarah Klešin, Nina Grozić, Natalija Malbašić, Matko Jasprica, Vedran Novak,')
fill_plain(6, 13, 1, u'Venio Fabijančić')
fill_plain(6, 14, 1, u'Lovel Kukuljan')   # Crtali
fill_plain(6, 15, 1, u'Lovel Kukuljan')   # Mjerili
fill_plain(6, 17, 1, u'Lovel Kukuljan')   # Nacrt uredio
fill_plain(6, 18, 1, u'Lovel Kukuljan, Ivana Dujmović, Luka Peloza, Venio Fabijančić')
fill_plain(6, 19, 1, u'Lovel Kukuljan')
fill_plain(6, 23, 1, u'Zagrebu', style_from=0)
fill_plain(6, 23, 3, u'17.05.2025.', style_from=2)
fill_plain(6, 23, 5, u'Lovel Kukuljan', style_from=4)

# ── checkboxes ───────────────────────────────────────────────────────
tick({
    u'smišljeno prema toponimu',          # Podrijetlo imena
    u'zatvoren granjem/balvanima',        # Stanje ulaza
    u'špilja',                            # Vrsta objekta
    u'povremeni tok',                     # Hidrološka karakteristika
    u'povremeni ponor',                   # Hidrogeološka funkcija
    u'potrebno proširivanje',             # Perspektiva daljnjeg istraživanja
    u'nastavlja se',
    u'mogućnost brzog potapanja kanala',  # Prirodne opasnosti
    u'onečišćenje otpadom',               # Antropogene opasnosti i utjecaj
})

# ── save ─────────────────────────────────────────────────────────────
new_xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
shutil.copy(SRC, DST)
zin2 = zipfile.ZipFile(SRC)
zout = zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED)
for item in zin2.infolist():
    data = zin2.read(item.filename)
    if item.filename == 'word/document.xml':
        data = new_xml
    zout.writestr(item, data)
zout.close()
print('written', DST)
