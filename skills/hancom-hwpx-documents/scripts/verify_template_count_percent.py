#!/usr/bin/env python3
"""Fail closed when a count-and-percent template field is omitted or miscalculated.

Usage: verify_template_count_percent.py TEMPLATE.hwpx OUTPUT.hwpx EXPECTATIONS.json
The JSON supplies template/output section and table indexes, rounding_decimals,
independently sourced field mappings and optional mutually exclusive groups.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from zipfile import BadZipFile, ZipFile

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
VALUE = re.compile(r'^\s*(\d+)\s*명\s*\(\s*(\d+(?:\.\d+)?)\s*%\s*\)\s*$')


def address(value):
    if not isinstance(value, list) or len(value) != 2 or any(type(n) is not int or n < 0 for n in value):
        raise ValueError('Each field address must be [nonnegative row, nonnegative column]')
    return tuple(value)


def table_cells(path, spec):
    section = spec['section']
    index = spec['table']
    if not isinstance(section, str) or not section.startswith('Contents/section') or not section.endswith('.xml'):
        raise ValueError('Invalid section path')
    if type(index) is not int or index < 0:
        raise ValueError('Invalid table index')
    with ZipFile(path) as z:
        root = ET.fromstring(z.read(section))
    tables = list(root.iter(HP + 'tbl'))
    if index >= len(tables):
        raise ValueError('Requested table does not exist')
    result = {}
    for row in tables[index].findall(HP + 'tr'):
        for cell in row.findall(HP + 'tc'):
            coord = cell.find(HP + 'cellAddr')
            if coord is None:
                raise ValueError('Table cell has no address')
            key = (int(coord.get('rowAddr')), int(coord.get('colAddr')))
            if key in result:
                raise ValueError('Duplicate table cell address')
            result[key] = ''.join(''.join(t.itertext()) for t in cell.iter(HP + 't'))
    return result


def verify(template_path, output_path, expected):
    source = table_cells(template_path, expected['template'])
    output = table_cells(output_path, expected['output'])
    # Examine every cell containing both the count unit and percent sign. An
    # unsupported/multi-value cell must fail, not silently disappear from scope.
    relevant = {k: v for k, v in source.items() if '명' in v and '%' in v}
    if not relevant:
        raise ValueError('No count-and-percent fields found in the selected template table')
    unsupported = [k for k, value in relevant.items() if not VALUE.fullmatch(value)]
    if unsupported:
        raise ValueError(f'Unsupported template field shape: {unsupported}')
    places = expected['rounding_decimals']
    if type(places) is not int or not 0 <= places <= 4:
        raise ValueError('rounding_decimals must be an integer from 0 to 4')
    quantum = Decimal(1).scaleb(-places)
    entries = expected['fields']
    if not isinstance(entries, list) or not entries:
        raise ValueError('Independent expected fields are required')
    seen_template = set()
    seen_output = set()
    checked_counts = {}
    checked_denominators = {}
    checked_percentages = {}
    groups = expected.get('groups', [])
    if not isinstance(groups, list):
        raise ValueError('groups must be a list')
    balanced_cells = set()
    group_membership = {}
    for group in groups:
        method = group.get('rounding', 'individual')
        if method not in {'individual', 'largest_remainder'}:
            raise ValueError('Unknown group rounding method')
        members = [address(item) for item in group['output_cells']]
        for member in members:
            previous = group_membership.get(member)
            if previous and (method == 'largest_remainder' or previous == 'largest_remainder'):
                raise ValueError('Balanced groups cannot overlap another group')
            group_membership[member] = method
        if method == 'largest_remainder':
            balanced_cells.update(members)
    for entry in entries:
        src, dst = address(entry['template']), address(entry['output'])
        if src in seen_template or dst in seen_output:
            raise ValueError('Duplicate source or output mapping')
        seen_template.add(src)
        seen_output.add(dst)
        if src not in relevant:
            raise ValueError(f'Mapped template cell is not a count-and-percent field: {src}')
        if dst not in output:
            raise ValueError(f'Missing output cell: {dst}')
        if not isinstance(entry.get('source'), str) or not entry['source'].strip():
            raise ValueError(f'Independent count evidence is missing for {dst}')
        count, denominator = entry['count'], entry['denominator']
        if type(count) is not int or type(denominator) is not int or denominator <= 0 or not 0 <= count <= denominator:
            raise ValueError(f'Invalid count or denominator at {dst}')
        match = VALUE.fullmatch(output[dst])
        if not match:
            raise ValueError(f'Missing count unit or percentage at {dst}: {output[dst]!r}')
        actual_count, actual_pct = int(match.group(1)), Decimal(match.group(2))
        correct_pct = (Decimal(count) * 100 / Decimal(denominator)).quantize(quantum, rounding=ROUND_HALF_UP)
        if actual_count != count or (dst not in balanced_cells and actual_pct != correct_pct):
            raise ValueError(f'Count or percentage mismatch at {dst}: got {output[dst]!r}, expected {count} and {correct_pct}%')
        checked_counts[dst] = count
        checked_denominators[dst] = denominator
        checked_percentages[dst] = actual_pct
    missing = set(relevant) - seen_template
    if missing:
        raise ValueError(f'Template fields not covered by independent expectations: {sorted(missing)}')
    for group in groups:
        members = [address(item) for item in group['output_cells']]
        if not members or len(members) != len(set(members)) or not set(members).issubset(checked_counts):
            raise ValueError('A group is empty, duplicated, or includes unchecked output fields')
        denominator = group['denominator']
        if (type(denominator) is not int or denominator <= 0
                or any(checked_denominators[c] != denominator for c in members)
                or sum(checked_counts[c] for c in members) != denominator):
            raise ValueError(f'Count total does not reconcile for group {group.get("name", "unnamed")}')
        if group.get('rounding', 'individual') == 'largest_remainder':
            scale = 10 ** places
            units = []
            remainders = []
            deltas = []
            for member in members:
                floor, remainder = divmod(checked_counts[member] * 100 * scale, denominator)
                actual_units = checked_percentages[member] * scale
                if actual_units != actual_units.to_integral_value():
                    raise ValueError('Balanced percentage exceeds selected precision')
                units.append(int(actual_units))
                remainders.append(remainder)
                deltas.append(int(actual_units) - floor)
            if sum(units) != 100 * scale or any(delta not in (0, 1) for delta in deltas):
                raise ValueError(f'Balanced percentages do not reconcile for group {group.get("name", "unnamed")}')
            selected = [r for r, delta in zip(remainders, deltas) if delta == 1]
            unselected = [r for r, delta in zip(remainders, deltas) if delta == 0]
            if selected and unselected and min(selected) < max(unselected):
                raise ValueError(f'Balanced percentage remainder allocation is invalid for group {group.get("name", "unnamed")}')
    return {'status': 'PASS', 'template_fields': len(relevant), 'verified_fields': len(entries), 'groups': len(groups)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('template', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('expectations', type=Path)
    args = parser.parse_args()
    try:
        expected = json.loads(args.expectations.read_text(encoding='utf-8-sig'))
        print(json.dumps(verify(args.template, args.output, expected), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError, InvalidOperation, IndexError) as exc:
        print(json.dumps({'status': 'VERIFICATION_FAILED', 'reason': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
