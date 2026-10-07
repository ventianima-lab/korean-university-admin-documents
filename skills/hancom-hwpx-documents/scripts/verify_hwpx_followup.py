#!/usr/bin/env python3
"""Compare preserved HWPX blocks against a snapshot of the live working final.

Exclusions are zero-based direct-child indexes per section, not page numbers.
This check supplements current rendering and inspection inside edited blocks.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusions(values: list[str]) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for value in values:
        part, sep, numbers = value.partition(':')
        if not sep or not numbers or not part.startswith('Contents/section') or not part.endswith('.xml'):
            raise ValueError('Use Contents/sectionN.xml:0,1,2 for each exclusion')
        indexes = {int(n) for n in numbers.split(',')}
        if any(n < 0 for n in indexes) or part in result:
            raise ValueError('Exclusion indexes must be nonnegative; specify each part once')
        result[part] = indexes
    return result


def normalized(element: ET.Element) -> tuple:
    """Ignore only recalculated line caches and nonsemantic object ordering IDs."""
    element = copy.deepcopy(element)
    for parent in element.iter():
        for child in list(parent):
            if child.tag == '{'+HP+'}linesegarray':
                parent.remove(child)
        if parent.tag in {'{'+HP+'}p', '{'+HP+'}tbl', '{'+HP+'}pic'}:
            parent.attrib.pop('id', None)
            parent.attrib.pop('zOrder', None)
    def node(el: ET.Element) -> tuple:
        return (el.tag, tuple(sorted(el.attrib.items())), el.text or '',
                tuple(node(child) for child in el))
    return node(element)


def verify(baseline: Path, candidate: Path, baseline_exclude: dict[str, set[int]],
           candidate_exclude: dict[str, set[int]]) -> dict:
    checked = 0
    with ZipFile(baseline) as before, ZipFile(candidate) as after:
        sections = sorted(n for n in before.namelist() if n.startswith('Contents/section') and n.endswith('.xml'))
        next_sections = sorted(n for n in after.namelist() if n.startswith('Contents/section') and n.endswith('.xml'))
        if sections != next_sections:
            raise ValueError('Section membership changed; use a separately verified topology comparison')
        if set(baseline_exclude) != set(candidate_exclude) or not set(baseline_exclude).issubset(sections):
            raise ValueError('Exclusion parts must exist and match between baseline and candidate')
        for part in sections:
            roots = [ET.fromstring(z.read(part)) for z in (before, after)]
            selected = []
            for root, omit in zip(roots, (baseline_exclude.get(part, set()), candidate_exclude.get(part, set()))):
                if omit and max(omit) >= len(root):
                    raise ValueError('Exclusion index is outside '+part)
                selected.append([normalized(p) for i, p in enumerate(root) if i not in omit])
            if selected[0] != selected[1]:
                raise ValueError('Preserved block content or formatting changed in '+part)
            checked += len(selected[0])
        if normalized(ET.fromstring(before.read('Contents/header.xml'))) != normalized(ET.fromstring(after.read('Contents/header.xml'))):
            raise ValueError('Shared header styles changed; review resolved styles before replacement')
        media_before = {n: hashlib.sha256(before.read(n)).hexdigest() for n in before.namelist() if n.startswith('BinData/')}
        media_after = {n: hashlib.sha256(after.read(n)).hexdigest() for n in after.namelist() if n.startswith('BinData/')}
        if media_before != media_after:
            raise ValueError('Embedded media changed; use an explicit media-specific preservation check')
    if checked == 0:
        raise ValueError('No preserved blocks remain; use a separate field-level preservation check')
    return {'status':'PASS', 'preserved_blocks':checked, 'preserved_media':len(media_before),
            'baseline_sha256':sha256(baseline), 'candidate_sha256':sha256(candidate)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--baseline-exclude', action='append', default=[])
    parser.add_argument('--candidate-exclude', action='append', default=[])
    parser.add_argument('--live-path', type=Path)
    parser.add_argument('--expected-live-sha256')
    args = parser.parse_args()
    try:
        if bool(args.live_path) != bool(args.expected_live_sha256):
            raise ValueError('The live path and expected SHA-256 must be supplied together')
        if args.live_path and sha256(args.live_path).lower() != args.expected_live_sha256.lower():
            raise ValueError('Live working final changed since inspection; reread it before replacing')
        result = verify(args.baseline, args.candidate, exclusions(args.baseline_exclude), exclusions(args.candidate_exclude))
        if args.live_path and sha256(args.baseline).lower() != args.expected_live_sha256.lower():
            raise ValueError('Baseline snapshot does not match the inspected live working final')
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, BadZipFile, ET.ParseError) as exc:
        print(json.dumps({'status':'VERIFICATION_FAILED', 'reason':str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
