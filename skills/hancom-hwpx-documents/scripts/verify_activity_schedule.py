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
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--require-weekday', action='store_true', help='fail if no weekday constraint is provided')
    args = parser.parse_args()
    try:
        spec = json.loads(args.inventory.read_text(encoding='utf-8-sig'))
        print(json.dumps(verify(args.document, spec, require_weekday=args.require_weekday), ensure_ascii=False))
        return 0
    except (OSError, BadZipFile, ValueError, KeyError, IndexError, ET.ParseError) as exc:
        print(json.dumps({'status': 'VERIFICATION_FAILED', 'reason': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
