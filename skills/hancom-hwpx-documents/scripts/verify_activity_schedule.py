#!/usr/bin/env python3
"""Verify an HWPX schedule against independently sourced activity and weekday facts.

The optional rectangular-table inventory uses section, table, source, headers,
and activities with cells and source. Weekly constraints use this shape::

  {"section": "Contents/section0.xml", "source": "schedule source",
   "weekly_constraints": [{"weekday": 2, "source": "weekday authority",
      "year": 2027, "year_source": "year authority", "scope_paragraphs": [0],
      "sessions": [{"paragraph": 0, "date_text": "5월 4일",
                    "source": "session-date source"}]}]}

Weekdays are ISO 1=Monday through 7=Sunday; paragraph indexes are zero-based
within the section, including paragraphs in tables. The caller must enumerate
all relevant paragraphs independently, including repeat dates elsewhere. The
check reads selected paragraph text only and never suggests replacement dates.

For a confirmed correction across independently enumerated surfaces, use
--reconcile INVENTORY.json instead of the two positional arguments. Its shape is::

  {"event": {"id": "event-a", "start": "09:20", "end": "11:20",
             "source": "explicit confirmation"},
   "required_surfaces": [{"id": "document-a", "kind": "document"}],
   "surfaces": [{"id": "document-a", "kind": "document",
     "target_record_ids": ["field-1"],
     "before": {"path": "before.json", "sha256": "<64 hex>", "source": "capture"},
     "after": {"path": "after.json", "sha256": "<64 hex>", "source": "capture"},
     "conflict_corrections": [{"stale": "time unconfirmed", "replacement": ""}]}]}

Each UTF-8 snapshot has a surface_id and a records list. Every record has a
unique record_id and an event_id. Target records additionally have normalized
24-hour start/end and conflict_display strings. Include all other records in
the independently inventoried scope. Snapshot hashes bind the supplied capture,
not the live document, API, or page. This helper cannot establish capture
freshness, source fidelity, inventory completeness, or rendered layout; check
those directly and independently before claiming cross-surface completion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
DATE = re.compile(
    r'(?<![\d./-])(?:(?P<year>\d{4})\s*(?:년|[./-])\s*)?'
    r'(?P<month>\d{1,2})\s*(?:월|[./-])\s*'
    r'(?P<day>\d{1,2})(?:[ \t]*(?:일|\.))?(?!\d|[./-]\s*\d)'
)
BARE_DAY = re.compile(r'(?<!\d)\d{1,2}\s*일(?!\w)')
LABEL = re.compile(r'\s*(?:\(\s*([월화수목금토일])(?:요일)?\s*\)|([월화수목금토일])요일)')
KOREAN_WEEKDAYS = '월화수목금토일'


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def paragraph_text(paragraph):
    """Read this paragraph's text only, excluding nested table paragraphs."""
    parts = []

    def visit(element):
        for child in element:
            if child.tag == HP + 'p':
                continue
            if child.tag == HP + 't':
                parts.append(''.join(child.itertext()))
            else:
                visit(child)

    visit(paragraph)
    return ''.join(parts)


def verify_table(root, spec):
    index = spec.get('table')
    headers, activities = spec.get('headers'), spec.get('activities')
    if type(index) is not int or index < 0:
        raise ValueError('A nonnegative table index is required')
    if not isinstance(headers, list) or len(headers) < 2 or not all(nonempty(v) for v in headers):
        raise ValueError('Explicit nonempty headers are required')
    if not isinstance(activities, list) or not activities:
        raise ValueError('Independent activity rows are required')
    expected = [headers]
    for activity in activities:
        if not isinstance(activity, dict) or not nonempty(activity.get('source')):
            raise ValueError('Every activity must have an independent source')
        cells = activity.get('cells')
        if not isinstance(cells, list) or len(cells) != len(headers) or not all(isinstance(v, str) for v in cells):
            raise ValueError('Activity cells must match the header width')
        expected.append(cells)
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
    return {'activities': len(activities), 'columns': len(headers)}


def verify_weekdays(root, constraints):
    if not isinstance(constraints, list) or not constraints:
        raise ValueError('At least one sourced weekday constraint is required')
    paragraphs = list(root.iter(HP + 'p'))
    checked = 0
    for rule in constraints:
        if not isinstance(rule, dict):
            raise ValueError('Each weekday constraint must be an object')
        weekday, year = rule.get('weekday'), rule.get('year')
        if type(weekday) is not int or not 1 <= weekday <= 7 or not nonempty(rule.get('source')):
            raise ValueError('An ISO weekday and its independent source are required')
        if type(year) is not int or not 1 <= year <= 9999 or not nonempty(rule.get('year_source')):
            raise ValueError('A year and its independent source are required')
        scope, sessions = rule.get('scope_paragraphs'), rule.get('sessions')
        if (not isinstance(scope, list) or not scope or
                any(type(i) is not int or i < 0 or i >= len(paragraphs) for i in scope) or
                len(set(scope)) != len(scope)):
            raise ValueError('A unique, valid schedule paragraph scope is required')
        if not isinstance(sessions, list) or not sessions:
            raise ValueError('Sourced session dates are required')
        expected = {i: [] for i in scope}
        for session in sessions:
            if not isinstance(session, dict) or not nonempty(session.get('source')):
                raise ValueError('Every session date requires a source')
            index, token = session.get('paragraph'), session.get('date_text')
            if type(index) is not int or index not in expected or not nonempty(token) or token != token.strip():
                raise ValueError('Each session requires a scoped paragraph and exact date text')
            expected[index].append(token)
        for index in scope:
            text = paragraph_text(paragraphs[index])
            matches = list(DATE.finditer(text))
            tokens = [m.group() for m in matches]
            if not expected[index] or Counter(tokens) != Counter(expected[index]):
                raise ValueError(f'Schedule date coverage mismatch at paragraph {index}')
            if any(not any(m.start() <= d.start() and d.end() <= m.end() for m in matches)
                   for d in BARE_DAY.finditer(text)):
                raise ValueError(f'Unsupported abbreviated date at paragraph {index}')
            for match in matches:
                token_year = int(match.group('year')) if match.group('year') else year
                if token_year != year:
                    raise ValueError(f'Schedule year mismatch at paragraph {index}')
                try:
                    actual = date(token_year, int(match.group('month')), int(match.group('day')))
                except ValueError as exc:
                    raise ValueError(f'Invalid schedule date at paragraph {index}') from exc
                label = LABEL.match(text[match.end():])
                if label and KOREAN_WEEKDAYS.index(label.group(1) or label.group(2)) + 1 != actual.isoweekday():
                    raise ValueError(f'Printed weekday differs from calendar at paragraph {index}')
                if actual.isoweekday() != weekday:
                    raise ValueError(f'Session weekday conflicts with its source at paragraph {index}')
                checked += 1
    return checked


def verify(path, spec, require_weekday=False):
    if not isinstance(spec, dict) or not nonempty(spec.get('source')):
        raise ValueError('An independent schedule source is required')
    unknown = set(spec) - {'section', 'source', 'table', 'headers', 'activities', 'weekly_constraints'}
    if unknown:
        raise ValueError('Unknown inventory fields: ' + ', '.join(sorted(unknown)))
    section = spec.get('section')
    if not isinstance(section, str) or not re.fullmatch(r'Contents/section\d+\.xml', section):
        raise ValueError('A section is required')
    has_table = any(key in spec for key in ('table', 'headers', 'activities'))
    has_weekday = 'weekly_constraints' in spec
    if require_weekday and not has_weekday:
        raise ValueError('A weekday constraint is required by --require-weekday')
    if not has_table and not has_weekday:
        raise ValueError('A schedule table or weekday constraint is required')
    with ZipFile(path) as package:
        root = ET.fromstring(package.read(section))
    result = {'status': 'PASS'}
    if has_table:
        result.update(verify_table(root, spec))
    result['weekday_constraints_checked'] = len(spec['weekly_constraints']) if has_weekday and isinstance(spec['weekly_constraints'], list) else 0
    result['session_dates_checked'] = verify_weekdays(root, spec['weekly_constraints']) if has_weekday else 0
    return result


def _snapshot_records(snapshot, base_dir, surface_id):
    if not isinstance(snapshot, dict):
        raise ValueError('Every snapshot needs a path, SHA-256, and source')
    path, digest, source = snapshot.get('path'), snapshot.get('sha256'), snapshot.get('source')
    if not nonempty(path) or not nonempty(source) or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('Every snapshot needs a path, SHA-256, and source')
    path = Path(path)
    raw = (path if path.is_absolute() else base_dir / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest.lower():
        raise ValueError('Snapshot hash mismatch')
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, dict) or data.get('surface_id') != surface_id or not isinstance(data.get('records'), list):
        raise ValueError('Snapshot surface identity or records are invalid')
    records = {}
    for record in data['records']:
        if not isinstance(record, dict) or not nonempty(record.get('record_id')) or not nonempty(record.get('event_id')):
            raise ValueError('Every snapshot record needs stable record and event identities')
        record_id = record['record_id']
        if record_id in records:
            raise ValueError('Duplicate snapshot record identity')
        records[record_id] = record
    return records


def _valid_clock(value):
    return isinstance(value, str) and re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value) is not None


def verify_reconciliation(spec, base_dir):
    """Check independently captured records; never change a source or snapshot."""
    if not isinstance(spec, dict) or set(spec) != {'event', 'required_surfaces', 'surfaces'}:
        raise ValueError('A reconciliation event, required surfaces, and surfaces are required')
    event = spec['event']
    if (not isinstance(event, dict) or not nonempty(event.get('id')) or
            not nonempty(event.get('source')) or not _valid_clock(event.get('start')) or
            not _valid_clock(event.get('end')) or event['start'] == event['end']):
        raise ValueError('An independently confirmed event identity and exact interval are required')
    required, surfaces = spec['required_surfaces'], spec['surfaces']
    if not isinstance(required, list) or not required or not isinstance(surfaces, list) or not surfaces:
        raise ValueError('Independently enumerated required surfaces are required')
    required_by_id = {}
    for item in required:
        if not isinstance(item, dict) or not nonempty(item.get('id')) or item.get('kind') not in {'document', 'calendar', 'page'}:
            raise ValueError('Each required surface needs an identity and kind')
        if item['id'] in required_by_id:
            raise ValueError('Duplicate required surface identity')
        required_by_id[item['id']] = item['kind']
    seen, target_count, unrelated_count = set(), 0, 0
    for surface in surfaces:
        if not isinstance(surface, dict) or not nonempty(surface.get('id')):
            raise ValueError('Every surface needs an identity')
        surface_id = surface['id']
        if surface_id in seen or required_by_id.get(surface_id) != surface.get('kind'):
            raise ValueError('Unexpected, duplicated, or mismatched surface')
        seen.add(surface_id)
        ids = surface.get('target_record_ids')
        if not isinstance(ids, list) or not ids or not all(nonempty(value) for value in ids) or len(set(ids)) != len(ids):
            raise ValueError('Every surface needs unique independently inventoried target records')
        corrections = surface.get('conflict_corrections')
        if not isinstance(corrections, list) or not corrections:
            raise ValueError('Every surface needs an independently identified stale-conflict check')
        markers = set()
        for correction in corrections:
            if (not isinstance(correction, dict) or not nonempty(correction.get('stale')) or
                    not isinstance(correction.get('replacement'), str) or
                    correction['stale'] in correction['replacement'] or correction['stale'] in markers):
                raise ValueError('Invalid or duplicate stale-conflict correction')
            markers.add(correction['stale'])
        before = _snapshot_records(surface.get('before'), base_dir, surface_id)
        after = _snapshot_records(surface.get('after'), base_dir, surface_id)
        if set(before) != set(after):
            raise ValueError('Snapshot record inventory changed')
        targets = set(ids)
        for records in (before, after):
            if {key for key, record in records.items() if record['event_id'] == event['id']} != targets:
                raise ValueError('Target event identity or occurrence coverage mismatch')
        for key, old in before.items():
            new = after[key]
            if key not in targets:
                if old != new:
                    raise ValueError('An unrelated record changed')
                unrelated_count += 1
                continue
            if any(field not in old or field not in new for field in ('start', 'end', 'conflict_display')):
                raise ValueError('Target time and conflict-display fields are required')
            if not isinstance(old['conflict_display'], str) or not isinstance(new['conflict_display'], str):
                raise ValueError('Conflict displays must be text')
            expected = dict(old)
            expected['start'], expected['end'] = event['start'], event['end']
            for correction in corrections:
                stale, replacement = correction['stale'], correction['replacement']
                if expected['conflict_display'].count(stale) > 1:
                    raise ValueError('Ambiguous stale-conflict marker requires a narrower scope')
                expected['conflict_display'] = expected['conflict_display'].replace(stale, replacement)
                if stale in new['conflict_display']:
                    raise ValueError('A superseded conflict display remains')
            if new != expected:
                raise ValueError('Target interval or protected fields differ from the confirmed correction')
            target_count += 1
    if seen != set(required_by_id):
        raise ValueError('A required surface is missing')
    return {'status': 'PASS', 'surfaces_checked': len(seen),
            'target_records_checked': target_count, 'unrelated_records_checked': unrelated_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path, nargs='?')
    parser.add_argument('inventory', type=Path, nargs='?')
    parser.add_argument('--require-weekday', action='store_true', help='fail if no weekday constraint is provided')
    parser.add_argument('--reconcile', type=Path, metavar='INVENTORY', help='verify independently captured cross-surface correction snapshots')
    args = parser.parse_args()
    if args.reconcile:
        if args.document is not None or args.inventory is not None or args.require_weekday:
            parser.error('--reconcile cannot be combined with document, inventory, or --require-weekday')
    elif args.document is None or args.inventory is None:
        parser.error('document and inventory are required unless --reconcile is used')
    try:
        inventory = args.reconcile or args.inventory
        spec = json.loads(inventory.read_text(encoding='utf-8-sig'))
        result = verify_reconciliation(spec, inventory.resolve().parent) if args.reconcile else verify(args.document, spec, require_weekday=args.require_weekday)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, BadZipFile, ValueError, KeyError, IndexError, ET.ParseError) as exc:
        print(json.dumps({'status': 'VERIFICATION_FAILED', 'reason': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
