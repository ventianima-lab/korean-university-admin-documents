#!/usr/bin/env python3
"""Reconcile independently listed document requirements with prepared files.

The JSON input has `requirements` (id, source) and `artifacts` (id, status,
paths, verification). Status is ready, pending, user_action, or not_applicable.
expense_reviews maps each applicable cost category and its independently
transcribed checklist items to requirement roles. For each ready HWPX file,
title_band_checks binds an independently selected official master to each title
area. Optional --advance-source-check compares each transcribed checklist cell
and mapped rows. Applicability, source scope, authenticity, layout and
institutional acceptance still require independent review.
"""
import argparse
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from verify_title_band import check_title_band


def check_advance_sources(reviews):
    """Compare independently classified segments with each selected HWPX cell.

    This checks transcription and mappings, not which source or conditions apply.
    """
    issues = []
    if not isinstance(reviews, list) or not reviews:
        return [{'problem': 'source_review_missing'}]
    for review in reviews:
        category = review.get('category', '')
        items = {item.get('label') for item in review.get('items', []) if isinstance(item, dict)}
        cells = review.get('source_cells')
        if not isinstance(cells, list) or not cells:
            issues.append({'category': category, 'problem': 'source_cells_missing'})
            continue
        if not any(isinstance(c, dict) and c.get('stage') == 'advance' for c in cells):
            issues.append({'category': category, 'problem': 'advance_source_cell_missing'})
        for cell in cells:
            if not isinstance(cell, dict):
                issues.append({'category': category, 'problem': 'invalid_source_cell'})
                continue
            stage = cell.get('stage')
            if stage not in {'advance', 'post'}:
                issues.append({'category': category, 'problem': 'invalid_stage'})
                continue
            if not all(isinstance(cell.get(k), str) and cell[k].strip() for k in
                       ('path', 'section', 'activity_context', 'applicability_basis')):
                issues.append({'category': category, 'problem': 'source_context_missing'})
                continue
            indexes = [cell.get(k) for k in ('table', 'row', 'cell')]
            if any(type(i) is not int or i < 0 for i in indexes):
                issues.append({'category': category, 'problem': 'invalid_source_location'})
                continue
            try:
                with ZipFile(cell['path']) as package:
                    root = ET.fromstring(package.read(cell['section']))
                tables = [e for e in root.iter() if e.tag.endswith('}tbl')]
                rows = [e for e in tables[indexes[0]] if e.tag.endswith('}tr')]
                columns = [e for e in rows[indexes[1]] if e.tag.endswith('}tc')]
                text = ''.join(e.text or '' for e in columns[indexes[2]].iter() if e.tag.endswith('}t'))
            except (OSError, BadZipFile, ET.ParseError, KeyError, IndexError, TypeError) as error:
                issues.append({'category': category, 'problem': 'source_cell_unverifiable', 'detail': str(error)})
                continue
            norm = lambda s: ''.join(s.split())
            normalized = norm(text)
            if ('[시행전]' in normalized and stage != 'advance') or ('[시행후]' in normalized and stage != 'post'):
                issues.append({'category': category, 'problem': 'source_stage_mismatch'})
            segments = cell.get('segments')
            if not isinstance(segments, list) or not segments:
                issues.append({'category': category, 'problem': 'source_segments_missing'})
                continue
            valid = all(isinstance(s, dict) and isinstance(s.get('text'), str) and s['text'].strip()
                        and s.get('kind') in {'context', 'item'} for s in segments)
            if not valid:
                issues.append({'category': category, 'problem': 'source_segment_invalid'})
                continue
            if norm(''.join(s['text'] for s in segments)) != normalized:
                issues.append({'category': category, 'problem': 'source_cell_incomplete_or_changed'})
            required_segments = [s for s in segments if s['kind'] == 'item']
            if not required_segments:
                issues.append({'category': category, 'problem': 'source_items_missing'})
            if stage == 'advance':
                for segment in required_segments:
                    if segment.get('item') not in items:
                        issues.append({'category': category, 'problem': 'source_item_unmapped',
                                       'item': segment.get('item')})
    return issues


def audit(manifest, advance_source_check=False):
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
    expense_issues = []
    reviews = manifest.get('expense_reviews')
    if not isinstance(reviews, list) or not reviews:
        expense_issues.append({'problem': 'expense_category_review_missing'})
    else:
        categories = set()
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError('expense review must be an object')
            category = review.get('category', '').strip()
            source = review.get('source', '').strip()
            items = review.get('items')
            if not category or not source or category in categories or not isinstance(items, list) or not items:
                raise ValueError('expense review needs unique category, source and checklist items')
            categories.add(category)
            labels = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError('expense checklist item must be an object')
                label = item.get('label', '').strip()
                state = item.get('status')
                if not label or label in labels or state not in {'required', 'pending', 'not_applicable'}:
                    raise ValueError('expense checklist item needs unique label and valid status')
                labels.add(label)
                if state == 'pending':
                    expense_issues.append({'category': category, 'item': label, 'problem': 'applicability_pending'})
                elif state == 'not_applicable':
                    if not item.get('reason', '').strip():
                        expense_issues.append({'category': category, 'item': label, 'problem': 'exclusion_reason_missing'})
                elif item.get('requirement_id') not in required:
                    expense_issues.append({'category': category, 'item': label, 'problem': 'required_role_missing'})
                elif found.get(item['requirement_id'], {}).get('status') == 'not_applicable':
                    expense_issues.append({'category': category, 'item': label, 'problem': 'required_role_marked_not_applicable'})
    source_issues = check_advance_sources(reviews) if advance_source_check else []
    complete = (not source_issues and not expense_issues and all(r['status'] in {'ready', 'not_applicable'} and
                not r['missing_files'] and not r['title_band_issues'] for r in results))
    return {'status': 'PASS' if complete else 'INCOMPLETE', 'requirements': results,
            'expense_review_issues': expense_issues, 'source_check_issues': source_issues}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--advance-source-check', action='store_true',
                   help='check advance checklist source-cell transcription and mapped rows')
    args = p.parse_args()
    try:
        result = audit(json.loads(args.manifest.read_text(encoding='utf-8-sig')), args.advance_source_check)
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(2, f'PACKET_INVENTORY_ERROR: {error}\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
