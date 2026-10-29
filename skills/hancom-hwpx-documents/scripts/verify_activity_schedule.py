#!/usr/bin/env python3
"""Verify an editable programme schedule against an independent activity inventory.

JSON: {section, table, source, headers: [text, ...],
       activities: [{cells: [text, ...], source: text}, ...]}.
Rows and cellAddr indexes are zero-based. This read-only check is for a simple
rectangular schedule, not merged-cell layouts or visual/policy validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def verify(path, spec):
    if not isinstance(spec, dict) or not spec.get('source'):
        raise ValueError('An independent schedule source is required')
    section, index = spec.get('section'), spec.get('table')
    headers, activities = spec.get('headers'), spec.get('activities')
    if not isinstance(section, str) or not section.startswith('Contents/section'):
        raise ValueError('A section is required')
    if type(index) is not int or index < 0:
        raise ValueError('A nonnegative table index is required')
    if not isinstance(headers, list) or len(headers) < 2 or not all(isinstance(v, str) and v for v in headers):
        raise ValueError('Explicit nonempty headers are required')
    if not isinstance(activities, list) or not activities:
        raise ValueError('Independent activity rows are required')
    expected = [headers]
    for activity in activities:
        if not isinstance(activity, dict) or not activity.get('source'):
            raise ValueError('Every activity must have an independent source')
        cells = activity.get('cells')
        if not isinstance(cells, list) or len(cells) != len(headers) or not all(isinstance(v, str) for v in cells):
            raise ValueError('Activity cells must match the header width')
        expected.append(cells)
    with ZipFile(path) as package:
        root = ET.fromstring(package.read(section))
    tables = list(root.iter(HP + 'tbl'))
    if index >= len(tables):
        raise ValueError('Schedule table not found')
    table = tables[index]
    rows = table.findall(HP + 'tr')
    if len(rows) != len(expected) or int(table.get('rowCnt', '-1')) != len(expected):
        raise ValueError('Schedule row count differs from the activity inventory')
    if int(table.get('colCnt', '-1')) != len(headers):
        raise ValueError('Schedule column count differs from the header inventory')
    for ri, row in enumerate(rows):
        cells = row.findall(HP + 'tc')
        if len(cells) != len(headers):
            raise ValueError('Schedule row is not rectangular')
        by_column = {}
        for tc in cells:
            addr, span = tc.find(HP + 'cellAddr'), tc.find(HP + 'cellSpan')
            if addr is None or int(addr.get('rowAddr', '-1')) != ri:
                raise ValueError('Schedule row address is inconsistent')
            if span is not None and (int(span.get('rowSpan', '1')) != 1 or int(span.get('colSpan', '1')) != 1):
                raise ValueError('Merged schedule cells require separate verification')
            col = int(addr.get('colAddr', '-1'))
            if col in by_column:
                raise ValueError('Schedule column address is duplicated')
            by_column[col] = ''.join(''.join(t.itertext()) for t in tc.iter(HP + 't'))
        for ci, value in enumerate(expected[ri]):
            if by_column.get(ci) != value:
                raise ValueError(f'Schedule cell mismatch at row {ri}, column {ci}')
    return {'status': 'PASS', 'activities': len(activities), 'columns': len(headers)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('inventory', type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads(args.inventory.read_text(encoding='utf-8-sig'))
        print(json.dumps(verify(args.document, spec), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, IndexError, ET.ParseError) as exc:
        print(json.dumps({'status': 'VERIFICATION_FAILED', 'reason': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
