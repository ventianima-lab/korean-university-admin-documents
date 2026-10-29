#!/usr/bin/env python3
"""Reconcile independently listed document requirements with prepared files.

The JSON input has `requirements` (id, source) and `artifacts` (id, status,
paths, verification). Status is ready, pending, user_action, or not_applicable.
For each ready HWPX file, title_band_checks binds an independently selected
official master to every applicable title area. Other authenticity, signatures,
field correctness, visual layout, and institutional acceptance need review.
"""
import argparse
import json
from pathlib import Path
from zipfile import BadZipFile
import xml.etree.ElementTree as ET

from verify_title_band import check_title_band


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
        title_issues = []
        checks = item.get('title_band_checks', [])
        if (not isinstance(checks, list) or any(not isinstance(c, dict) or
                not isinstance(c.get('path'), str) or not c['path'].strip() for c in checks)):
            raise ValueError('title_band_checks must be a list of entries with paths')
        for path in paths if state == 'ready' else []:
            candidate = Path(path)
            if candidate.suffix.lower() != '.hwpx' or str(path) in bad:
                continue
            selected = [c for c in checks if Path(c.get('path', '')).resolve() == candidate.resolve()]
            if len(selected) != 1:
                title_issues.append({'path': str(path), 'problem': 'title_band_check_missing_or_duplicate'})
                continue
            check = selected[0]
            if check.get('not_applicable') is True:
                if (not check.get('reason', '').strip() or not check.get('source', '').strip()
                        or not Path(check.get('master', '')).is_file()):
                    title_issues.append({'path': str(path), 'problem': 'no_title_band_needs_master_and_reason'})
                continue
            bands = check.get('bands', [])
            if not isinstance(bands, list) or not bands:
                title_issues.append({'path': str(path), 'problem': 'title_band_locations_missing'})
                continue
            for band in bands:
                try:
                    result = check_title_band(candidate, band)
                    if result['status'] != 'PASS':
                        title_issues.append({'path': str(path), 'problem': 'title_band_modified',
                                             'cells': result['issues']})
                except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError) as error:
                    title_issues.append({'path': str(path), 'problem': 'title_band_unverifiable',
                                         'detail': str(error)})
        found[key] = {'id': key, 'status': state, 'missing_files': bad, 'title_band_issues': title_issues}
    results = []
    for key in required:
        results.append(found.get(key, {'id': key, 'status': 'missing_role', 'missing_files': [], 'title_band_issues': []}))
    complete = all(r['status'] in {'ready', 'not_applicable'} and not r['missing_files'] and not r['title_band_issues'] for r in results)
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
