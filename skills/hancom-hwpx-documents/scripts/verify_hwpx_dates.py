#!/usr/bin/env python3
"""Read-only date preservation check, including dates inside edited blocks.

Optional JSON: {"changes":[{"section":"Contents/section0.xml",
"before":"table=0/row=2/col=1/p=0", "after":"table=0/row=2/col=1/p=0",
"old":["2027. 5. 12."], "new":["2027. 5. 19."],
"source":"The user's explicit instruction for this date field"}]}.
Use null for a missing old/new field. Changes authorize only exact date tokens
at the mapped locations; they do not authorize other content or format edits.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
DATE = re.compile(
    r'(?<!\d)(?:(?:19|20)\d{6}(?!\d)|'
    r'(?:\d{4}|\d{2})\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}\.?(?!\d)|'
    r'(?:\d{4}|\d{2})\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일|'
    r'\d{1,2}\s*월\s*\d{1,2}\s*일|(?:19|20)\d{2}\s*[.년])')


def paragraph_text(paragraph):
    def visit(node):
        if node is not paragraph and node.tag in {HP+'p', HP+'tbl'}:
            return ''
        if node.tag == HP+'t':
            return ''.join(node.itertext())
        return ''.join(visit(child) for child in node)
    return visit(paragraph)


def date_fields(root):
    locations = {}
    for ti, table in enumerate(root.iter(HP+'tbl')):
        for row in table.findall(HP+'tr'):
            for cell in row.findall(HP+'tc'):
                addr = cell.find(HP+'cellAddr')
                if addr is None:
                    raise ValueError('Cannot locate a table date without cellAddr')
                sub = cell.find(HP+'subList')
                for pi, paragraph in enumerate(sub.findall(HP+'p') if sub is not None else []):
                    locations[id(paragraph)] = (
                        f'table={ti}/row={addr.get("rowAddr")}/col={addr.get("colAddr")}/p={pi}')
    result = {}
    body = 0
    for paragraph in root.iter(HP+'p'):
        location = locations.get(id(paragraph))
        if location is None:
            location = f'body={body}'
            body += 1
        tokens = [match.group() for match in DATE.finditer(paragraph_text(paragraph))]
        if tokens:
            result[location] = tokens
    return result


def verify(baseline: Path, candidate: Path, changes=None):
    changes = changes if changes is not None else {'changes': []}
    if not isinstance(changes, dict) or not isinstance(changes.get('changes'), list):
        raise ValueError('Date changes require a changes list')
    used = set()
    mapped = set()
    protected = 0
    with ZipFile(baseline) as before, ZipFile(candidate) as after:
        parts = sorted(n for n in before.namelist()
                       if re.fullmatch(r'Contents/section\d+\.xml', n))
        if parts != sorted(n for n in after.namelist()
                           if re.fullmatch(r'Contents/section\d+\.xml', n)):
            raise ValueError('Date check requires matching sections')
        for part in parts:
            old = date_fields(ET.fromstring(before.read(part)))
            new = date_fields(ET.fromstring(after.read(part)))
            protected += len(old)
            for index, change in enumerate(changes['changes']):
                if not isinstance(change, dict):
                    raise ValueError('Each date change must be an object')
                if change.get('section') != part:
                    continue
                if not isinstance(change.get('source'), str) or not change['source'].strip():
                    raise ValueError('Date change lacks the explicit user instruction')
                for side, fields, token_key in [('before', old, 'old'), ('after', new, 'new')]:
                    if side not in change or token_key not in change:
                        raise ValueError('Date change requires both locations and token lists')
                    location, expected = change[side], change[token_key]
                    if not isinstance(expected, list) or not all(isinstance(t, str) for t in expected):
                        raise ValueError('Date tokens must be string lists')
                    if location is None:
                        if expected:
                            raise ValueError('Missing date field cannot have tokens')
                    elif not isinstance(location, str) or fields.get(location, []) != expected:
                        raise ValueError('Authorized date change does not match the exact source/target field')
                    else:
                        key = (part, side, location)
                        if key in mapped:
                            raise ValueError('Duplicate date authorization for one field')
                        mapped.add(key)
                        fields.pop(location, None)
                used.add(index)
            if old != new:
                # Keep personal dates out of failure logs; report only locations.
                changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
                raise ValueError('Unrequested date deletion, replacement or insertion in '
                                 + part + ': ' + ', '.join(changed))
    if used != set(range(len(changes['changes']))):
        raise ValueError('Unused date authorization or unknown section')
    return {'status': 'PASS', 'protected_date_fields': protected,
            'explicit_date_changes': len(used)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--changes', type=Path)
    args = parser.parse_args()
    try:
        changes = json.loads(args.changes.read_text(encoding='utf-8-sig')) if args.changes else None
        print(json.dumps(verify(args.baseline, args.candidate, changes), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, BadZipFile, ET.ParseError) as exc:
        print(json.dumps({'status': 'VERIFICATION_FAILED', 'reason': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
