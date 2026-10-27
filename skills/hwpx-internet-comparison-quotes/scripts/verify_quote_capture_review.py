"""Validate a human visual review bound to exact HWPX, captures and page renders.

This checks review completeness and stale files, not screenshot authenticity or OCR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
CHECKS = ('seller_and_total_same_capture', 'only_quoted_product_visible',
          'seller_readable', 'product_photo_visible', 'product_name_readable',
          'options_visible', 'quantity_visible', 'total_visible',
          'shipping_verified', 'discount_verified', 'pointer_free',
          'final_render_readable')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_issues(document: Path, manifest: dict, base: Path) -> list[str]:
    issues = []
    if manifest.get('document_sha256') != digest(document):
        issues.append('document hash mismatch: review is missing or stale')
    with zipfile.ZipFile(document) as archive:
        pictures = [p for name in archive.namelist()
                    if name.startswith('Contents/section') and name.endswith('.xml')
                    for p in ET.fromstring(archive.read(name)).iter(f'{{{HP}}}pic')]
    entries = manifest.get('captures')
    if not isinstance(entries, list) or len(entries) != len(pictures):
        return issues + ['one visual review is required for every picture']
    expected_ids = [p.get('id') for p in pictures]
    if len(set(expected_ids)) != len(expected_ids):
        issues.append('document has duplicate picture ids')
    if [entry.get('picture_id') for entry in entries if isinstance(entry, dict)] != expected_ids:
        issues.append('picture ids or order do not match the document')
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            issues.append(f'capture {index}: invalid review entry')
            continue
        label = f'capture {index}'
        if entry.get('source_kind') not in ('product_detail', 'cart', 'vendor_quote'):
            issues.append(f'{label}: search/list/unknown source is insufficient')
        if not isinstance(entry.get('seller'), str) or not entry['seller'].strip():
            issues.append(f'{label}: readable seller identification is missing')
        for check in CHECKS:
            if entry.get(check) is not True:
                issues.append(f'{label}: {check} is not verified')
        for kind in ('original', 'render'):
            file = entry.get(kind + '_file')
            sha = entry.get(kind + '_sha256')
            path = base / file if isinstance(file, str) and file else None
            if path is None or not path.is_file() or digest(path) != sha:
                issues.append(f'{label}: {kind} file is missing or changed')
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.review.read_text(encoding='utf-8-sig'))
        if not isinstance(manifest, dict):
            raise ValueError('review must be a JSON object')
        issues = review_issues(args.document, manifest, args.review.parent)
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        print(f'FAIL: {error}')
        return 2
    if issues:
        print('FAIL\n' + '\n'.join('- ' + issue for issue in issues))
        return 1
    print('PASS: exact-file visual review is complete; authenticity remains a human check')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
