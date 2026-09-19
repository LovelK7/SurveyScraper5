# -*- coding: utf-8 -*-
"""Compare a template with the .docx Google Docs gives back after a round-trip.

    python check_gdocs_roundtrip.py <original.docx> <from-google.docx>

How to produce the second file
------------------------------
1. Upload the template to Drive, open it with Google Docs.
2. File → Download → Microsoft Word (.docx).
3. Run this script over the pair.

What it checks — everything that would silently break the OSZ fetcher:

* checkbox markers   ``[ ]`` / ``[x]`` — count must match exactly
* hint markers       ``⟨ … ⟩`` — count must match; text may be re-wrapped
* table geometry     table count, rows per table, cells per row
* field labels       every label the template carries must still be present
* run fragmentation  how badly Docs split the text into runs (the fetcher must
                     join runs inside a paragraph before matching anything)
* leftovers          content controls, Wingdings symbols, floating tables

Anything reported as MISMATCH means the fetcher cannot treat the two files the
same way, and the template needs another pass.
"""
import argparse
import re
import sys
import zipfile

from lxml import etree

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:                # pragma: no cover
    pass

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'

BOX_RE = re.compile(r'\[\s*[xX✓✔]?\s*\]')
HINT_RE = re.compile(r'⟨[^⟩]*⟩')


def load(path):
    return etree.fromstring(zipfile.ZipFile(path).read('word/document.xml'))


def paragraphs(root):
    """(text, run_count) per paragraph, runs joined — as the fetcher must do."""
    out = []
    for p in root.iter(W + 'p'):
        runs = p.findall('.//' + W + 'r')
        text = ''.join(t.text or '' for t in p.iter(W + 't'))
        text = ' '.join(text.split())
        if text:
            out.append((text, len(runs)))
    return out


def tables(root):
    geometry = []
    for tbl in root.iter(W + 'tbl'):
        rows = tbl.findall(W + 'tr')
        geometry.append([len([c for c in tr if c.tag in (W + 'tc', W + 'sdt')]) for tr in rows])
    return geometry


def labels(root):
    """Cell texts that look like field labels (end with ':')."""
    found = []
    for tc in root.iter(W + 'tc'):
        text = ' '.join(''.join(t.text or '' for t in tc.iter(W + 't')).split())
        if text.endswith(':') and 1 < len(text) < 60:
            found.append(text)
    return found


def stats(root):
    paras = paragraphs(root)
    all_text = ' '.join(t for t, _ in paras)
    return {
        'paragraphs': len(paras),
        'boxes': len(BOX_RE.findall(all_text)),
        'ticked': len([m for m in BOX_RE.findall(all_text) if m.strip('[] ')]),
        'hints': len(HINT_RE.findall(all_text)),
        'tables': tables(root),
        'labels': labels(root),
        'sdt': len(list(root.iter(W + 'sdt'))),
        'sym': len(list(root.iter(W + 'sym'))),
        'floating': len(list(root.iter(W + 'tblpPr'))),
        'max_runs': max([n for _, n in paras], default=0),
        'total_runs': sum(n for _, n in paras),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('original')
    ap.add_argument('roundtrip')
    a = ap.parse_args()

    src, dst = stats(load(a.original)), stats(load(a.roundtrip))
    problems = 0

    def cmp(name, key, must_match=True):
        nonlocal problems
        ok = src[key] == dst[key]
        if not ok and must_match:
            problems += 1
        flag = 'OK      ' if ok else ('MISMATCH' if must_match else 'changed ')
        print('  %s %-14s original=%-6s google=%s' % (flag, name, src[key], dst[key]))

    print('== content that must survive ==')
    cmp('checkboxes', 'boxes')
    cmp('ticked boxes', 'ticked')
    cmp('hint markers', 'hints')
    cmp('paragraphs', 'paragraphs', must_match=False)

    print('\n== table geometry ==')
    if src['tables'] == dst['tables']:
        print('  OK       %d tables, identical row/cell counts' % len(src['tables']))
    else:
        problems += 1
        print('  MISMATCH tables: original %d, google %d' % (len(src['tables']), len(dst['tables'])))
        for i, (o, d) in enumerate(zip(src['tables'], dst['tables'])):
            if o != d:
                print('     table %d: rows %d→%d, cells %s → %s' % (i, len(o), len(d), o, d))

    print('\n== field labels ==')
    missing = [l for l in src['labels'] if l not in dst['labels']]
    if missing:
        problems += 1
        print('  MISMATCH %d label(s) lost:' % len(missing))
        for l in missing:
            print('     %s' % l)
    else:
        print('  OK       all %d labels present' % len(src['labels']))

    print('\n== leftovers that should be zero ==')
    for name, key in (('content controls', 'sdt'), ('Wingdings symbols', 'sym'), ('floating tables', 'floating')):
        for who, s in (('original', src), ('google  ', dst)):
            if s[key]:
                print('  !! %s still has %d %s' % (who, s[key], name))
    if not any(src[k] or dst[k] for k in ('sdt', 'sym', 'floating')):
        print('  OK       none in either file')

    print('\n== run fragmentation (fetcher must join runs per paragraph) ==')
    print('  runs total: original %d, google %d' % (src['total_runs'], dst['total_runs']))
    print('  worst paragraph: original %d runs, google %d runs' % (src['max_runs'], dst['max_runs']))
    if dst['total_runs'] > src['total_runs'] * 1.5:
        print('  note: Google split the text noticeably more — never match on a single w:r')

    print('\n%s' % ('PASS — the round-trip is loss-free for everything the fetcher reads'
                    if problems == 0 else 'FAIL — %d mismatch(es) above' % problems))


if __name__ == '__main__':
    main()
