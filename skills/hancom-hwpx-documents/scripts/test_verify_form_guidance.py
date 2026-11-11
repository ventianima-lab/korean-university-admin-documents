"""Synthetic annotated-form regressions; never use live records."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from verify_form_guidance import (check_guidance, load_package, observe, node_at,
                                  key, loc, within, digest)
from verify_form_source_pack import check_pack

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HH = 'http://www.hancom.co.kr/hwpml/2011/head'
PART = 'Contents/section4.xml'


def package(path, root, header=None):
    if header is None:
        header = ET.fromstring(f'<h:head xmlns:h="{HH}"><h:fontfaces><h:fontface lang="HANGUL"><h:font id="0" face="SyntheticFont"/></h:fontface></h:fontfaces><h:charPr id="0" height="1000"/><h:paraPr id="0" lineSpacing="150"/></h:head>')
    with ZipFile(path, 'w') as z:
        z.writestr(PART, ET.tostring(root))
        z.writestr('Contents/header.xml', ET.tostring(header))


def make_spec(source, target, regions=None):
    a, b = observe(load_package(source)), observe(load_package(target))
    if regions is None:
        regions = [{'source': loc(PART, []), 'target': loc(PART, [])}]
    scopes = []
    for region in regions:
        part, path = key(region['source'])
        scopes.extend((part, path + (i,)) for i in region['source'].get('children', []))
        if 'children' not in region['source']:
            scopes.append((part, path))
    spec = {'schema_version': 1, 'source': str(source), 'source_sha256': digest(source),
            'target': str(target), 'stage': 'blank', 'regions': regions,
            'text_reviews': [], 'annotation_reviews': [], 'instructions': [],
            'text_edits': [], 'deletions': [], 'extraction_openers': []}
    # Synthetic fixture decisions only; production inspection does not emit PASS specs.
    for t in a['texts']:
        selected = within(t['location'], scopes)
        guidance = selected and (t['channel'] == 'memo_text' and t['tag'] == 't' or t['text'] == 'INLINE: write detailed activities')
        classification = 'out_of_scope' if not selected else 'guidance' if guidance else 'metadata' if t['channel'] == 'memo_text' else 'label'
        iid = 'instruction-' + t['id']
        ids = [iid] if guidance else []
        if guidance:
            spec['instructions'].append({'id': iid, 'evidence_ids': [t['id']],
                                         'applicability': 'applies', 'permission': 'retain',
                                         'action': 'preserve', 'scope': [t['location']],
                                         'reason': 'synthetic original says retain in blank'})
        spec['text_reviews'].append({'id': t['id'], 'classification': classification,
                                     'reason': 'independently classified synthetic text', 'instruction_ids': ids})
    for annotation in a['annotations']:
        selected = within(annotation['location'], scopes)
        ids = []
        if selected:
            iid = 'instruction-' + annotation['id']
            ids = [iid]
            spec['instructions'].append({'id': iid, 'evidence_ids': [annotation['id']],
                                         'applicability': 'applies', 'permission': 'retain',
                                         'action': 'preserve', 'scope': [annotation['location']],
                                         'reason': 'reviewed synthetic instruction control'})
        target = next((n['id'] for n in b['annotations'] if n['sha256'] == annotation['sha256']), None)
        spec['annotation_reviews'].append({'id': annotation['id'], 'reviewed': True,
                                           'classification': 'instruction' if selected else 'out_of_scope',
                                           'reason': 'reviewed synthetic annotation and anchor',
                                           'instruction_ids': ids,
                                           'disposition': 'preserve' if selected else 'out_of_scope',
                                           'target_id': target})
    return spec


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.target = self.root/'official.hwpx', self.root/'blank.hwpx'
        self.xml = ET.fromstring(f'''<p:sec xmlns:p="{HP}">
          <p:p paraPrIDRef="0"><p:run charPrIDRef="0"><p:secPr id="section-original"/><p:colPr type="NEWSPAPER"/></p:run></p:p>
          <p:p paraPrIDRef="0"><p:run charPrIDRef="0"><p:ctrl><p:fieldBegin type="MEMO" id="synthetic-memo"><p:parameters><p:stringParam name="Author">synthetic-author</p:stringParam></p:parameters><p:subList><p:p><p:run><p:t>MEMO: delete trip block only if inapplicable</p:t></p:run></p:p></p:subList></p:fieldBegin></p:ctrl><p:t>OFFICIAL LABEL</p:t></p:run></p:p>
          <p:p paraPrIDRef="0"><p:run charPrIDRef="0"><p:tbl rowCnt="2" colCnt="2"><p:tr><p:tc><p:cellSpan colSpan="2" rowSpan="1"/><p:subList><p:p><p:run><p:t>TOTAL</p:t></p:run></p:p></p:subList></p:tc></p:tr><p:tr><p:tc><p:cellSpan colSpan="1" rowSpan="1"/><p:subList><p:p><p:run><p:t>EXAMPLE INPUT</p:t></p:run></p:p></p:subList></p:tc></p:tr></p:tbl></p:run></p:p>
          <p:p><p:run><p:t>INLINE: write detailed activities</p:t></p:run></p:p>
          <!-- synthetic raw XML comment instruction -->
        </p:sec>''', parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
        package(self.source, self.xml)
        package(self.target, self.xml)
        self.spec = make_spec(self.source, self.target)

    def problems(self):
        return {i['problem'] for i in check_guidance(self.spec)}

    def test_exact_annotated_blank_passes(self):
        self.assertEqual(self.problems(), set())

    def test_hidden_memo_text_is_not_visible_body(self):
        observed = observe(load_package(self.source))
        self.assertNotIn('delete trip', observed['visible_body_text'][PART])
        self.assertTrue(any(t['channel'] == 'memo_text' and 'delete trip' in t['text'] for t in observed['texts']))
        self.assertTrue(any(a['tag'] == '#xml-comment' for a in observed['annotations']))

    def test_omitted_memo_review_cannot_pass(self):
        self.spec['annotation_reviews'].pop(0)
        self.assertIn('observed_annotation_inventory_incomplete_or_unknown', self.problems())

    def test_omitted_inline_instruction_text_review_cannot_pass(self):
        self.spec['text_reviews'].pop()
        self.assertIn('source_text_review_inventory_incomplete_or_unknown', self.problems())

    def test_unreviewed_memo_cannot_pass(self):
        self.spec['annotation_reviews'][0]['reviewed'] = False
        self.assertIn('observed_annotation_unreviewed', self.problems())

    def test_memo_parameter_metadata_cannot_hide_actual_instruction(self):
        observed = observe(load_package(self.source))
        ident = next(t['id'] for t in observed['texts'] if t['channel'] == 'memo_text' and t['tag'] == 't')
        next(r for r in self.spec['text_reviews'] if r['id'] == ident)['classification'] = 'metadata'
        self.assertIn('selected_memo_instruction_text_cannot_be_metadata', self.problems())

    def test_old_free_paragraph_predecessor_cannot_replace_original_table(self):
        changed = copy.deepcopy(self.xml)
        changed[2][0].remove(changed[2][0][0])
        ET.SubElement(changed[2][0], '{'+HP+'}t').text = 'TOTAL EXAMPLE INPUT as free prose'
        package(self.target, changed)
        self.assertIn('original_table_labels_merges_or_protected_structure_changed', self.problems())

    def test_changed_merge_and_fixed_label_fail(self):
        for item in ('merge', 'label'):
            changed = copy.deepcopy(self.xml)
            if item == 'merge':
                next(n for n in changed.iter() if n.tag.endswith('cellSpan')).set('colSpan', '1')
            else:
                next(n for n in changed.iter() if n.text == 'TOTAL').text = 'replacement label'
            package(self.target, changed)
            self.assertIn('original_table_labels_merges_or_protected_structure_changed', self.problems())

    def test_style_definitions_change_even_with_same_id_fails(self):
        header = load_package(self.source)['Contents/header.xml']
        next(n for n in header.iter() if n.tag.endswith('charPr')).set('height', '900')
        package(self.target, self.xml, header)
        self.assertIn('original_style_or_font_fingerprint_changed', self.problems())

    def test_blank_cannot_drop_memo_or_guidance_by_exception(self):
        self.spec['deletions'] = [{'source': loc(PART, [1]), 'instruction_id': self.spec['instructions'][0]['id']}]
        self.assertIn('blank_master_guidance_and_structure_must_be_preserved', self.problems())

    def test_program_content_permission_is_not_layout_permission(self):
        self.spec.update(stage='filled', content_authority={'kind': 'user_facts', 'basis': 'synthetic task'})
        instruction = self.spec['instructions'][0]
        instruction.update(permission='content_only', action='delete', scope=[loc(PART, [2])])
        self.spec['deletions'] = [{'source': loc(PART, [2]), 'instruction_id': instruction['id']}]
        changed = copy.deepcopy(self.xml)
        changed.remove(changed[2])
        package(self.target, changed)
        self.assertIn('structural_deletion_not_source_authorized', self.problems())

    def test_source_authorized_narrow_block_deletion_passes_for_filled_only(self):
        self.spec.update(stage='filled', content_authority={'kind': 'user_facts', 'basis': 'synthetic task'})
        instruction = self.spec['instructions'][0]
        instruction.update(permission='delete_block', action='delete', scope=[loc(PART, [2])], applicability='inapplicable')
        self.spec['deletions'] = [{'source': loc(PART, [2]), 'instruction_id': instruction['id']}]
        changed = copy.deepcopy(self.xml)
        changed.remove(changed[2])
        package(self.target, changed)
        # No memo controls occur in the removed synthetic table; retained controls unchanged.
        targets = observe(load_package(self.target))['annotations']
        originals = {a['id']: a for a in observe(load_package(self.source))['annotations']}
        for review in self.spec['annotation_reviews']:
            review['target_id'] = next(a['id'] for a in targets if a['sha256'] == originals[review['id']]['sha256'])
        self.assertEqual(self.problems(), set())

    def test_exact_selected_paragraphs_and_source_section_opener_pass(self):
        changed = copy.deepcopy(self.xml)
        changed.remove(changed[0])
        opener = copy.deepcopy(self.xml[0][0])
        changed[0].insert(0, opener)
        package(self.target, changed)
        regions = [{'source': {**loc(PART, []), 'children': list(range(1, len(self.xml)))},
                    'target': loc(PART, [])}]
        self.spec = make_spec(self.source, self.target, regions)
        self.spec['extraction_openers'] = [{'source_parts': [loc(PART, [0, 0, 0]), loc(PART, [0, 0, 1])],
                                            'target': loc(PART, [0, 0]), 'reason': 'exact original section/column property transfer'}]
        self.assertEqual(self.problems(), set())
        changed[0][0][0].set('id', 'changed-geometry')
        package(self.target, changed)
        with self.assertRaisesRegex(ValueError, 'opener differs'):
            self.problems()

    def test_source_pack_active_boundary_still_fails_with_guidance(self):
        active = self.root/'active'
        active.mkdir()
        inventory = {'schema_version': 1, 'event_id': 'synthetic', 'phase': 'advance', 'mode': 'create',
                     'existing_finals': [], 'sources': [{'id': 'official', 'path': str(self.source),
                       'sha256': digest(self.source), 'authority': 'synthetic current official'}],
                     'requirements': [{'id': 'form', 'role': 'form', 'phase': 'advance', 'status': 'required',
                       'basis': {'source_id': 'official', 'location': 'synthetic instruction', 'reason': 'applicable'},
                       'form': {'source_id': 'official', 'location': 'selected original section', 'kind': 'standalone'}}]}
        pack = {'schema_version': 1, 'event_id': 'synthetic', 'phase': 'advance',
                'sources': [{'source_id': 'official', 'path': str(self.target)}], 'forms': []}
        with self.assertRaisesRegex(ValueError, 'outside active'):
            check_pack(inventory, pack, active)

    def test_opener_preserves_original_ctrl_column_wrapper_and_start_counter(self):
        donor = self.xml[0][0]
        column = donor[1]
        donor.remove(column)
        wrapped = ET.SubElement(donor, '{'+HP+'}ctrl')
        wrapped.append(column)
        ET.SubElement(donor[0], '{'+HP+'}startNum', {'page': '0'})
        package(self.source, self.xml)
        changed = copy.deepcopy(self.xml)
        changed.remove(changed[0])
        changed[0].insert(0, copy.deepcopy(donor))
        package(self.target, changed)
        regions = [{'source': {**loc(PART, []), 'children': list(range(1, len(self.xml)))}, 'target': loc(PART, [])}]
        self.spec = make_spec(self.source, self.target, regions)
        self.spec['extraction_openers'] = [{'source_parts': [loc(PART, [0,0,0]), loc(PART, [0,0,1])],
          'target': loc(PART, [0,0]), 'reason': 'exact original secPr + ctrl(colPr)'}]
        self.assertEqual(self.problems(), set())
        changed[0][0][0][0].set('page', '1')
        package(self.target, changed)
        with self.assertRaisesRegex(ValueError, 'opener differs'):
            self.problems()

    def test_cli_inspect_does_not_claim_reviewed_pass(self):
        script = str(Path(__file__).with_name('verify_form_guidance.py'))
        result = subprocess.run([sys.executable, script, '--inspect', str(self.source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'UNREVIEWED')

    def test_placeholder_example_needs_actual_evidence_and_fill_mapping(self):
        self.spec.update(stage='filled', content_authority={'kind': 'user_facts', 'basis': 'synthetic actual input'})
        obs = next(t for t in observe(load_package(self.source))['texts'] if t['text'] == 'EXAMPLE INPUT')
        review = next(r for r in self.spec['text_reviews'] if r['id'] == obs['id'])
        review['classification'] = 'placeholder'
        self.assertIn('selected_placeholder_not_resolved_as_actual_input', self.problems())
        self.spec['instructions'].append({'id': 'actual-fill', 'evidence_ids': [obs['id']],
          'applicability': 'applies', 'permission': 'content_only', 'action': 'fill',
          'scope': [obs['location']], 'reason': 'explicit synthetic input-field instruction'})
        self.spec['text_edits'] = [{'source': obs['location'], 'old': 'EXAMPLE INPUT', 'new': 'supported actual input',
          'instruction_id': 'actual-fill', 'content_evidence': 'explicit synthetic user value'}]
        changed = copy.deepcopy(self.xml)
        node_at({PART: changed}, obs['location']).text = 'supported actual input'
        package(self.target, changed)
        self.assertEqual(self.problems(), set())

    def test_memo_paired_field_end_is_observed_as_anchor(self):
        ET.SubElement(self.xml[1][0], '{'+HP+'}fieldEnd', {'beginIDRef': 'synthetic-memo'})
        package(self.source, self.xml)
        observation = observe(load_package(self.source))
        self.assertTrue(any(a['tag'] == 'fieldEnd' for a in observation['annotations']))
        begin = next(a for a in observation['annotations'] if a['tag'] == 'fieldBegin')
        self.assertTrue(begin['reference_candidates'])

    def test_scoped_memo_pair_deletion_preserves_surrounding_control_and_labels(self):
        ET.SubElement(self.xml[1][0], '{'+HP+'}fieldEnd', {'beginIDRef': 'synthetic-memo'})
        package(self.source, self.xml)
        changed = copy.deepcopy(self.xml)
        changed[1][0][0].remove(changed[1][0][0][0])
        changed[1][0].remove(changed[1][0][2])
        package(self.target, changed)
        self.spec = make_spec(self.source, self.target)
        self.spec.update(stage='filled', content_authority={'kind': 'user_facts', 'basis': 'synthetic source-directed note removal'})
        observation = observe(load_package(self.source))
        evidence = []
        replaced = set()
        for row in self.spec['text_reviews']:
            item = next(t for t in observation['texts'] if t['id'] == row['id'])
            if item['channel'] == 'memo_text' and item['tag'] == 't':
                replaced.update(row['instruction_ids'])
                row['instruction_ids'] = ['remove-pair']
                evidence.append(row['id'])
        original_annotations = {a['id']: a for a in observation['annotations']}
        for row in self.spec['annotation_reviews']:
            item = original_annotations[row['id']]
            if item['tag'] in {'fieldBegin', 'fieldEnd'}:
                replaced.update(row['instruction_ids'])
                row.update(instruction_ids=['remove-pair'], disposition='delete')
                evidence.append(row['id'])
            elif item['tag'] == 'ctrl':
                replaced.update(row['instruction_ids'])
                target_control = next(a for a in observe(load_package(self.target))['annotations'] if a['tag'] == 'ctrl')
                row.update(classification='metadata', instruction_ids=[], target_id=target_control['id'])
        self.spec['instructions'] = [i for i in self.spec['instructions'] if i['id'] not in replaced]
        scope = [loc(PART, [1,0,0,0]), loc(PART, [1,0,2])]
        self.spec['instructions'].append({'id': 'remove-pair', 'evidence_ids': evidence,
          'applicability': 'applies', 'permission': 'delete_annotation', 'action': 'delete',
          'scope': scope, 'reason': 'synthetic source explicitly directs paired note removal'})
        self.spec['deletions'] = [{'source': p, 'instruction_id': 'remove-pair'} for p in scope]
        self.assertEqual(self.problems(), set())

    def test_cli_spec_reports_result_hashes_without_path_type_crash(self):
        specfile = self.root/'actual-cli-contract.json'
        specfile.write_text(json.dumps(self.spec), encoding='utf-8')
        command = [sys.executable, str(Path(__file__).with_name('verify_form_guidance.py')), '--spec', str(specfile)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['status'], 'PASSED')
        self.assertEqual(data['target_sha256'], digest(self.target))
        self.assertEqual(data['spec_sha256'], digest(specfile))
        changed = copy.deepcopy(self.xml)
        changed.remove(changed[2])
        package(self.target, changed)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'FAILED')
        self.assertNotIn('Traceback', result.stderr)

    def test_pack_guidance_flag_enforces_review_and_official_original_binding(self):
        active = self.root/'active-realpack'
        active.mkdir()
        blank = active/'official-blank.hwpx'
        blank.write_bytes(self.source.read_bytes())
        guidance = make_spec(self.source, blank)
        specfile = self.root/'private-guidance.json'
        specfile.write_text(json.dumps(guidance), encoding='utf-8')
        inventory = {'schema_version': 1, 'event_id': 'synthetic', 'phase': 'advance', 'mode': 'create',
          'existing_finals': [], 'sources': [{'id': 'official', 'path': str(self.source), 'sha256': digest(self.source),
          'authority': 'synthetic original annotated official'}], 'requirements': [{'id': 'form', 'role': 'form',
          'phase': 'advance', 'status': 'required', 'basis': {'source_id': 'official', 'location': 'current checklist', 'reason': 'applicable'},
          'form': {'source_id': 'official', 'location': 'selected official form', 'kind': 'standalone'}}]}
        pack = {'schema_version': 1, 'event_id': 'synthetic', 'phase': 'advance',
          'sources': [{'source_id': 'official', 'path': str(blank)}], 'forms': [{'requirement_id': 'form', 'path': str(blank),
          'sha256': digest(blank), 'source_location': 'selected official form', 'guidance_spec': str(specfile)}]}
        evidence = []
        self.assertEqual(check_pack(inventory, pack, active, guidance_check=True, guidance_evidence=evidence), [])
        self.assertEqual(evidence[0]['status'], 'PASSED')
        self.assertEqual(evidence[0]['spec_sha256'], digest(specfile))
        invfile, packfile = self.root/'inventory.json', self.root/'pack.json'
        invfile.write_text(json.dumps(inventory), encoding='utf-8')
        packfile.write_text(json.dumps(pack), encoding='utf-8')
        command = [sys.executable, str(Path(__file__).with_name('verify_form_source_pack.py')),
          '--inventory', str(invfile), '--pack', str(packfile), '--active-dir', str(active), '--guidance-check']
        cli = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        result = json.loads(cli.stdout)
        self.assertTrue(result['guidance_checked'])
        self.assertEqual(result['guidance_checks'][0]['spec_sha256'], digest(specfile))
        guidance['annotation_reviews'].pop()
        specfile.write_text(json.dumps(guidance), encoding='utf-8')
        self.assertTrue(check_pack(inventory, pack, active, guidance_check=True))
        predecessor = self.root/'modified-predecessor.hwpx'
        predecessor.write_bytes(self.source.read_bytes())
        guidance['source'] = str(predecessor)
        specfile.write_text(json.dumps(guidance), encoding='utf-8')
        self.assertIn('official_guidance_check_unverifiable', {i['problem'] for i in check_pack(inventory, pack, active, guidance_check=True)})
        del pack['forms'][0]['guidance_spec']
        self.assertIn('annotated_official_guidance_spec_missing', {i['problem'] for i in check_pack(inventory, pack, active, guidance_check=True)})
        self.assertEqual(check_pack(inventory, pack, active), [])

    def test_exact_opener_unique_style_is_checked_then_removed_from_body_style_set(self):
        self.xml[0][0].set('charPrIDRef', '8')
        header = load_package(self.source)['Contents/header.xml']
        ET.SubElement(header, '{'+HH+'}charPr', {'id': '8', 'height': '1100'})
        package(self.source, self.xml, header)
        changed = copy.deepcopy(self.xml)
        changed.remove(changed[0])
        changed[0].insert(0, copy.deepcopy(self.xml[0][0]))
        package(self.target, changed, header)
        regions = [{'source': {**loc(PART, []), 'children': list(range(1, len(self.xml)))}, 'target': loc(PART, [])}]
        self.spec = make_spec(self.source, self.target, regions)
        self.spec['extraction_openers'] = [{'source_parts': [loc(PART, [0,0,0]), loc(PART, [0,0,1])],
          'target': loc(PART, [0,0]), 'reason': 'original donor uses a style outside the selected body'}]
        self.assertEqual(self.problems(), set())
        next(n for n in header if n.get('id') == '8').set('height', '900')
        package(self.target, changed, header)
        with self.assertRaisesRegex(ValueError, 'opener referenced style/font'):
            self.problems()

    def test_empty_original_run_accepts_only_scoped_text_leaf_in_filled_mode(self):
        paragraph = ET.SubElement(self.xml, '{'+HP+'}p')
        ET.SubElement(paragraph, '{'+HP+'}run', {'charPrIDRef': '0'})
        location = loc(PART, [len(self.xml)-1, 0])
        package(self.source, self.xml)
        changed = copy.deepcopy(self.xml)
        ET.SubElement(node_at({PART: changed}, location), '{'+HP+'}t').text = 'supported attachment title'
        package(self.target, changed)
        self.spec = make_spec(self.source, self.target)
        evidence = next(t['id'] for t in observe(load_package(self.source))['texts'] if t['channel'] == 'memo_text' and t['tag'] == 't')
        self.spec['instructions'].append({'id': 'fill-empty', 'evidence_ids': [evidence], 'applicability': 'applies',
          'permission': 'content_only', 'action': 'fill', 'scope': [location], 'reason': 'synthetic source directs field fill'})
        self.spec['text_insertions'] = [{'parent': location, 'new': 'supported attachment title',
          'instruction_id': 'fill-empty', 'content_evidence': 'independently confirmed synthetic attachment'}]
        self.assertIn('blank_master_guidance_and_structure_must_be_preserved', self.problems())
        self.spec.update(stage='filled', content_authority={'kind': 'user_facts', 'basis': 'synthetic current content'})
        self.assertEqual(self.problems(), set())
        self.spec['text_insertions'][0]['parent'] = loc(PART, [1,0])
        with self.assertRaisesRegex(ValueError, 'empty original'):
            self.problems()


if __name__ == '__main__':
    unittest.main()
