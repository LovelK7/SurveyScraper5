# -*- coding: utf-8 -*-
"""Check an OSZ template against what SpeleoFlow / CroSpeleo expect.

    python check_conformance.py <template.docx> [--crospeleo ../../../../crospeleo-automation]

Three checks:

1. **Checkbox vocabularies** — every group in the template is matched against the
   CroSpeleo controlled vocab (transcribed from
   ``docs/ui_reference/**/fields_inventory.md`` in the crospeleo-automation
   repo).  Reports labels that CroSpeleo does not know (would fail the tick)
   and vocab entries the template omits.
2. **Field headings** — every row label is run through ``OSZParser._canonical_key``
   so heading renames that would silently drop a section surface immediately.
   Skipped when the crospeleo-automation checkout is not found.
3. **Control hygiene** — narrative controls that cannot hold paragraphs
   (no ``multiLine``), controls with no font size, and controls with no ``w:tag``.

Exit code is 0 always: this is a report, not a gate.
"""
import argparse
import os
import sys

try:                                  # Croatian diacritics on a cp1250 console
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:                # pragma: no cover — Python < 3.7
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_osz import W, load, checkbox_groups, node_text, row_nodes, sdt_info  # noqa: E402

# ── CroSpeleo controlled vocabularies ────────────────────────────────
# Source: crospeleo-automation docs/ui_reference/{01_osnovni_podaci_tab,
# 02_opazanja_tab}/fields_inventory.md (screenshot-confirmed 2026-05-10)
# and services/observation_mappings.py.
VOCAB = {
    'Podrijetlo imena': {
        'nepoznato podrijetlo', 'preuzeto iz literature', 'preuzeto kao lokalni naziv',
        'preuzeto sa karte', 'smišljeno novo', 'smišljeno prema toponimu',
    },
    'Stanje ulaza': {
        'horizontalne rešetke', 'kameni zid', 'kaptiran', 'ograda', 'puna vrata',
        'vertikalne rešetke', 'zaključan', 'zatrpan otpadom', 'zatrpan sedimentom/stijenama',
        'zatvoren granjem/balvanima',
    },
    'Hidrološka karakteristika': {
        'nakapnica/prokapnica', 'potopljen', 'povremena stajaća voda', 'povremeni tok',
        'povremeno potopljen', 'stalna stajaća voda', 'stalni tok', 'suh',
    },
    'Hidrogeološka funkcija': {
        'anhijalini objekt', 'estavela', 'morski objekt', 'nema', 'povremeni izvor',
        'povremeni ponor', 'protočan objekt', 'stalni izvor', 'stalni ponor', 'vrulja',
    },
    'Perspektiva daljnjeg istraživanja': {
        'moguć nastavak u slučaju topljenja ledenog čepa', 'nastavlja se',
        'nastavlja se penjanjem', 'nastavlja se preko vodenog tijela',
        'nastavlja se prečkanjem', 'nastavlja se provlačenjem', 'nastavlja se spuštanjem',
        'nije poznato', 'potpuno istražen', 'potrebno proširivanje', 'potrebno ronjenje',
        'potrebno ukloniti prepreke (eksplozivne naprave, otpad, strvine, kamenja...)',
    },
    'Opasnosti': {
        'divlje životinje', 'električni vodovi', 'krušljive stijene', 'lažno dno', 'led',
        'minski sumnjivo područje u kojem je objekt', 'minsko-eksplozivna sredstva',
        'mogućnost brzog potapanja kanala', 'mogućnost urušavanja ili odrona',
        'opasni otpad', 'opasni ulaz', 'otpad u objektu', 'povišena koncentracija CO2',
    },
    'Antropogene aktivnosti': {
        'turističke aktivnosti', 'šumarske aktivnosti',
        'eksploatacija mineralnih sirovina (kamenolomi, rudnici, …)', 'gradnja suhozida',
        'iskop sedimenta/sonda',
        'fizička devastacija (npr. uništavanje sigovine, grafiti, paljenje)',
        'crpljenje vode/bunara', 'hidrotehnički zahvati', 'ilegalne zamke za faunu',
        'skladištenje dobara', 'vojne svrhe', 'upotreba za sklonište',
        'građevinski radovi (npr. izgradnja prometnica, građevina, ...)',
        'religijski obredi', 'onečišćenje otpadom',
    },
    'Prisutnost snijega i leda': {
        'led - da', 'led - ne', 'led - privremeno', 'led - stalno',
        'snijeg - da', 'snijeg - ne', 'snijeg - privremeno', 'snijeg - stalno',
    },
}

# Vocab entries whose absence from the template is a deliberate decision
# rather than a gap.  Keyed by "<vocab group>|<label>".
ACCEPTED_OMISSIONS = {
    'Opasnosti|minsko-eksplozivna sredstva': 'moved to the Antropogene group',
    'Opasnosti|otpad u objektu': 'covered by Antropogene "onečišćenje otpadom"',
}

# Groups the template deliberately keeps as a subset — reported as one line
# instead of a wall of "missing" entries.
SUBSET_BY_DESIGN = {
    'Antropogene aktivnosti': 'only onečišćenje otpadom kept (decision 2026-08-23: 15 labels too many for the form)',
    'Prisutnost snijega i leda': 'presence only (snijeg / led); permanence stays in the Mikroklimatski prose',
}

# Template labels that do not appear verbatim in a CroSpeleo vocab but have a
# known mapping rule.  Reported as "mapped", not as unknown labels.
MAPPED_LABELS = {
    'prisutnost snijega': 'Prisutnost snijega i leda → "snijeg - da" (or "- stalno"/"- privremeno" from the prose); '
                          'unticked + filled section → "snijeg - ne"',
    'prisutnost leda': 'Prisutnost snijega i leda → "led - da" (same rule as snijeg)',
}

# Vocabularies where we know valid labels but not the complete option list —
# checked for unknown labels only, never for completeness.
PARTIAL_VOCAB = {
    'Vrsta objekta': {
        'jama', 'špilja', 'jama sa špiljskim ulazom', 'špilja s jamskim ulazom',
        'kaverna', 'kompleksni objekt', 'jamski sustav', 'špiljski sustav',
    },
}

# Template groups with no CroSpeleo counterpart to diff against.
NO_VOCAB_NOTE = {}


def all_checkbox_labels(root):
    """[(label, checked, anchor)] for every checkbox in the document."""
    out = []
    for anchor, boxes in checkbox_groups(root):
        clean = anchor.replace('{TXT:PLC:', '').strip()
        for label, checked in boxes:
            out.append((label, checked, clean))
    return out


def check_vocabularies(root):
    print('\n== 1. CHECKBOX VOCABULARIES ==')
    labels = all_checkbox_labels(root)
    label_set = {l for l, _, _ in labels}
    matched = set()

    for group, vocab in VOCAB.items():
        present = sorted(vocab & label_set)
        missing = sorted(vocab - label_set)
        matched |= set(present)
        if not present:
            note = ACCEPTED_OMISSIONS.get('%s|*' % group)
            print('  -- %-32s absent from template%s' % (group, ' (' + note + ')' if note else ''))
            continue
        if not missing:
            print('  OK %-32s all %d labels present' % (group, len(vocab)))
            continue
        if group in SUBSET_BY_DESIGN:
            print('  ~  %-32s %d/%d labels — %s' % (group, len(present), len(vocab), SUBSET_BY_DESIGN[group]))
            continue
        print('  !! %-32s %d/%d labels' % (group, len(present), len(vocab)))
        for l in missing:
            why = ACCEPTED_OMISSIONS.get('%s|%s' % (group, l))
            print('       missing: %-52s %s' % (repr(l), '(' + why + ')' if why else '<-- gap'))

    for group, vocab in PARTIAL_VOCAB.items():
        present = [l for l, _, _ in labels if l in vocab]
        if present:
            matched |= set(present)
            print('  OK %-32s %d labels, all confirmed against CroSpeleo (list not exhaustive)'
                  % (group, len(present)))

    mapped = [l for l, _, _ in labels if l not in matched and l in MAPPED_LABELS]
    if mapped:
        print('\n  labels mapped by rule (no verbatim CroSpeleo label):')
        for l in mapped:
            matched.add(l)
            print('     %-22s %s' % (l, MAPPED_LABELS[l]))

    leftover = [(l, a) for l, _, a in labels if l not in matched]
    if leftover:
        print('\n  labels with no CroSpeleo vocab match:')
        for l, anchor in leftover:
            note = ''
            for key, text in NO_VOCAB_NOTE.items():
                if key.lower() in anchor.lower() or key.lower() in l.lower():
                    note = ' — ' + text
                    break
            print('     %-46s [%s]%s' % (repr(l), anchor[:28], note))


def row_labels(root):
    """Every label-looking cell text in the document, for the alias check."""
    seen, out = set(), []
    for tbl in root.find(W + 'body').findall(W + 'tbl'):
        for tr in tbl.findall(W + 'tr'):
            for n in row_nodes(tr):
                txt = node_text(n).strip()
                if not txt or txt.startswith('<<') or '[ ]' in txt or '[x]' in txt:
                    continue
                txt = txt.rstrip(':').strip()
                if 1 < len(txt) < 60 and txt not in seen:
                    seen.add(txt)
                    out.append(txt)
    return out


def check_aliases(root, repo):
    print('\n== 2. HEADINGS vs OSZParser ALIASES ==')
    src = os.path.join(repo, 'src')
    if not os.path.isdir(src):
        print('  (skipped — crospeleo-automation not found at %s)' % repo)
        return
    sys.path.insert(0, src)
    try:
        from crospeleo_automation.services.osz_parser import OSZParser
    except Exception as exc:                      # missing deps in this interpreter
        print('  (skipped — could not import OSZParser: %s)' % exc)
        return
    parser = OSZParser()
    known, unknown = [], []
    for label in row_labels(root):
        key = parser._canonical_key(label)
        (known if key else unknown).append((label, key))
    print('  recognised: %d' % len(known))
    for label, key in known:
        print('     %-42s -> %s' % (label, key))
    print('  NOT recognised: %d' % len(unknown))
    for label, _ in unknown:
        print('     %s' % label)


def check_hygiene(root):
    print('\n== 3. CONTROL HYGIENE ==')
    no_multi, no_size, no_tag, n = [], [], 0, 0
    for sdt in root.iter(W + 'sdt'):
        i = sdt_info(sdt)
        if i['kind'] != 'TXT':
            continue
        n += 1
        label = (i['text'] or '')[:40]
        if not i['multiLine']:
            no_multi.append(label)
        if not i['sz']:
            no_size.append(label)
        if not i['tag']:
            no_tag += 1
    print('  text controls: %d' % n)
    print('  without multiLine (Enter blocked): %d' % len(no_multi))
    for l in no_multi:
        print('     %r' % l)
    print('  without explicit font size (falls back to 11 pt): %d' % len(no_size))
    for l in no_size:
        print('     %r' % l)
    print('  without w:tag (fetcher must match on heading text): %d' % no_tag)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_repo = os.path.abspath(os.path.join(here, '..', '..', '..', '..', '..', 'crospeleo-automation'))
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('--crospeleo', default=default_repo)
    a = ap.parse_args()
    root = load(a.docx)
    print('Template: %s' % a.docx)
    check_vocabularies(root)
    check_aliases(root, a.crospeleo)
    check_hygiene(root)


if __name__ == '__main__':
    main()
