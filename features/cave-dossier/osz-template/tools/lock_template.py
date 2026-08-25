# -*- coding: utf-8 -*-
"""Produce a locked, distribution-ready copy of the Word OSZ template.

    python lock_template.py <master.docx> <out.docx|out.dotx> [options]

What it can add
---------------
--forms            ``w:documentProtection w:edit="forms"`` — everything is
                   read-only except the content controls.  The recorder can
                   still tick boxes and type in fields, but cannot delete a row,
                   drag a column or wreck the layout.
--password PW      the same, but "Stop Protection" then asks for a password
                   (ECMA-376 agile hash: SHA-512, 100 000 spins).
--read-only-rec    ``w:writeProtection w:recommended="1"`` — Word asks "open
                   read-only?" on every open.
--lock-controls    ``w:lock w:val="sdtLocked"`` on every content control, so the
                   fields themselves cannot be deleted (content stays editable).
--dotx             write the output as a Word *template* part type.  Double-
                   clicking a .dotx in Explorer opens a NEW document based on
                   it; the .dotx itself is never the thing being edited.

What none of this does
----------------------
**Google Docs ignores every one of these flags.**  Word's protection, write
protection and "Mark as Final" have no counterpart in Docs, so a .docx opened
from Drive in Office-editing mode can still be typed into and saved back over
the template.  The only reliable lock there is a Drive permission: keep the
template file *Viewer*-only for recorders, so Docs can offer them nothing but
"Make a copy".  See docs/google-docs-compatibility.md.
"""
import argparse
import base64
import hashlib
import os
import struct
import sys
import zipfile

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flatten_for_gdocs import drop_embedded_fonts  # noqa: E402

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
CT_DOCUMENT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
CT_TEMPLATE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml'

SPIN_COUNT = 100000


def password_hash(password, salt):
    """ECMA-376 agile password verifier: SHA-512 over salt+password, spun."""
    h = hashlib.sha512(salt + password.encode('utf-16-le')).digest()
    for i in range(SPIN_COUNT):
        h = hashlib.sha512(h + struct.pack('<I', i)).digest()
    return h


def set_protection(settings_root, *, forms, password, read_only_rec):
    """documentProtection / writeProtection are top-level w:settings children."""
    for tag in ('documentProtection', 'writeProtection'):
        for el in list(settings_root.iter(W + tag)):
            el.getparent().remove(el)

    if read_only_rec:
        wp = etree.Element(W + 'writeProtection')
        wp.set(W + 'recommended', '1')
        settings_root.insert(0, wp)

    if not forms:
        return
    dp = etree.Element(W + 'documentProtection')
    dp.set(W + 'edit', 'forms')
    dp.set(W + 'enforcement', '1')
    if password:
        salt = os.urandom(16)
        dp.set(W + 'cryptProviderType', 'rsaAES')
        dp.set(W + 'cryptAlgorithmClass', 'hash')
        dp.set(W + 'cryptAlgorithmType', 'typeAny')
        dp.set(W + 'cryptAlgorithmSid', '14')          # 14 = SHA-512
        dp.set(W + 'cryptSpinCount', str(SPIN_COUNT))
        dp.set(W + 'hash', base64.b64encode(password_hash(password, salt)).decode())
        dp.set(W + 'salt', base64.b64encode(salt).decode())
    # after writeProtection, before the rest
    settings_root.insert(1 if read_only_rec else 0, dp)


def lock_controls(doc_root):
    """Make every content control undeletable; its content stays editable."""
    n = 0
    for sdt in doc_root.iter(W + 'sdt'):
        pr = sdt.find(W + 'sdtPr')
        if pr is None:
            continue
        for old in pr.findall(W + 'lock'):
            pr.remove(old)
        lock = etree.Element(W + 'lock')
        lock.set(W + 'val', 'sdtLocked')
        # w:lock belongs early in sdtPr, right after rPr/alias/tag/id
        anchor = next((pr.find(W + t) for t in ('id', 'tag', 'alias')
                       if pr.find(W + t) is not None), None)
        if anchor is not None:
            anchor.addnext(lock)
        else:
            pr.insert(0, lock)
        n += 1
    return n


def as_template(parts):
    """Flip the main part's content type so Word treats the file as a template."""
    ct = etree.fromstring(parts['[Content_Types].xml'])
    changed = False
    for el in ct:
        if el.get('ContentType') == CT_DOCUMENT:
            el.set('ContentType', CT_TEMPLATE)
            changed = True
    parts['[Content_Types].xml'] = etree.tostring(
        ct, xml_declaration=True, encoding='UTF-8', standalone=True)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--forms', action='store_true', help='restrict editing to content controls')
    ap.add_argument('--password', help='password required to lift the restriction')
    ap.add_argument('--read-only-rec', action='store_true', help='prompt "open read-only?"')
    ap.add_argument('--lock-controls', action='store_true', help='controls cannot be deleted')
    ap.add_argument('--dotx', action='store_true', help='write as a Word template part type')
    ap.add_argument('--strip-fonts', action='store_true',
                    help='drop embedded fonts (~4.3 MB) from the distributed copy')
    a = ap.parse_args()

    zin = zipfile.ZipFile(a.src)
    names, infos = zin.namelist(), list(zin.infolist())
    parts = {n: zin.read(n) for n in names}
    zin.close()

    forms = a.forms or bool(a.password)
    settings = etree.fromstring(parts['word/settings.xml'])
    set_protection(settings, forms=forms, password=a.password, read_only_rec=a.read_only_rec)
    parts['word/settings.xml'] = etree.tostring(
        settings, xml_declaration=True, encoding='UTF-8', standalone=True)

    locked = 0
    if a.lock_controls:
        doc = etree.fromstring(parts['word/document.xml'])
        locked = lock_controls(doc)
        parts['word/document.xml'] = etree.tostring(
            doc, xml_declaration=True, encoding='UTF-8', standalone=True)

    templated = as_template(parts) if a.dotx else False

    font_stats = {'fonts_dropped': 0}
    if a.strip_fonts:
        names = drop_embedded_fonts(names, parts, font_stats)

    tmp = a.dst + '.tmp'
    zout = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
    for item in infos:
        if item.filename in names:
            zout.writestr(item, parts[item.filename])
    zout.close()
    os.replace(tmp, a.dst)

    print('written %s' % a.dst)
    print('  editing restricted to fields : %s%s' % (forms, ' (password set)' if a.password else ''))
    print('  read-only recommended        : %s' % a.read_only_rec)
    print('  controls locked (undeletable): %d' % locked)
    print('  Word template part type      : %s' % templated)
    print('  embedded fonts dropped       : %d parts' % font_stats['fonts_dropped'])
    print('  size                         : %d KB' % (os.path.getsize(a.dst) // 1024))
    print('\n  Reminder: Google Docs ignores all of the above — protect the file')
    print('  on Drive by sharing it as Viewer, not Editor.')


if __name__ == '__main__':
    main()
