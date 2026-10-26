#!/usr/bin/env python3
"""Check an explicitly confirmed department/person scope before batch handoff.

Request JSON: department, people (unique names), document_kinds (optional).
Manifest JSON: companies [{teacher, department, company, source}],
artifacts [{teacher, department, kind}]. Source authority needs human review;
this gate detects omissions and accidental expansion after scope is confirmed.
"""
import argparse
import json
from pathlib import Path


def verify(request, manifest):
    department = request['department'].strip()
    people = request['people']
    if not department or not people or len(people) != len(set(people)):
        raise ValueError('Scope requires a department and unique confirmed names')
    expected = set(people)
    companies = manifest['companies']
    actual = [c['teacher'] for c in companies]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Person scope mismatch: missing or additional people')
    for row in companies + manifest.get('artifacts', []):
        if row.get('department') != department or row.get('teacher') not in expected:
            raise ValueError('Department/person outside the confirmed scope')
    for row in companies:
        if not row.get('company', '').strip() or not row.get('source', '').strip():
            raise ValueError('Affiliation requires organization and source')
    required = {(name, kind) for name in people for kind in request.get('document_kinds', [])}
    actual_artifacts = {(row['teacher'], row['kind']) for row in manifest.get('artifacts', [])}
    if required - actual_artifacts:
        raise ValueError('Required document missing for a scoped person')
    return {'status': 'PASS', 'people': len(expected), 'department': department}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
        print(json.dumps(verify(read(args.request), read(args.manifest)), ensure_ascii=False))
    except (KeyError, TypeError, ValueError) as error:
        print('ROSTER_SCOPE_FAILED: ' + str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
