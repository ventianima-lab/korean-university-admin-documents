#!/usr/bin/env python3
"""Check a human-confirmed recipient name in TXT, HWPX, and decoded EML copies."""
from __future__ import annotations

import argparse
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []

    def handle_data(self, data):
        self.text.append(data)


def compact(text):
    return re.sub(r'\s+', '', text)


def check_text(text, required, forbidden, label, require=True):
    value = compact(text)
    if any(compact(name) in value for name in forbidden):
        raise ValueError(f'{label}: superseded name remains')
    if require and compact(required) not in value:
        raise ValueError(f'{label}: confirmed name missing')


def check_hwpx(data, required, forbidden, label):
    with ZipFile(BytesIO(data)) as package:
        sections = [name for name in package.namelist()
                    if re.fullmatch(r'Contents/section\d+\.xml', name)]
        if not sections:
            raise ValueError(f'{label}: no document sections')
        text = []
        for name in sections:
            root = ET.fromstring(package.read(name))
            # Join runs within a paragraph so a name split across styles is checked.
            text.extend(''.join(''.join(t.itertext()) for t in p.iter(HP+'t'))
                        for p in root.iter(HP+'p'))
        check_text('\n'.join(text), required, forbidden, label)
        if 'Preview/PrvText.txt' in package.namelist():
            check_text(package.read('Preview/PrvText.txt').decode('utf-8-sig'),
                       required, forbidden, label+'/preview', require=False)


def verify(path, required, forbidden):
    path = Path(path)
    check_text(path.name, required, forbidden, str(path), require=False)
    data = path.read_bytes()
    if path.suffix.lower() == '.hwpx':
        check_hwpx(data, required, forbidden, str(path))
        return {'file': str(path), 'hwpx_checked': 1}
    if path.suffix.lower() == '.txt':
        check_text(data.decode('utf-8-sig'), required, forbidden, str(path))
        return {'file': str(path), 'text_bodies_checked': 1}
    if path.suffix.lower() != '.eml':
        raise ValueError(f'{path}: expected TXT, HWPX, or EML')
    message = BytesParser(policy=policy.default).parsebytes(data)
    check_text(str(message['Subject'] or ''), required, forbidden,
               str(path)+'/subject', require=False)
    bodies = attachments = 0
    for part in message.walk():
        if part.is_multipart():
            continue
        name = part.get_filename()
        if name:
            check_text(name, required, forbidden, str(path)+'/filename', require=False)
            if name.lower().endswith('.hwpx'):
                check_hwpx(part.get_payload(decode=True), required, forbidden,
                           str(path)+'/'+name)
                attachments += 1
        elif part.get_content_type() in ('text/plain', 'text/html'):
            text = part.get_content()
            if part.get_content_type() == 'text/html':
                parser = VisibleText()
                parser.feed(text)
                text = ''.join(parser.text)
            check_text(text, required, forbidden, str(path)+'/'+part.get_content_type())
            bodies += 1
    if not bodies:
        raise ValueError(f'{path}: no decoded message body')
    return {'file': str(path), 'text_bodies_checked': bodies,
            'hwpx_attachments_checked': attachments}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-name', required=True,
                        help='Exact name confirmed by the human or original evidence')
    parser.add_argument('--forbid-name', action='append', default=[])
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        if not args.require_name.strip() or any(not n.strip() for n in args.forbid_name):
            raise ValueError('Names must be nonempty')
        rows = [verify(p, args.require_name, args.forbid_name) for p in args.files]
    except Exception as error:
        print(json.dumps({'status': 'VERIFICATION_FAILED', 'reason': str(error)},
                         ensure_ascii=False))
        return 1
    print(json.dumps({'status': 'PASS', 'rows': rows}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
