# -*- coding: utf-8 -*-
"""Flatten a Word OSZ template into a Google-Docs-safe .docx.

    python flatten_for_gdocs.py <master.docx> <out.docx>

Google Docs does not support Word content controls (``w:sdt``).  On import it
throws the control away and keeps whatever was inside it, which means:

* a checkbox control becomes its raw ``Wingdings 2`` glyph — no longer tickable,
  and rendered as a random box/character because Docs has no Wingdings;
* a plain-text control's *placeholder* becomes ordinary grey text, and the
  moment the recorder saves, that hint is real content;
* positioned (floating) tables and Word's content-control layout hints drift,
  which pushes rows onto the wrong page.

This script produces a version with no content controls at all, which renders
and behaves identically in Word, Google Docs and LibreOffice:

1. every checkbox control  → literal ``[ ]`` text (tick by typing an x: ``[x]``)
2. every text control      → hint wrapped in ``⟨ … ⟩`` so the fetcher can drop any
                             field the recorder left untouched.  Deliberately in
                             plain black: with no content control to reset the
                             formatting, whatever the hint wears is what the
                             recorder's answer inherits when they type over it.
3. floating tables         → un-anchored (``w:tblpPr`` removed)
4. embedded fonts          → dropped (Docs ignores them; ~8.5 MB of the file)
5. footer                  → one line pointing at the Word original (``--no-note``)

**Both versions stay in use.**  The Word original with real content controls is
the recommended one — click-to-tick checkboxes, placeholders that vanish on
typing, no stray hint text.  This flattened variant is the fallback for people
who fill the zapisnik in Google Docs from Drive.

Idempotent: run it on an already-flattened file that was hand-edited in Word and
it only re-applies the fixes (plain hints, no embedded fonts, footer note).
Passing the same path as src and dst is safe.
"""
import argparse
import copy
import os
import re
import zipfile

from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
XMLSPACE = '{http://www.w3.org/XML/1998/namespace}space'

UNCHECKED = '[ ]'
HINT_OPEN, HINT_CLOSE = '⟨ ', ' ⟩'          # ⟨ … ⟩


def make_run(text, rpr):
    r = etree.Element(W + 'r')
    if rpr is not None:
        rpr = copy.deepcopy(rpr)
        # Hints are deliberately NOT grey or italic.  Without a content
        # control there is nothing to reset the formatting when the recorder
        # types over the hint — whatever the hint wears, the answer inherits.
        for bad in ('rStyle', 'color', 'i', 'iCs'):
            for el in rpr.findall(W + bad):
                rpr.remove(el)
        r.append(rpr)
    t = etree.SubElement(r, W + 't')
    t.text = text
    t.set(XMLSPACE, 'preserve')
    return r


def sdt_kind(sdt):
    pr = sdt.find(W + 'sdtPr')
    if pr is None:
        return None, None
    if pr.find(W14 + 'checkbox') is not None:
        chk = pr.find(W14 + 'checkbox/' + W14 + 'checked')
        return 'checkbox', (chk is not None and chk.get(W14 + 'val') in ('1', 'true'))
    if pr.find(W + 'text') is not None:
        return 'text', pr.find(W + 'showingPlcHdr') is not None
    return 'other', None


def flatten_document(root, stats):
    """Replace every w:sdt with plain content, innermost first."""
    for sdt in list(root.iter(W + 'sdt'))[::-1]:
        parent = sdt.getparent()
        if parent is None:
            continue
        pr = sdt.find(W + 'sdtPr')
        content = sdt.find(W + 'sdtContent')
        if content is None:
            parent.remove(sdt)
            continue
        kind, flag = sdt_kind(sdt)
        rpr = pr.find(W + 'rPr') if pr is not None else None

        if kind == 'checkbox':
            box = '[x]' if flag else UNCHECKED
            parent.replace(sdt, make_run(box, rpr))
            stats['checkbox'] += 1
            continue

        if kind == 'text':
            text = ''.join(t.text or '' for t in content.iter(W + 't')).strip()
            text = re.sub(r'\s+', ' ', text)
            # Only an untouched placeholder becomes a ⟨ … ⟩ hint; a value the
            # recorder actually typed is carried over verbatim.
            if flag and text:
                text = HINT_OPEN + text + HINT_CLOSE
            inner_tc = content.find(W + 'tc')
            if inner_tc is not None:
                # cell-level control: unwrap the w:tc back into the row
                paras = inner_tc.findall(W + 'p')
                if paras:
                    p = paras[0]
                    keep = [copy.deepcopy(r) for r in p.findall(W + 'r')] if not flag else []
                    for r in p.findall(W + 'r'):
                        p.remove(r)
                    if flag:
                        if text:
                            p.append(make_run(text, rpr))
                    else:
                        for r in keep:          # preserve line breaks in filled text
                            p.append(r)
                parent.replace(sdt, inner_tc)
                stats['text_cell'] += 1
            else:
                run = make_run(text, rpr) if text else None
                if run is not None:
                    parent.replace(sdt, run)
                else:
                    parent.remove(sdt)
                stats['text_inline'] += 1
            continue

        # any other control: keep its content, drop the wrapper
        idx = parent.index(sdt)
        for child in list(content):
            parent.insert(idx, child)
            idx += 1
        parent.remove(sdt)
        stats['other'] += 1


def plainify_hints(root, stats):
    """Strip colour/italic from ⟨ … ⟩ hint text.

    Runs idempotently on an already-flattened file, so a variant that was
    hand-edited in Word can be fixed in place without regenerating it.
    """
    for p in root.iter(W + 'p'):
        text = ''.join(t.text or '' for t in p.iter(W + 't'))
        if HINT_OPEN.strip() not in text:
            continue
        for r in p.findall(W + 'r'):
            rpr = r.find(W + 'rPr')
            if rpr is None:
                continue
            for bad in ('color', 'i', 'iCs', 'rStyle'):
                for el in rpr.findall(W + bad):
                    rpr.remove(el)
                    stats['hints_plainified'] += 1


FOOTER_NOTE = (
    'Inačica prilagođena Google Docsu. Ako zapisnik ispunjavaš u Wordu, '
    'koristi izvornu inačicu s poljima za unos.'
)


def add_footer_note(parts, note=FOOTER_NOTE):
    """Append a one-line pointer to the Word original in the page footer."""
    part = 'word/footer1.xml'
    if part not in parts:
        return False
    root = etree.fromstring(parts[part])
    body = root
    existing = body.findall(W + 'p')
    if any(note[:30] in ''.join(t.text or '' for t in p.iter(W + 't')) for p in existing):
        return False                      # already there — keep idempotent
    p = etree.SubElement(body, W + 'p')
    ppr = etree.SubElement(p, W + 'pPr')
    jc = etree.SubElement(ppr, W + 'jc')
    jc.set(W + 'val', 'center')
    rpr = etree.SubElement(etree.Element(W + 'tmp'), W + 'rPr')
    fonts = etree.SubElement(rpr, W + 'rFonts')
    for attr in ('ascii', 'hAnsi', 'cs'):
        fonts.set(W + attr, 'Arial')
    sz = etree.SubElement(rpr, W + 'sz')
    sz.set(W + 'val', '14')               # 7 pt
    szcs = etree.SubElement(rpr, W + 'szCs')
    szcs.set(W + 'val', '14')
    p.append(make_run(note, rpr))
    parts[part] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return True


def unfloat_tables(root, stats):
    for tblpr in root.iter(W + 'tblPr'):
        pos = tblpr.find(W + 'tblpPr')
        if pos is not None:
            tblpr.remove(pos)
            stats['unfloated'] += 1


def drop_embedded_fonts(names, parts, stats):
    """Remove word/fonts/*.odttf, their relationships and the embed refs."""
    font_parts = [n for n in names if n.startswith('word/fonts/')]
    if not font_parts:
        return names
    stats['fonts_dropped'] = len(font_parts)

    if 'word/fontTable.xml' in parts:
        ft = etree.fromstring(parts['word/fontTable.xml'])
        for tag in ('embedRegular', 'embedBold', 'embedItalic', 'embedBoldItalic'):
            for el in list(ft.iter(W + tag)):
                el.getparent().remove(el)
        parts['word/fontTable.xml'] = etree.tostring(
            ft, xml_declaration=True, encoding='UTF-8', standalone=True)

    rels = 'word/_rels/fontTable.xml.rels'
    if rels in parts:
        rt = etree.fromstring(parts[rels])
        for el in list(rt):
            if 'font' in (el.get('Target') or ''):
                rt.remove(el)
        parts[rels] = etree.tostring(rt, xml_declaration=True, encoding='UTF-8', standalone=True)

    if 'word/settings.xml' in parts:
        st = etree.fromstring(parts['word/settings.xml'])
        for tag in ('embedTrueTypeFonts', 'embedSystemFonts', 'saveSubsetFonts'):
            for el in list(st.iter(W + tag)):
                el.getparent().remove(el)
        parts['word/settings.xml'] = etree.tostring(
            st, xml_declaration=True, encoding='UTF-8', standalone=True)

    ct = '[Content_Types].xml'
    if ct in parts:
        c = etree.fromstring(parts[ct])
        for el in list(c):
            if (el.get('PartName') or '').startswith('/word/fonts/'):
                c.remove(el)
        parts[ct] = etree.tostring(c, xml_declaration=True, encoding='UTF-8', standalone=True)

    return [n for n in names if not n.startswith('word/fonts/')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--keep-fonts', action='store_true')
    ap.add_argument('--no-note', action='store_true',
                    help='skip the footer line pointing at the Word original')
    a = ap.parse_args()

    zin = zipfile.ZipFile(a.src)
    names = zin.namelist()
    parts = {n: zin.read(n) for n in names}
    infos = list(zin.infolist())
    zin.close()
    stats = {'checkbox': 0, 'text_cell': 0, 'text_inline': 0, 'other': 0,
             'unfloated': 0, 'fonts_dropped': 0, 'hints_plainified': 0}

    for part in ('word/document.xml', 'word/footer1.xml', 'word/header1.xml'):
        if part not in parts:
            continue
        root = etree.fromstring(parts[part])
        flatten_document(root, stats)
        unfloat_tables(root, stats)
        plainify_hints(root, stats)
        parts[part] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    noted = False if a.no_note else add_footer_note(parts)

    if not a.keep_fonts:
        names = drop_embedded_fonts(names, parts, stats)

    tmp = a.dst + '.tmp'
    zout = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
    for item in infos:
        if item.filename in names:
            zout.writestr(item, parts[item.filename])
    zout.close()
    os.replace(tmp, a.dst)                # safe when dst == src (in-place fix)

    print('written %s' % a.dst)
    print('  checkboxes flattened : %d' % stats['checkbox'])
    print('  text controls        : %d cell-level, %d inline' % (stats['text_cell'], stats['text_inline']))
    print('  other controls       : %d' % stats['other'])
    print('  tables un-anchored   : %d' % stats['unfloated'])
    print('  hint runs de-styled  : %d' % stats['hints_plainified'])
    print('  footer note          : %s' % ('added' if noted else 'not added'))
    print('  embedded fonts kept  : %s' % ('yes' if a.keep_fonts else 'no (%d parts dropped)' % stats['fonts_dropped']))


if __name__ == '__main__':
    main()
