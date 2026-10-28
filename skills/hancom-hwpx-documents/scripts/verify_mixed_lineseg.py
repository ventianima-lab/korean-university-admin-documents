#!/usr/bin/env python3
"""Inspect lineseg offsets where hp:t contains explicit hp:lineBreak children.

Some validators omit mixed-content hp:t entirely when counting text. This
read-only check counts the complete text, including tails after lineBreak. It
reports bounds only: it does not validate layout or prove that a file opens.
"""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
NS = {'hp': HP}


def units(text):
    return len(text.encode('utf-16-le')) // 2


def inspect_section(section):
    root = ET.fromstring(section)
    found = []
    for i, para in enumerate(root.findall('.//hp:p', NS)):
        texts = para.findall('./hp:run/hp:t', NS)
        mixed = [t for t in texts if t.find('./hp:lineBreak', NS) is not None]
        if not mixed:
            continue
        if any(any(child.tag != f'{{{HP}}}lineBreak' for child in t) for t in texts):
            found.append({'paragraph': i, 'status': 'unsupported_inline_control'})
            continue
        full = units(''.join(''.join(t.itertext()) for t in texts))
        legacy_count = units(''.join(t.text or '' for t in texts if len(t) == 0))
        offsets = [int(s.get('textpos', '0')) for s in para.findall('./hp:linesegarray/hp:lineseg', NS)]
        warned = [n for n in offsets if n > legacy_count]
        if not warned:
            continue
        found.append({'paragraph': i, 'status': 'within_full_text' if max(warned) <= full else 'overflow',
                      'naive_units': legacy_count, 'full_text_units': full, 'flagged_offsets': warned})
    return found


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('document', type=Path)
    a = p.parse_args()
    findings = []
    try:
        with ZipFile(a.document) as z:
            for name in z.namelist():
                if name.startswith('Contents/section') and name.endswith('.xml'):
                    findings.extend({'section': name, **x} for x in inspect_section(z.read(name)))
    except (OSError, ValueError, ET.ParseError) as e:
        p.exit(2, f'MIXED_LINESEG_ERROR: {e}\n')
    passed = bool(findings) and all(x['status'] == 'within_full_text' for x in findings)
    print(json.dumps({'status': 'BOUNDS_PASS' if passed else 'REVIEW_REQUIRED', 'findings': findings}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
