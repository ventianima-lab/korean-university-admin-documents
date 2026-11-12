#!/usr/bin/env python3
"""Inspect raw HWPX guidance; compare reviewed official form scopes read-only.

See references/form-guidance-gate.md. Semantic authority, scope completeness,
visual fidelity and instruction interpretation require independent review.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import verify_form_source_pack as source_pack_helpers
from verify_form_source_pack import absolute, expected_hash, text, indexed, rows, digest

CHECKER_SHA256 = digest(Path(__file__))
SOURCE_PACK_DEPENDENCY_SHA256 = digest(Path(source_pack_helpers.__file__))


def local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else '#xml-comment'


def canonical(node):
    # Only line-layout caches and whitespace-only serialization are ignored.
    attrs = {k: v for k, v in node.attrib.items() if local(k) not in {'dirty', 'textWidth', 'textHeight'}}
    literal = local(node.tag) in {'t', 'stringParam', '#xml-comment'}
    return [local(node.tag) if not isinstance(node.tag, str) else node.tag,
            sorted(attrs.items()), node.text if node.text is not None and (literal or node.text.strip()) else '',
            node.tail if node.tail and node.tail.strip() else '',
            [canonical(c) for c in node if local(c.tag) != 'linesegarray']]


def fingerprint(node):
    raw = json.dumps(canonical(node), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def is_annotation(node):
    name = local(node.tag).lower()
    return (not isinstance(node.tag, str) or name == 'ctrl'
            or any(word in name for word in ('memo', 'comment', 'annotation'))
            or any('MEMO' in v.upper() or 'COMMENT' in v.upper()
                   for k, v in node.attrib.items() if local(k).lower() in {'type', 'name'}))


def is_memo(node):
    return ('memo' in local(node.tag).lower()
            or (local(node.tag) == 'fieldBegin' and node.get('type', '').upper() == 'MEMO'))


def load_package(path):
    result = {}
    with ZipFile(path) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP entry')
        for name in names:
            if name.lower().endswith(('.xml', '.hpf', '.rels')):
                parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
                result[name] = ET.fromstring(package.read(name), parser=parser)
    if not any(re.fullmatch(r'Contents/section\d+\.xml', name) for name in result):
        raise ValueError('HWPX section XML missing')
    return result


def walk(root, path=(), memo=False):
    memo = memo or is_memo(root)
    yield path, root, memo
    for i, child in enumerate(root):
        yield from walk(child, path + (i,), memo)


def loc(part, path):
    return {'part': part, 'path': list(path)}


def key(location):
    if (not isinstance(location, dict) or not isinstance(location.get('part'), str)
            or not isinstance(location.get('path'), list)
            or any(type(n) is not int or n < 0 for n in location['path'])):
        raise ValueError('location needs part and zero-based nonnegative child path')
    return location['part'], tuple(location['path'])


def node_at(package, location):
    part, path = key(location)
    if part not in package:
        raise ValueError('missing XML part: ' + part)
    node = package[part]
    try:
        for n in path:
            node = node[n]
    except IndexError as error:
        raise ValueError('missing source/target XML node') from error
    return node


def within(location, scopes):
    part, path = key(location)
    return any(part == p and path[:len(s)] == s for p, s in scopes)


def selected_nodes(package, location):
    node = node_at(package, location)
    indexes = location.get('children')
    if indexes is None:
        return node, None
    if (not isinstance(indexes, list) or not indexes
            or any(type(i) is not int or i < 0 or i >= len(node) for i in indexes)
            or indexes != sorted(set(indexes))):
        raise ValueError('children must be unique ascending existing child indexes')
    return node, [node[i] for i in indexes]


def region_fingerprint(node, selected):
    if selected is None:
        return fingerprint(node)
    view = copy.copy(node)
    view[:] = [child for child in selected if child in list(node)]
    return fingerprint(view)


def observe(package):
    texts, annotations, nodes, visible = [], [], [], {}
    flat = [(part, path, node, memo) for part, root in sorted(package.items())
            for path, node, memo in walk(root)]
    reference_index = {}
    memo_ids = {node.get('id') for _, _, node, _ in flat
                if local(node.tag) == 'fieldBegin' and node.get('type', '').upper() == 'MEMO' and node.get('id') is not None}
    for part, path, node, _ in flat:
        for attr, value in node.attrib.items():
            if 'ref' in local(attr).lower():
                reference_index.setdefault(value, []).append(loc(part, path))
    for part, path, node, memo in flat:
        here = loc(part, path)
        ident = part + ':' + '.'.join(map(str, path))
        nodes.append({'location': here, 'tag': local(node.tag), 'sha256': fingerprint(node)})
        if node.text and node.text.strip():
            channel = 'memo_text' if memo else 'raw_xml_text'
            if local(node.tag) == 't' and not memo:
                channel = 'body_text'
                visible.setdefault(part, []).append(node.text)
            texts.append({'id': 'text:' + ident, 'location': here,
                          'channel': channel, 'text': node.text, 'tag': local(node.tag)})
        if node.tail and node.tail.strip():
            texts.append({'id': 'tail:' + ident, 'location': here, 'channel': 'raw_xml_tail',
                          'text': node.tail, 'tag': local(node.tag), 'slot': 'tail'})
        if (is_annotation(node) or (local(node.tag) == 'fieldEnd'
                and node.get('beginIDRef') in memo_ids)):
            ids = {v for k, v in node.attrib.items() if local(k).lower() == 'id'}
            refs = [location for ident in sorted(ids) for location in reference_index.get(ident, [])]
            annotations.append({'id': 'annotation:' + ident, 'location': here,
                                'tag': local(node.tag), 'attributes': dict(node.attrib),
                                'sha256': fingerprint(node), 'reference_candidates': refs,
                                'raw_xml': ET.tostring(node, encoding='unicode')})
    return {'texts': texts, 'annotations': annotations, 'nodes': nodes,
            'visible_body_text': {part: '\n'.join(items) for part, items in visible.items()}}


def styles(package, regions, views=None):
    # Bind actual referenced style definitions, not just equal numeric IDRefs.
    refs = set()
    mapping = {'charPrIDRef': 'charPr', 'paraPrIDRef': 'paraPr',
               'styleIDRef': 'style', 'borderFillIDRef': 'borderFill'}
    def collect(node):
        for child in node.iter():
            for name, value in child.attrib.items():
                if local(name) in mapping:
                    refs.add((mapping[local(name)], value))
    mapped = views if views is not None else [selected_nodes(package, r) for r in regions]
    for node, selected in mapped:
        for item in [c for c in selected if c in list(node)] if selected is not None else [node]:
            collect(item)
    header = package.get('Contents/header.xml')
    result = {}
    if refs and header is None:
        raise ValueError('referenced style header missing')
    if header is not None:
        for node in header.iter():
            if local(node.tag).lower() == 'fontfaces':
                result['fontfaces'] = fingerprint(node)
        done = set()
        while refs - done:
            tag, ident = next(iter(refs - done))
            matches = [n for n in header.iter() if local(n.tag) == tag and n.get('id') == ident]
            if len(matches) != 1:
                raise ValueError(f'undefined/ambiguous style {tag}:{ident}')
            result[tag + ':' + ident] = fingerprint(matches[0])
            done.add((tag, ident))
            collect(matches[0])
    return result


def field_semantic_issues(edit, required=False):
    """Validate declared placement review, not the truth of its authority."""
    mapping = edit.get('field_semantics')
    if mapping is None:
        return ['field_semantics_missing'] if required else []
    if not isinstance(mapping, dict) or any(
            not isinstance(mapping.get(k), str) or not mapping[k].strip()
            for k in ('field_context', 'semantic_role', 'placement_evidence')):
        return ['field_semantics_incomplete']
    if mapping.get('source_kind') not in {'placeholder', 'actual_value', 'operational_phrase', 'blank'}:
        return ['field_semantics_source_kind_invalid']
    if mapping['source_kind'] == 'operational_phrase' and edit.get('old') != edit.get('new'):
        authority = mapping.get('change_authority', {})
        if (not isinstance(authority, dict)
                or authority.get('kind') not in {'explicit_user_instruction', 'field_specific_authority'}
                or any(not isinstance(authority.get(k), str) or not authority[k].strip()
                       for k in ('reference', 'quote'))):
            return ['operational_phrase_replacement_without_placement_authority']
    return []


def check_guidance(spec, source_override=None, target_override=None):
    if not isinstance(spec, dict) or spec.get('schema_version') != 1:
        raise ValueError('guidance schema_version must be 1')
    source = absolute(spec.get('source'), 'guidance.source')
    target = absolute(spec.get('target'), 'guidance.target')
    if source_override is not None and source != Path(source_override).resolve():
        raise ValueError('guidance source is not the role official original')
    if target_override is not None and target != Path(target_override).resolve():
        raise ValueError('guidance target is not the active blank form')
    if digest(source) != expected_hash(spec.get('source_sha256'), 'guidance.source_sha256'):
        raise ValueError('annotated official source hash mismatch')
    stage = spec.get('stage')
    if stage not in {'blank', 'filled'}:
        raise ValueError('stage must be blank or filled')
    if source == target and stage != 'blank':
        raise ValueError('filled guidance comparison needs distinct original and target')
    if stage == 'filled':
        authority = spec.get('content_authority')
        if not isinstance(authority, dict) or authority.get('kind') not in {'live_filled', 'user_facts'}:
            raise ValueError('declare latest content authority separately from structural source')
        text(authority.get('basis'), 'content_authority.basis')
        if authority['kind'] == 'live_filled':
            # Path declaration only: never read/hash the live user-owned final.
            absolute(authority.get('path'), 'content_authority.path', False)
    before, after = load_package(source), load_package(target)
    observed, candidate = observe(before), observe(after)
    texts = {x['id']: x for x in observed['texts']}
    annotations = {x['id']: x for x in observed['annotations']}
    target_annotations = {x['id']: x for x in candidate['annotations']}
    regions = rows(spec.get('regions'), 'regions', True)
    origins, destinations, region_roots = [], [], []
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError('region must map source and target nodes')
        for field, package, used in [('source', before, origins), ('target', after, destinations)]:
            location = region.get(field)
            selected_nodes(package, location)
            part, path = key(location)
            if field == 'source':
                region_roots.append((part, path))
            entries = [(part, path + (i,)) for i in location['children']] if 'children' in location else [(part, path)]
            for entry in entries:
                if any(entry[0] == p and (entry[1][:len(s)] == s or s[:len(entry[1])] == entry[1])
                       for p, s in used):
                    raise ValueError('duplicate/overlapping region')
                used.append(entry)
    issues = []
    def fail(problem, ident=''):
        issues.append({'problem': problem, 'id': ident})
    reviews = indexed(spec.get('text_reviews'), 'id', 'text_reviews')
    ann_reviews = indexed(spec.get('annotation_reviews'), 'id', 'annotation_reviews')
    if set(reviews) != set(texts):
        fail('source_text_review_inventory_incomplete_or_unknown')
    if set(ann_reviews) != set(annotations):
        fail('observed_annotation_inventory_incomplete_or_unknown')
    instructions = indexed(spec.get('instructions'), 'id', 'instructions')
    evidence = {**texts, **annotations}
    for ident, instruction in instructions.items():
        ids = rows(instruction.get('evidence_ids'), ident + '.evidence_ids', True)
        if any(e not in evidence for e in ids):
            raise ValueError('instruction evidence must be observed original text/annotation')
        text(instruction.get('reason'), ident + '.reason')
        applicability = instruction.get('applicability')
        if applicability not in {'applies', 'inapplicable', 'out_of_scope', 'unresolved'}:
            raise ValueError('invalid instruction applicability')
        if applicability == 'unresolved':
            fail('unreviewed_instruction_applicability', ident)
        if instruction.get('permission') not in {'content_only', 'delete_block', 'delete_annotation', 'retain'}:
            raise ValueError('invalid instruction permission')
        if instruction.get('action') not in {'fill', 'delete', 'preserve', 'not_applicable'}:
            raise ValueError('invalid instruction action')
        for scope in rows(instruction.get('scope'), ident + '.scope', True):
            node_at(before, scope)
    for ident, review in reviews.items():
        if ident not in texts:
            continue
        kind = review.get('classification')
        if kind not in {'guidance', 'label', 'placeholder', 'value', 'metadata', 'out_of_scope'}:
            raise ValueError('invalid text classification')
        text(review.get('reason'), ident + '.reason')
        ids = rows(review.get('instruction_ids'), ident + '.instruction_ids')
        if any(i not in instructions for i in ids):
            raise ValueError('unknown text instruction')
        if kind == 'guidance' and not ids:
            fail('guidance_text_has_no_instruction_decision', ident)
        if kind == 'guidance' and any(ident not in instructions[i]['evidence_ids'] for i in ids):
            fail('guidance_decision_not_bound_to_observed_text', ident)
        if texts[ident]['channel'] == 'memo_text' and kind not in {'guidance', 'metadata', 'out_of_scope'}:
            fail('hidden_memo_text_not_reviewed_as_guidance', ident)
        if (texts[ident]['channel'] == 'memo_text' and texts[ident]['tag'] == 't'
                and within(texts[ident]['location'], origins) and kind != 'guidance'):
            fail('selected_memo_instruction_text_cannot_be_metadata', ident)
        if kind == 'out_of_scope' and within(texts[ident]['location'], origins):
            fail('selected_region_text_cannot_be_ignored', ident)

    def permission(iid, location, action, allowed):
        instruction = instructions.get(iid)
        return (instruction is not None and instruction['applicability'] not in {'out_of_scope', 'unresolved'}
                and instruction['action'] == action and instruction['permission'] in allowed
                and within(location, [key(s) for s in instruction['scope']]))

    edits = rows(spec.get('text_edits'), 'text_edits')
    insertions = rows(spec.get('text_insertions', []), 'text_insertions')
    deletions = rows(spec.get('deletions'), 'deletions')
    semantic_required = spec.get('require_field_semantics', False)
    if not isinstance(semantic_required, bool):
        raise ValueError('require_field_semantics must be boolean')
    if stage == 'blank' and (edits or insertions or deletions):
        fail('blank_master_guidance_and_structure_must_be_preserved')
    expected = copy.deepcopy(before)
    expected_annotations = {ident: node_at(expected, obs['location']) for ident, obs in annotations.items()}
    preserved_annotations = []
    comparable_after = copy.deepcopy(after)
    for opener in rows(spec.get('extraction_openers', []), 'extraction_openers'):
        text(opener.get('reason'), 'extraction_opener.reason')
        parts = [node_at(before, p) for p in rows(opener.get('source_parts'), 'source_parts', True)]
        def opener_part(node):
            return (local(node.tag) in {'secPr', 'colPr'}
                    or (local(node.tag) == 'ctrl' and len(node) == 1
                        and local(node[0].tag) == 'colPr'
                        and not (node.text or '').strip()
                        and not (node.tail or '').strip()))
        if (any(not opener_part(n) for n in parts)
                or len({local(n.tag) for n in parts}) != len(parts)):
            raise ValueError('opener source parts must be exact original secPr/colPr or ctrl(colPr) subtrees')
        donor_locations = [key(p) for p in opener['source_parts']]
        donor_parents = {(p, q[:-1]) for p, q in donor_locations if q}
        if len(donor_parents) != 1 or any(not q for _, q in donor_locations):
            raise ValueError('opener properties must come from one original donor run')
        donor_part, donor_path = next(iter(donor_parents))
        donor = node_at(before, loc(donor_part, donor_path))
        if local(donor.tag) != 'run':
            raise ValueError('opener donor must be the actual original run')
        location = opener.get('target')
        node = node_at(comparable_after, location)
        if not within(location, destinations) or local(node.tag) != 'run':
            raise ValueError('opener must be an inserted run in the mapped target')
        actual = [n for n in node if not (local(n.tag) == 't' and not len(n) and not (n.text or '').strip())]
        if ([fingerprint(n) for n in parts] != [fingerprint(n) for n in actual]
                or any(local(k) != 'charPrIDRef' for k in node.attrib)
                or node.attrib != donor.attrib
                or (node.text and node.text.strip()) or (node.tail and node.tail.strip())):
            raise ValueError('opener differs from exact source section/column properties')
        donor_view = copy.copy(donor)
        donor_view[:] = parts
        if styles(before, [], views=[(donor_view, None)]) != styles(after, [], views=[(node, None)]):
            raise ValueError('opener referenced style/font definitions differ from original donor')
        part, path = key(location)
        if not path:
            raise ValueError('opener cannot be the target root')
        parent = node_at(comparable_after, loc(part, path[:-1]))
        parent.remove(node)
    expected_regions = [selected_nodes(expected, r['source']) for r in regions]
    edited = set()
    for edit in edits:
        location = edit.get('source')
        node = node_at(expected, location)
        ident = 'text:' + location['part'] + ':' + '.'.join(map(str, location['path']))
        if key(location) in edited or not within(location, origins):
            raise ValueError('text edit duplicate or outside selected form')
        edited.add(key(location))
        if reviews.get(ident, {}).get('classification') not in {'placeholder', 'value', 'guidance'}:
            fail('fixed_label_or_guidance_is_not_a_fill_value', ident)
        if not permission(edit.get('instruction_id'), location, 'fill', {'content_only'}):
            fail('fill_not_authorized_by_scoped_instruction', ident)
        text(edit.get('content_evidence'), 'text_edit.content_evidence')
        for problem in field_semantic_issues(edit, semantic_required):
            fail(problem, ident)
        if node.text != edit.get('old') or not isinstance(edit.get('new'), str) or len(node):
            raise ValueError('exact leaf text edit mismatch')
        node.text = edit['new']
    inserted = set()
    for insertion in insertions:
        location = insertion.get('parent')
        node = node_at(expected, location)
        if (node.tag != '{http://www.hancom.co.kr/hwpml/2011/paragraph}run'
                or len(node) or (node.text or '').strip() or not within(location, origins)
                or key(location) in inserted):
            raise ValueError('text insertion requires one existing empty original hp:run')
        inserted.add(key(location))
        if not permission(insertion.get('instruction_id'), location, 'fill', {'content_only'}):
            fail('empty_run_insertion_not_source_authorized', str(location))
        text(insertion.get('content_evidence'), 'text_insertion.content_evidence')
        for problem in field_semantic_issues(insertion, semantic_required):
            fail(problem, str(location))
        if not isinstance(insertion.get('new'), str):
            raise ValueError('inserted text must be a string')
        ET.SubElement(node, '{http://www.hancom.co.kr/hwpml/2011/paragraph}t').text = insertion['new']
    deletion_keys = []
    for deletion in deletions:
        location = deletion.get('source')
        node_at(before, location)
        entry = key(location)
        if not entry[1] or entry in region_roots or not within(location, origins):
            raise ValueError('cannot delete whole mapped form or outside source scope')
        if any(entry[0] == p and (entry[1][:len(s)] == s or s[:len(entry[1])] == entry[1])
               for p, s in deletion_keys):
            raise ValueError('duplicate/overlapping deletion')
        if not permission(deletion.get('instruction_id'), location, 'delete', {'delete_block', 'delete_annotation'}):
            fail('structural_deletion_not_source_authorized', str(location))
        deletion_keys.append(entry)
    if stage == 'filled':
        for ident, instruction in instructions.items():
            if instruction['applicability'] not in {'out_of_scope', 'unresolved'}:
                if instruction['action'] == 'fill' and not any(e.get('instruction_id') == ident for e in edits + insertions):
                    fail('applicable_fill_instruction_not_applied', ident)
                if instruction['action'] == 'delete' and not any(d.get('instruction_id') == ident for d in deletions):
                    fail('applicable_deletion_instruction_not_applied', ident)
        for ident, review in reviews.items():
            if ident not in texts or review['classification'] != 'placeholder':
                continue
            location = texts[ident]['location']
            preserved = (review.get('disposition') == 'preserve_fixed_example'
                         and any(permission(i, location, 'preserve', {'retain'})
                                 for i in review['instruction_ids']))
            if (within(location, origins) and key(location) not in edited
                    and not within(location, deletion_keys) and not preserved):
                fail('selected_placeholder_not_resolved_as_actual_input', ident)
    for ident, review in ann_reviews.items():
        if ident not in annotations:
            continue
        obs = annotations[ident]
        if review.get('reviewed') is not True:
            fail('observed_annotation_unreviewed', ident)
        text(review.get('reason'), ident + '.reason')
        if review.get('classification') not in {'instruction', 'metadata', 'out_of_scope'}:
            raise ValueError('invalid annotation classification')
        ids = rows(review.get('instruction_ids'), ident + '.instruction_ids')
        if any(i not in instructions for i in ids):
            raise ValueError('unknown annotation instruction')
        if review['classification'] == 'instruction' and not ids:
            fail('annotation_has_no_instruction_decision', ident)
        if (review['classification'] == 'instruction'
                and any(ident not in instructions[i]['evidence_ids'] for i in ids)):
            fail('annotation_decision_not_bound_to_observed_control', ident)
        observed_node = node_at(before, obs['location'])
        if (local(observed_node.tag) == 'fieldBegin' and observed_node.get('type', '').upper() == 'MEMO'
                and within(obs['location'], origins)
                and any(local(n.tag) == 't' and (n.text or '').strip() for n in observed_node.iter())
                and review['classification'] != 'instruction'):
            fail('selected_memo_control_requires_instruction_review', ident)
        disposition = review.get('disposition')
        if disposition == 'out_of_scope':
            if within(obs['location'], origins) or any(within(r, origins) for r in obs['reference_candidates']):
                fail('selected_or_anchored_annotation_cannot_be_ignored', ident)
        elif disposition == 'preserve':
            target_obs = target_annotations.get(review.get('target_id'))
            if target_obs is None or within(obs['location'], deletion_keys):
                fail('annotated_guidance_missing_or_changed', ident)
            else:
                preserved_annotations.append((ident, target_obs))
        elif disposition == 'delete':
            if stage == 'blank' or not within(obs['location'], deletion_keys):
                fail('annotation_deleted_without_scoped_source_exception', ident)
        else:
            raise ValueError('invalid annotation disposition')
    # Delete deepest/rightmost nodes first so source child paths remain stable.
    for part, path in sorted(deletion_keys, key=lambda v: (len(v[1]), v[1]), reverse=True):
        parent = node_at(expected, loc(part, path[:-1]))
        parent.remove(parent[path[-1]])
    for ident, target_obs in preserved_annotations:
        if target_obs['sha256'] != fingerprint(expected_annotations[ident]):
            fail('annotated_guidance_missing_or_changed', ident)
    for i, region in enumerate(regions):
        target_node, target_selected = selected_nodes(comparable_after, region['target'])
        if region_fingerprint(*expected_regions[i]) != region_fingerprint(target_node, target_selected):
            fail('original_table_labels_merges_or_protected_structure_changed', str(i))
    if styles(expected, [], views=expected_regions) != styles(comparable_after, [r['target'] for r in regions]):
        fail('original_style_or_font_fingerprint_changed')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect', type=Path)
    group.add_argument('--spec', type=Path)
    args = parser.parse_args()
    try:
        if args.inspect:
            result = {'gate': 'FORM_GUIDANCE_OBSERVATIONS', 'status': 'UNREVIEWED',
                      'source_sha256': digest(args.inspect), **observe(load_package(args.inspect))}
            code = 0
        else:
            raw = args.spec.read_bytes()
            spec = json.loads(raw.decode('utf-8-sig'))
            issues = check_guidance(spec)
            result = {'gate': 'FORM_GUIDANCE', 'status': 'FAILED' if issues else 'PASSED',
                      'issues': issues, 'spec_sha256': hashlib.sha256(raw).hexdigest(),
                      'source_sha256': spec['source_sha256'], 'target_sha256': digest(Path(spec['target'])),
                      'field_semantics_required': spec.get('require_field_semantics', False),
                      'scope': 'declared original XML guidance/structure only; semantic and visual review separate'}
            code = 1 if issues else 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, BadZipFile, ET.ParseError) as error:
        result = {'gate': 'FORM_GUIDANCE', 'status': 'FAILED', 'issues': [str(error)]}
        code = 1
    result.update(checker_sha256=CHECKER_SHA256,
                  source_pack_dependency_sha256=SOURCE_PACK_DEPENDENCY_SHA256,
                  checked_at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
