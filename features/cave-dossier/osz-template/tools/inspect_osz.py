# -*- coding: utf-8 -*-
"""Structural inspection of an OSZ .docx.

    python inspect_osz.py <template.docx> [--mode layout|index|controls] [-o out.txt]

Modes
-----
layout    document order: paragraphs, table rows, content controls inline
index     addressable map  table[t].row[r].cell[c]  — coordinates for make_mockup.py
controls  every content control: checkbox groups with labels, text-control flags

Word content controls (``w:sdt``) are invisible to python-docx, so everything
here works on ``word/document.xml`` through lxml.
"""
import argparse
import io
import sys
import zipfile

from lxml import etree

try:                                  # Croatian diacritics on a cp1250 console
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:                # pragma: no cover — Python < 3.7
    pass

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'


# ── shared helpers ───────────────────────────────────────────────────
def load(path):
    return etree.fromstring(zipfile.ZipFile(path).read('word/document.xml'))


def sdt_info(sdt):
    pr = sdt.find(W + 'sdtPr')
    kind, checked, multi = 'sdt', None, None
    if pr is not None:
        if pr.find(W14 + 'checkbox') is not None:
            kind = 'CHK'
            c = pr.find(W14 + 'checkbox/' + W14 + 'checked')
            checked = c is not None and c.get(W14 + 'val') in ('1', 'true')
        elif pr.find(W + 'text') is not None:
            kind = 'TXT'
            multi = pr.find(W + 'text').get(W + 'multiLine')
        elif pr.find(W + 'dropDownList') is not None:
            kind = 'DDL'
    alias = pr.find(W + 'alias') if pr is not None else None
    tag = pr.find(W + 'tag') if pr is not None else None
    rpr = pr.find(W + 'rPr') if pr is not None else None
    sz = rpr.find(W + 'sz') if rpr is not None else None
    fonts = rpr.find(W + 'rFonts') if rpr is not None else None
    return {
        'kind': kind,
        'checked': checked,
        'multiLine': multi,
        'plc': pr is not None and pr.find(W + 'showingPlcHdr') is not None,
        'alias': alias.get(W + 'val') if alias is not None else None,
        'tag': tag.get(W + 'val') if tag is not None else None,
        'font': fonts.get(W + 'ascii') if fonts is not None else None,
        'sz': sz.get(W + 'val') if sz is not None else None,
        'level': 'cell' if sdt.find(W + 'sdtContent/' + W + 'tc') is not None else 'inline',
        'text': ''.join(t.text or '' for t in sdt.iter(W + 't')).strip(),
    }


def _outside_sdt(node, stop_tag):
    anc = node.getparent()
    while anc is not None and anc.tag != stop_tag:
        if anc.tag == W + 'sdt':
            return False
        anc = anc.getparent()
    return True


def para_text(p, mark_controls=True):
    parts = []
    for node in p.iter():
        if node.tag == W + 'sdt':
            i = sdt_info(node)
            if not mark_controls:
                parts.append(i['text'])
            elif i['kind'] == 'CHK':
                parts.append('[x] ' if i['checked'] else '[ ] ')
            else:
                parts.append('{%s:%s:%s}' % (i['kind'], 'PLC' if i['plc'] else 'VAL', i['text'][:70]))
        elif node.tag == W + 't' and _outside_sdt(node, W + 'p'):
            parts.append(node.text or '')
    return ' '.join(''.join(parts).split()).strip()


def cell_text(tc):
    return ' / '.join(x for x in (para_text(p) for p in tc.findall(W + 'p')) if x)


def row_nodes(tr):
    return [n for n in tr if n.tag in (W + 'tc', W + 'sdt')]


def node_text(node):
    """Text of a row member — a plain cell or a cell-level control."""
    if node.tag == W + 'sdt':
        i = sdt_info(node)
        inner = node.find('.//' + W + 'tc')
        body = cell_text(inner) if inner is not None else i['text']
        return '<<%s %s>> %s' % (i['kind'], 'PLC' if i['plc'] else 'VAL', body)
    return cell_text(node)


# ── modes ────────────────────────────────────────────────────────────
def mode_layout(root, out):
    def walk(el, depth=0):
        pad = '  ' * depth
        for ch in el:
            if ch.tag == W + 'p':
                t = para_text(ch)
                if t:
                    out.write('%sP  %s\n' % (pad, t))
            elif ch.tag == W + 'tbl':
                out.write('%s--- TABLE ---\n' % pad)
                for tr in ch.findall(W + 'tr'):
                    line = ' || '.join(node_text(n) for n in row_nodes(tr))
                    if line.strip(' |'):
                        out.write('%sR  %s\n' % (pad, line))
                out.write('%s--- /TABLE ---\n' % pad)
            else:
                walk(ch, depth)
    walk(root.find(W + 'body'))


def mode_index(root, out):
    for ti, tbl in enumerate(root.find(W + 'body').findall(W + 'tbl')):
        out.write('\n===== TABLE %d =====\n' % ti)
        for ri, tr in enumerate(tbl.findall(W + 'tr')):
            cells = row_nodes(tr)
            out.write('  row %-2d : %s\n' % (
                ri, ' | '.join('[%d]%r' % (ci, node_text(c)[:70]) for ci, c in enumerate(cells))))


def checkbox_label(sdt):
    """Label text following a checkbox inside its paragraph."""
    p = sdt.getparent()
    while p is not None and p.tag != W + 'p':
        p = p.getparent()
    if p is None:
        return ''
    got, seen = [], False
    for node in p:
        if node is sdt:
            seen = True
            continue
        if not seen:
            continue
        if node.tag == W + 'sdt':
            break
        if node.tag == W + 'r':
            got.append(''.join(t.text or '' for t in node.findall(W + 't')))
    return ' '.join(''.join(got).split()).strip()


def checkbox_groups(root):
    """[(anchor_label, [(label, checked), ...]), ...] grouped by table row."""
    groups, current, prev_row = [], None, object()
    for sdt in root.iter(W + 'sdt'):
        pr = sdt.find(W + 'sdtPr')
        if pr is None or pr.find(W14 + 'checkbox') is None:
            continue
        tc = sdt.getparent()
        while tc is not None and tc.tag != W + 'tc':
            tc = tc.getparent()
        row = tc.getparent() if tc is not None else None
        if row is not prev_row:
            current = (_anchor_for(row), [])
            groups.append(current)
            prev_row = row
        c = pr.find(W14 + 'checkbox/' + W14 + 'checked')
        current[1].append((checkbox_label(sdt), c is not None and c.get(W14 + 'val') in ('1', 'true')))
    return groups


def _anchor_for(row):
    """Nearest preceding row text — the group's heading."""
    if row is None:
        return '?'
    prev = row.getprevious()
    while prev is not None:
        if prev.tag == W + 'tr':
            txt = ' '.join(node_text(n) for n in row_nodes(prev)).strip(' |')
            txt = txt.replace('[ ]', '').strip()
            if txt and '<<' not in txt:
                return ' '.join(txt.split())[:60]
        prev = prev.getprevious()
    return '?'


def mode_controls(root, out):
    out.write('== CHECKBOX GROUPS ==\n')
    total = 0
    for anchor, boxes in checkbox_groups(root):
        out.write('\n%s  (%d)\n' % (anchor, len(boxes)))
        for label, checked in boxes:
            out.write('   [%s] %s\n' % ('x' if checked else ' ', label))
        total += len(boxes)
    out.write('\n== TEXT CONTROLS ==\n')
    n = 0
    for sdt in root.iter(W + 'sdt'):
        i = sdt_info(sdt)
        if i['kind'] != 'TXT':
            continue
        n += 1
        out.write('%02d %-6s multiLine=%-4s tag=%-22s font=%-6s sz=%-4s %r\n' % (
            n, i['level'], i['multiLine'], i['tag'], i['font'] or '-', i['sz'] or '-', i['text'][:55]))
    out.write('\nTOTAL: %d checkboxes, %d text controls\n' % (total, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('--mode', default='controls', choices=['layout', 'index', 'controls'])
    ap.add_argument('-o', '--out')
    a = ap.parse_args()
    root = load(a.docx)
    out = io.open(a.out, 'w', encoding='utf-8') if a.out else io.StringIO()
    {'layout': mode_layout, 'index': mode_index, 'controls': mode_controls}[a.mode](root, out)
    if a.out:
        out.close()
        print('written', a.out)
    else:
        print(out.getvalue())


if __name__ == '__main__':
    main()
