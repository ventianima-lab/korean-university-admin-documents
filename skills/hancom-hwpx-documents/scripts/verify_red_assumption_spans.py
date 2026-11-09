#!/usr/bin/env python3
"""Verify currently or standing-authorized red assumption spans against a pre-color HWPX.

Usage: verify_red_assumption_spans.py BEFORE.hwpx AFTER.hwpx PRIVATE_INVENTORY.json
The private inventory is independently prepared before coloring; see the skill.
Both files must already have identical, independently checked input text. This
checker does not establish provenance truth or that the inventory is exhaustive.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH = '{http://www.hancom.co.kr/hwpml/2011/head}'
SECTION = re.compile(r'Contents/section[0-9]+\.xml')
PROVENANCE = {'assistant_unconfirmed', 'user_confirmed', 'verified_fact',
              'verified_calculation', 'fixed_form'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signature(node, ignore=()):
    return (node.tag, tuple(sorted((k, v) for k, v in node.attrib.items() if k not in ignore)),
            node.text, node.tail, tuple(signature(child) for child in node))


def header_data(data):
    root = ET.fromstring(data)
    containers = list(root.iter(HH + 'charProperties'))
    if len(containers) != 1:
        raise ValueError('one charProperties container is required')
    cp = containers[0]
    properties = {}
    for node in cp:
        if node.tag != HH + 'charPr' or node.get('id') is None:
            raise ValueError('unsupported character property entry')
        key = node.get('id')
        if key in properties or not re.fullmatch(r'#[0-9a-fA-F]{6}', node.get('textColor', '')):
            raise ValueError('duplicate style id or invalid textColor')
        properties[key] = node
    # itemCnt may grow only to reflect actual added styles; preserve every
    # other container attribute and the surrounding header structure.
    attrs = dict(cp.attrib)
    if 'itemCnt' in attrs:
        if not attrs['itemCnt'].isdigit() or int(attrs['itemCnt']) != len(properties):
            raise ValueError('character property count mismatch')
        del attrs['itemCnt']
    original_text, original_tail = cp.text, cp.tail
    cp.clear()
    cp.tag = 'AUTHORIZED_CHARACTER_PROPERTY_LIST'
    cp.attrib.update(attrs)
    cp.text, cp.tail = original_text, original_tail
    return signature(root), properties


def section_data(data, props):
    root = ET.fromstring(data)
    paragraphs = []
    used_styles = set()

    def visit(node):
        if node.tag != HP + 'p':
            return (node.tag, tuple(sorted(node.attrib.items())), node.text, node.tail,
                    tuple(visit(child) for child in node))
        index = len(paragraphs)
        paragraphs.append(None)
        tokens = []
        chars = []
        def add_text(s):
            if tokens and tokens[-1][0] == 'text':
                tokens[-1] = ('text', tokens[-1][1] + s)
            else:
                tokens.append(('text', s))
        for child in node:
            if child.tag != HP + 'run':
                tokens.append(('node', visit(child)))
                continue
            # Avoid silently losing attributes when normalizing split text runs.
            if set(child.attrib) != {'charPrIDRef'} or child.text or child.tail:
                raise ValueError('unsupported run attributes or mixed run content')
            style = child.get('charPrIDRef')
            if style not in props:
                raise ValueError('unknown character property reference')
            if not len(child):
                tokens.append(('empty_run', style))
            for item in child:
                if item.tag == HP + 't':
                    if len(item) or item.tail or item.attrib:
                        raise ValueError('unsupported inline text control')
                    text = item.text or ''
                    if not text:
                        tokens.append(('empty_text', style))
                    else:
                        add_text(text)
                        used_styles.add(style)
                        chars.extend((ch, style) for ch in text)
                else:
                    # Keep style of run-owned non-text controls and all structure.
                    tokens.append(('run_node', style, visit(item)))
        paragraphs[index] = chars
        return (node.tag, tuple(sorted(node.attrib.items())), node.text, node.tail, tuple(tokens))
    shape = visit(root)
    return shape, paragraphs, used_styles


def read_package(path):
    with ZipFile(path) as package:
        names = package.namelist()
        if len(set(names)) != len(names):
            raise ValueError('duplicate package part')
        parts = {n for n in names if not n.startswith('Preview/')}
        if 'Contents/header.xml' not in parts:
            raise ValueError('missing header')
        sections = {n for n in parts if SECTION.fullmatch(n)}
        if not sections:
            raise ValueError('missing section')
        header, props = header_data(package.read('Contents/header.xml'))
        data = {n: section_data(package.read(n), props) for n in sections}
        other = {n: package.read(n) for n in parts - sections - {'Contents/header.xml'}}
        return header, props, data, other


def verify(before, after, spec):
    if before.resolve() == after.resolve():
        raise ValueError('pre-color baseline and saved target must be distinct')
    for key, path in [('before_sha256', before), ('after_sha256', after)]:
        expected = spec.get(key)
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            raise ValueError('both exact file hashes are required')
        if sha(path).lower() != expected.lower():
            raise ValueError('file hash mismatch: ' + key)
    if not isinstance(spec.get('red_instruction'), str) or not spec['red_instruction'].strip():
        raise ValueError('current or standing user instruction reference is required')
    if spec.get('red_instruction_scope', 'current_request') not in {'current_request', 'standing_preference'}:
        raise ValueError('red_instruction_scope must be current_request or standing_preference')
    red = spec.get('red_color', '')
    if not isinstance(red, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', red):
        raise ValueError('explicit red color must be #RRGGBB')
    rgb = tuple(int(red[n:n+2], 16) for n in (1, 3, 5))
    if rgb[0] < 128 or rgb[1] > 40 or rgb[2] > 40:
        raise ValueError('specified color is not a supported red')
    red = red.upper()
    values = spec.get('values')
    if not isinstance(values, list) or not values:
        raise ValueError('independently sourced value inventory is required')
    left_header, left_props, left_sections, left_other = read_package(before)
    right_header, right_props, right_sections, right_other = read_package(after)
    if left_header != right_header or left_other != right_other:
        raise ValueError('protected non-preview package or header definition changed')
    if set(left_sections) != set(right_sections):
        raise ValueError('sections changed')
    for key, value in left_props.items():
        if key not in right_props or signature(value) != signature(right_props[key]):
            raise ValueError('existing character style definition changed')
    marks = {}
    for item in values:
        if not isinstance(item, dict):
            raise ValueError('invalid value entry')
        section, para = item.get('section'), item.get('paragraph')
        start, end = item.get('start'), item.get('end')
        if (section not in left_sections or type(para) is not int or para < 0 or
                para >= len(left_sections[section][1]) or type(start) is not int or
                type(end) is not int or start < 0 or end <= start or
                item.get('provenance') not in PROVENANCE or
                not isinstance(item.get('evidence'), str) or not item['evidence'].strip() or
                not isinstance(item.get('text'), str)):
            raise ValueError('invalid source-mapped span')
        text = ''.join(ch for ch, _ in left_sections[section][1][para])
        if end > len(text) or text[start:end] != item['text']:
            raise ValueError('inventory span or expected text mismatch')
        for pos in range(start, end):
            key = (section, para, pos)
            if key in marks:
                raise ValueError('overlapping source-mapped values')
            marks[key] = item['provenance']
    extra_styles_used = set()
    count_red = 0
    count_chars = 0
    for section in sorted(left_sections):
        before_shape, before_paras, _ = left_sections[section]
        after_shape, after_paras, _ = right_sections[section]
        if before_shape != after_shape or len(before_paras) != len(after_paras):
            raise ValueError('protected form structure or text changed: ' + section)
        for para, (old, new) in enumerate(zip(before_paras, after_paras)):
            if len(old) != len(new):
                raise ValueError('paragraph text length changed')
            for pos, ((old_char, old_id), (new_char, new_id)) in enumerate(zip(old, new)):
                if old_char != new_char:
                    raise ValueError('paragraph text changed')
                a, b = left_props[old_id], right_props[new_id]
                if signature(a, ('id', 'textColor')) != signature(b, ('id', 'textColor')):
                    raise ValueError('font or other character styling changed')
                old_color, new_color = a.get('textColor').upper(), b.get('textColor').upper()
                marked = marks.get((section, para, pos)) == 'assistant_unconfirmed'
                if marked and new_color != red:
                    raise ValueError('unconfirmed assistant value missing requested red')
                if not marked and new_color != old_color:
                    raise ValueError('color change outside authorized assumption span')
                if new_id not in left_props:
                    if not marked:
                        raise ValueError('new character style used outside authorized assumption span')
                    extra_styles_used.add(new_id)
                count_red += int(marked)
                count_chars += 1
    if set(right_props) - set(left_props) != extra_styles_used:
        raise ValueError('unused or unauthorized added character style')
    if sha(before).lower() != spec['before_sha256'].lower() or sha(after).lower() != spec['after_sha256'].lower():
        raise ValueError('file changed during verification')
    return {'status': 'PASS', 'mapped_values': len(values), 'assumption_characters': count_red,
            'total_characters': count_chars,
            'scope': 'exact text, structure, font properties and color; source truth, inventory completeness and visual rendering require separate review'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('inventory', type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads(args.inventory.read_text(encoding='utf-8-sig'))
        result = verify(args.before, args.after, spec)
    except (OSError, KeyError, TypeError, ValueError, BadZipFile, ET.ParseError) as error:
        print('RED_ASSUMPTION_CHECK_FAILED: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
