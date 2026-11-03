#!/usr/bin/env python3
"""Verify every calendar reference to selected shared files, without writing.

Usage: verify_calendar_shared_sources.py SNAPSHOT.json --document PATH [--document PATH ...]
SNAPSHOT.json is an independently captured complete calendar API response with
integer version and events; each event contains id and sources, whose entries
contain id, path and sha256. Documents and nonempty source paths must be
absolute. Each selected document must have at least one reference. File paths
are normalized using the current platform; existing hard-link aliases are also
matched. Missing, malformed or stale hashes on any selected link fail.

The caller must independently establish that the snapshot is a fresh, complete
API response, and re-fetch/re-run after any concurrent edit or before/after a
scan/finish. This tool does not access the API, update calendar fields, validate
file contents, or prove capture completeness, authenticity or future stability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re


def _identity(path):
    return os.path.normcase(os.path.realpath(path))


def _digest(path):
    # Verify identity and metadata around the read to detect ordinary concurrent edits.
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        after = os.fstat(stream.fileno())
    current = path.stat()
    key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if key(before) != key(after) or key(after) != key(current):
        raise ValueError('A selected document changed during verification')
    return digest.hexdigest()


def verify(snapshot, documents):
    if (not isinstance(snapshot, dict) or snapshot.get('ok', True) is not True
            or type(snapshot.get('version')) is not int
            or snapshot['version'] < 0 or not isinstance(snapshot.get('events'), list)):
        raise ValueError('A complete versioned calendar snapshot is required')
    if not documents:
        raise ValueError('At least one absolute selected document is required')
    paths = []
    for value in documents:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError('Selected document paths must be absolute')
        if not path.is_file():
            raise ValueError('A selected document is missing or not a file')
        if any(_identity(path) == _identity(other) or os.path.samefile(path, other) for other in paths):
            raise ValueError('Selected documents must be unique')
        paths.append(path)
    digests = [_digest(path) for path in paths]
    counts = [0] * len(paths)
    issues = []
    event_ids = set()
    for event in snapshot['events']:
        if not isinstance(event, dict) or not isinstance(event.get('id'), str) or not event['id'].strip():
            raise ValueError('Every calendar event needs a stable identity')
        event_id = event['id']
        if event_id in event_ids:
            raise ValueError('Duplicate calendar event identity')
        event_ids.add(event_id)
        sources = event.get('sources', [])
        if not isinstance(sources, list):
            raise ValueError('Event sources must be a list')
        source_ids = set()
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source['id'].strip():
                raise ValueError('Every source needs a stable identity')
            source_id = source['id']
            if source_id in source_ids:
                raise ValueError('Duplicate source identity within an event')
            source_ids.add(source_id)
            raw = source.get('path', '')
            if not isinstance(raw, str) or '\x00' in raw:
                raise ValueError('A source path is invalid')
            if not raw:
                continue
            candidate = Path(raw)
            if not candidate.is_absolute():
                raise ValueError('Nonempty source paths must be absolute')
            for index, selected in enumerate(paths):
                matches = _identity(candidate) == _identity(selected)
                if not matches:
                    try:
                        matches = os.path.samefile(candidate, selected)
                    except (OSError, ValueError):
                        pass
                if not matches:
                    continue
                counts[index] += 1
                stored = source.get('sha256')
                if not isinstance(stored, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', stored):
                    issues.append({'event_id': event_id, 'source_id': source_id, 'reason': 'missing_or_invalid_hash'})
                elif stored.lower() != digests[index]:
                    issues.append({'event_id': event_id, 'source_id': source_id, 'reason': 'hash_mismatch'})
    for index, count in enumerate(counts):
        if not count:
            issues.append({'document_index': index, 'reason': 'no_matching_reference'})
    if [_digest(path) for path in paths] != digests:
        raise ValueError('A selected document changed during verification')
    return {'status': 'VERIFICATION_FAILED' if issues else 'PASS',
            'calendar_version': snapshot['version'], 'documents_checked': len(paths),
            'references_checked': sum(counts), 'issues': issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--document', action='append', required=True, type=Path)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
        result = verify(snapshot, args.document)
    except (OSError, ValueError, TypeError) as exc:
        result = {'status': 'VERIFICATION_FAILED', 'reason': str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
