#!/usr/bin/env python3
"""Reconcile independently listed document requirements with prepared files.

The JSON input has `requirements` (id, source) and `artifacts` (id, status,
paths, verification). Status is ready, pending, user_action, or not_applicable.
This checks coverage and file existence, not whether a document is genuine,
signed, authorized, correctly filled, or accepted by a receiving office.
"""
import argparse
import json
from pathlib import Path


def audit(manifest):
    requirements = manifest.get('requirements')
    artifacts = manifest.get('artifacts')
    if not isinstance(requirements, list) or not requirements or not isinstance(artifacts, list):
        raise ValueError('requirements and artifacts must be lists; requirements cannot be empty')
    required = {}
    for item in requirements:
        key = item.get('id', '').strip()
        if not key or key in required or not item.get('source', '').strip():
            raise ValueError('requirement needs a unique id and source')
        required[key] = item
    found = {}
    for item in artifacts:
        key = item.get('id', '').strip()
        if key not in required or key in found:
            raise ValueError('artifact role is duplicate or absent from requirements')
        state = item.get('status')
        if state not in {'ready', 'pending', 'user_action', 'not_applicable'}:
            raise ValueError('invalid artifact status')
        if not item.get('verification', '').strip():
            raise ValueError('every role needs evidence or a specific outstanding action')
        paths = item.get('paths', [])
        if not isinstance(paths, list) or (state == 'ready' and not paths):
            raise ValueError('ready roles need at least one file path')
        bad = [str(p) for p in paths if not Path(p).is_file() or Path(p).stat().st_size == 0]
        found[key] = {'id': key, 'status': state, 'missing_files': bad}
    results = []
    for key in required:
        results.append(found.get(key, {'id': key, 'status': 'missing_role', 'missing_files': []}))
    complete = all(r['status'] in {'ready', 'not_applicable'} and not r['missing_files'] for r in results)
    return {'status': 'PASS' if complete else 'INCOMPLETE', 'requirements': results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    args = p.parse_args()
    try:
        result = audit(json.loads(args.manifest.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(2, f'PACKET_INVENTORY_ERROR: {error}\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
