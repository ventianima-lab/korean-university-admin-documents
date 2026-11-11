import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from pathlib import Path
import unittest

module_path = Path(__file__).with_name('verify_required_packet.py')
spec = importlib.util.spec_from_file_location('packet', module_path)
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)


class PacketAuditTest(unittest.TestCase):
    def test_missing_role_and_user_action_cannot_pass(self):
        m = {'requirements': [{'id': 'form', 'source': 'manual'}, {'id': 'receipt', 'source': 'manual'}],
             'artifacts': [{'id': 'receipt', 'status': 'user_action', 'paths': [],
                            'verification': 'attach original receipt'}]}
        r = packet.audit(m)
        self.assertEqual(r['status'], 'INCOMPLETE')
        self.assertEqual(r['requirements'][0]['status'], 'missing_role')

    def test_existing_files_are_required_for_a_ready_role(self):
        path = Path(__file__).with_name('nonexistent-test-document.hwpx')
        m = {'requirements': [{'id': 'form', 'source': 'manual section'}],
             'artifacts': [{'id': 'form', 'status': 'ready', 'paths': [str(path)],
                            'verification': 'exact saved file reviewed'}]}
        self.assertEqual(packet.audit(m)['status'], 'INCOMPLETE')
        m['artifacts'][0]['paths'] = [str(Path(__file__))]
        m['expense_reviews'] = [{'category': 'expense', 'source': 'manual expense section',
                                 'items': [{'label': 'form', 'status': 'required', 'requirement_id': 'form'}]}]
        self.assertEqual(packet.audit(m)['status'], 'PASS')

    def test_cost_checklist_is_mandatory_and_missing_required_form_blocks(self):
        m = {'requirements': [{'id': 'photo', 'source': 'program guide'}],
             'artifacts': [{'id': 'photo', 'status': 'ready', 'paths': [str(Path(__file__))],
                            'verification': 'available'}]}
        self.assertEqual(packet.audit(m)['expense_review_issues'][0]['problem'], 'expense_category_review_missing')
        m['expense_reviews'] = [{'category': 'operating expense', 'source': 'budget rules',
                                 'items': [{'label': 'inspection', 'status': 'required',
                                            'requirement_id': 'inspection'}]}]
        self.assertEqual(packet.audit(m)['expense_review_issues'][0]['problem'], 'required_role_missing')
        m['expense_reviews'][0]['items'][0] = {'label': 'inspection', 'status': 'pending'}
        self.assertEqual(packet.audit(m)['expense_review_issues'][0]['problem'], 'applicability_pending')
        m['expense_reviews'][0]['items'][0] = {'label': 'inspection', 'status': 'not_applicable'}
        self.assertEqual(packet.audit(m)['expense_review_issues'][0]['problem'], 'exclusion_reason_missing')
        m['expense_reviews'][0]['items'][0] = {'label': 'photo', 'status': 'required', 'requirement_id': 'photo'}
        self.assertEqual(packet.audit(m)['status'], 'PASS')

    def test_duplicate_role_and_unexplained_status_fail(self):
        m = {'requirements': [{'id': 'x', 'source': 'manual'}],
             'artifacts': [{'id': 'x', 'status': 'not_applicable', 'paths': [], 'verification': 'not used'}]}
        m['expense_reviews'] = [{'category': 'expense', 'source': 'manual expense section',
                                 'items': [{'label': 'not used', 'status': 'not_applicable', 'reason': 'not triggered'}]}]
        self.assertEqual(packet.audit(m)['status'], 'PASS')
        m['artifacts'].append(dict(m['artifacts'][0]))
        with self.assertRaises(ValueError):
            packet.audit(m)


class EventOutputGroupingTest(unittest.TestCase):
    def test_shared_event_requirement_and_separate_earlier_event(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current, earlier = root / 'event-alpha-signin.txt', root / 'earlier-event-beta-signin.txt'
            current.write_text('Synthetic event-alpha sign-in', encoding='utf-8')
            earlier.write_text('Synthetic earlier event-beta sign-in', encoding='utf-8')
            source = ('Synthetic user instruction: one event-alpha sign-in covers the meal and entry '
                      'associations; retain separate evidence for earlier event-beta.')
            manifest = {
                'requirements': [{'id': key, 'source': source} for key in ('event_alpha', 'event_beta')],
                'artifacts': [{'id': key, 'status': 'ready', 'paths': [str(path)],
                               'verification': 'Synthetic saved event and output grouping reviewed'}
                              for key, path in (('event_alpha', current), ('event_beta', earlier))],
                'expense_reviews': [
                    {'category': category, 'source': source,
                     'items': [{'label': 'event sign-in', 'status': 'required',
                                'requirement_id': 'event_alpha'}]}
                    for category in ('meal', 'entry')
                ] + [{'category': 'earlier event', 'source': source,
                      'items': [{'label': 'earlier event evidence', 'status': 'required',
                                 'requirement_id': 'event_beta'}]}]
            }
            self.assertEqual(packet.audit(manifest)['status'], 'PASS')
            self.assertEqual(len(manifest['artifacts'][0]['paths']), 1)
            split = copy.deepcopy(manifest)
            split['artifacts'].append({'id': 'unrequested_meal_signin', 'status': 'ready',
                                       'paths': [str(current)], 'verification': 'Unrequested split'})
            with self.assertRaisesRegex(ValueError, 'absent from requirements'):
                packet.audit(split)


class OutputGroupGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet_dir = self.root / 'packet'
        self.packet_dir.mkdir()
        self.attendance = self.packet_dir / 'attendance.txt'
        self.attendance.write_text('Synthetic shared attendance', encoding='utf-8')
        self.manifest = {
            'requirements': [{'id': name, 'source': 'Synthetic reviewed event and cost rules'}
                             for name in ('class', 'refreshments')],
            'artifacts': [{'id': name, 'status': 'ready', 'paths': [str(self.attendance)],
                           'verification': 'Synthetic session and population inspected'}
                          for name in ('class', 'refreshments')],
            'expense_reviews': [{'category': name, 'source': 'Synthetic cost rules',
                                 'items': [{'label': 'attendance', 'status': 'required',
                                            'requirement_id': name}]}
                                for name in ('class', 'refreshments')],
            'output_group_check': {
                'packet_directory': str(self.packet_dir), 'active_files': [],
                'groups': [{'id': 'event-attendance',
                            'source': 'Synthetic reviewed authority: one shared session/population output',
                            'requirement_ids': ['class', 'refreshments'], 'expected_file_count': 1}]
            }
        }
        self.snapshot()

    def snapshot(self):
        self.manifest['output_group_check']['active_files'] = [
            {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in self.packet_dir.rglob('*') if p.is_file()]

    def audit(self):
        return packet.audit(self.manifest, output_group_check=True)

    def problems(self):
        return {i['problem'] for i in self.audit()['output_group_issues']}

    def split(self):
        other = self.packet_dir / 'refreshments.txt'
        other.write_bytes(self.attendance.read_bytes())
        self.manifest['artifacts'][1]['paths'] = [str(other)]
        self.snapshot()
        return other

    def test_two_cost_roles_reuse_one_path(self):
        self.assertEqual(self.audit()['status'], 'PASS')
        self.assertEqual(self.problems(), set())

    def test_duplicate_files_even_identical_bytes_cannot_satisfy_one_output(self):
        self.split()
        # The previous API passes this independently plausible two-ID manifest.
        self.assertEqual(packet.audit(self.manifest)['status'], 'PASS')
        self.assertEqual(self.audit()['status'], 'INCOMPLETE')
        self.assertIn('output_group_file_count_mismatch', self.problems())

    def test_independently_authorized_two_outputs_can_pass(self):
        self.split()
        group = self.manifest['output_group_check']['groups'][0]
        group['source'] = 'Synthetic office instruction explicitly requires separate participant confirmations'
        group['expected_file_count'] = 2
        self.assertEqual(self.audit()['status'], 'PASS')

    def test_file_omitted_from_both_manifest_and_snapshot_is_detected(self):
        nested = self.packet_dir / 'nested'
        nested.mkdir()
        (nested / 'unrequested-copy.txt').write_bytes(self.attendance.read_bytes())
        self.assertIn('active_file_unlisted', self.problems())
        self.assertIn('active_file_unmapped', self.problems())

    def test_snapshotted_but_unmapped_extra_file_is_detected(self):
        (self.packet_dir / 'extra.txt').write_text('Synthetic extra', encoding='utf-8')
        self.snapshot()
        self.assertIn('active_file_unmapped', self.problems())
        self.assertNotIn('active_file_unlisted', self.problems())

    def test_stale_hash_and_removed_file_are_detected(self):
        self.attendance.write_text('Synthetic changed content', encoding='utf-8')
        self.assertIn('active_snapshot_hash_mismatch', self.problems())
        self.attendance.unlink()
        self.assertIn('active_snapshot_file_missing', self.problems())
        self.assertIn('group_file_missing', self.problems())

    def test_reviewed_retained_record_does_not_need_an_expense_role(self):
        original = self.packet_dir / 'retained-original.txt'
        original.write_text('Synthetic original', encoding='utf-8')
        self.manifest['output_group_check']['retained_records'] = [
            {'path': 'retained-original.txt', 'source': 'Synthetic explicit instruction to retain original'}]
        self.snapshot()
        self.assertEqual(self.audit()['status'], 'PASS')

    def test_pending_actual_evidence_does_not_mask_group_check_result(self):
        self.manifest['requirements'].append({'id': 'actual_receipt', 'source': 'Synthetic cost rules'})
        self.manifest['artifacts'].append({'id': 'actual_receipt', 'status': 'pending', 'paths': [],
                                           'verification': 'Actual receipt remains outstanding'})
        result = self.audit()
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['output_group_issues'], [])

    def test_new_role_cannot_hide_its_file_as_retained_record(self):
        self.split()
        check = self.manifest['output_group_check']
        check['groups'][0]['requirement_ids'] = ['class']
        check['retained_records'] = [{'path': self.manifest['artifacts'][1]['paths'][0],
                                      'source': 'Synthetic attempted retained-record bypass'}]
        self.assertIn('active_artifact_requirement_ungrouped', self.problems())

    def test_invalid_group_authority_count_and_membership_are_rejected(self):
        base = copy.deepcopy(self.manifest)
        for field, value in [('source', ''), ('expected_file_count', True),
                             ('expected_file_count', -1), ('requirement_ids', ['missing']),
                             ('requirement_ids', ['class', 'class'])]:
            with self.subTest(field=field, value=value):
                self.manifest = copy.deepcopy(base)
                self.manifest['output_group_check']['groups'][0][field] = value
                with self.assertRaises(ValueError):
                    self.audit()

    def test_snapshot_path_escape_and_missing_opt_in_schema_are_rejected(self):
        self.manifest['output_group_check']['active_files'][0]['path'] = '../outside.txt'
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.audit()
        del self.manifest['output_group_check']
        self.assertEqual(packet.audit(self.manifest)['status'], 'PASS')
        with self.assertRaisesRegex(ValueError, 'must be an object'):
            self.audit()

    def test_cli_opt_in_pass_and_duplicate_failure(self):
        manifest_path = self.root / 'manifest.json'
        def run():
            manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
            return subprocess.run([sys.executable, str(module_path), str(manifest_path), '--output-group-check'],
                                  capture_output=True, text=True, encoding='utf-8',
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        good = run()
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)['output_group_issues'], [])
        self.split()
        bad = run()
        self.assertEqual(bad.returncode, 1, bad.stderr)
        self.assertIn('output_group_file_count_mismatch', bad.stdout)


class UserManagedPreparationTest(unittest.TestCase):
    def manifest(self):
        return {
            'requirements': [{'id': 'form', 'source': 'synthetic manual'},
                             {'id': 'voucher', 'source': 'synthetic manual'}],
            'artifacts': [
                {'id': 'form', 'status': 'ready', 'paths': [str(Path(__file__))],
                 'verification': 'Synthetic prepared file reviewed'},
                {'id': 'voucher', 'status': 'user_managed', 'paths': [],
                 'verification': 'Blank attachment area preserved',
                 'user_management': {'kind': 'explicit_user_instruction',
                                     'medium': 'physical', 'action': 'attach',
                                     'reference': 'Synthetic conversation',
                                     'quote': 'I will attach my own voucher.'}}
            ],
            'expense_reviews': [{'category': 'synthetic expense', 'source': 'synthetic manual',
                                 'items': [{'label': 'form', 'status': 'required', 'requirement_id': 'form'},
                                           {'label': 'voucher', 'status': 'required', 'requirement_id': 'voucher'}]}]
        }

    def test_user_managed_is_pass_only_for_authorized_preparation(self):
        manifest = self.manifest()
        self.assertEqual(packet.audit(manifest)['status'], 'INCOMPLETE')
        scoped = packet.audit(manifest, preparation_scope=True)
        self.assertEqual(scoped['status'], 'PASS')
        self.assertEqual(scoped['scope'], 'authorized_preparation')
        self.assertIn('not verified as attached', scoped['scope_note'])
        self.assertEqual(scoped['requirements'][1]['status'], 'user_managed')
        self.assertEqual(scoped['requirements'][1]['missing_files'], [])

    def test_user_management_needs_exact_instruction_and_no_agent_path(self):
        for mutation in ('absent', 'wrong_kind', 'wrong_medium', 'wrong_action', 'blank_reference', 'blank_quote', 'path'):
            manifest = self.manifest()
            voucher = manifest['artifacts'][1]
            if mutation == 'absent':
                del voucher['user_management']
            elif mutation == 'wrong_kind':
                voucher['user_management']['kind'] = 'inferred'
            elif mutation == 'wrong_medium':
                voucher['user_management']['medium'] = 'electronic'
            elif mutation == 'wrong_action':
                voucher['user_management']['action'] = 'unspecified'
            elif mutation == 'blank_reference':
                voucher['user_management']['reference'] = ''
            elif mutation == 'blank_quote':
                voucher['user_management']['quote'] = ' '
            else:
                voucher['paths'] = ['unseen-synthetic-voucher']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                packet.audit(manifest, preparation_scope=True)

    def test_real_pending_missing_and_user_action_still_block_preparation(self):
        for status in ('pending', 'user_action'):
            manifest = self.manifest()
            manifest['artifacts'][0]['status'] = status
            manifest['artifacts'][0]['paths'] = []
            with self.subTest(status=status):
                self.assertEqual(packet.audit(manifest, preparation_scope=True)['status'], 'INCOMPLETE')
        missing = self.manifest()
        del missing['artifacts'][0]
        self.assertEqual(packet.audit(missing, preparation_scope=True)['status'], 'INCOMPLETE')
        unresolved = self.manifest()
        unresolved['expense_reviews'][0]['items'][0]['status'] = 'pending'
        self.assertEqual(packet.audit(unresolved, preparation_scope=True)['status'], 'INCOMPLETE')

    def test_cli_scope_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            path.write_text(json.dumps(self.manifest()), encoding='utf-8')
            def run(*args):
                return subprocess.run([sys.executable, str(module_path), str(path), *args],
                                      capture_output=True, text=True, encoding='utf-8',
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(run().returncode, 1)
            result = run('--preparation-scope')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['scope'], 'authorized_preparation')


class AdvanceSourceCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'manual.hwpx'
        xml = """<hs:section xmlns:hs='urn:test:s' xmlns:hp='urn:test:p'>
          <hp:tbl><hp:tr><hp:tc><hp:p><hp:t>[시행 전] Letter Plan and Students Safety plan and Pledge</hp:t></hp:p></hp:tc></hp:tr>
          <hp:tr><hp:tc><hp:p><hp:t>[시행 후] Receipt</hp:t></hp:p></hp:tc></hp:tr></hp:tbl></hs:section>"""
        with ZipFile(self.source, 'w') as z:
            z.writestr('Contents/section0.xml', xml)
        self.manifest = {
            'requirements': [{'id': x, 'source': 'synthetic source'} for x in ('letter', 'plan', 'students')],
            'artifacts': [{'id': x, 'status': 'ready', 'paths': [str(Path(__file__))],
                           'verification': 'synthetic evidence reviewed'} for x in ('letter', 'plan', 'students')],
            'expense_reviews': [{'category': 'programme', 'source': 'synthetic manual',
                'items': [
                    {'label': 'letter', 'status': 'required', 'requirement_id': 'letter'},
                    {'label': 'plan', 'status': 'required', 'requirement_id': 'plan'},
                    {'label': 'students', 'status': 'required', 'requirement_id': 'students'},
                    {'label': 'safety', 'status': 'not_applicable', 'reason': 'user supplied activity-specific exclusion'},
                    {'label': 'pledge', 'status': 'not_applicable', 'reason': 'user supplied activity-specific exclusion'}],
                'source_cells': [self.cell(0, 'advance', [
                    ('[시행 전]', 'context', None), ('Letter', 'item', 'letter'),
                    ('Plan', 'item', 'plan'), ('and', 'context', None),
                    ('Students', 'item', 'students'), ('Safety plan', 'item', 'safety'),
                    ('and', 'context', None), ('Pledge', 'item', 'pledge')]),
                    self.cell(1, 'post', [('[시행 후]', 'context', None), ('Receipt', 'item', None)])]}]}

    def cell(self, row, stage, segments):
        return {'path': str(self.source), 'section': 'Contents/section0.xml',
                'table': 0, 'row': row, 'cell': 0, 'stage': stage,
                'activity_context': 'synthetic indoor programme',
                'applicability_basis': 'user stated conditional scope; institutional status separate',
                'segments': [dict(text=text, kind=kind, **({'item': item} if item else {}))
                             for text, kind, item in segments]}

    def problems(self, manifest):
        result = packet.audit(manifest, advance_source_check=True)
        return result['status'], {x['problem'] for x in result['source_check_issues'] + result['expense_review_issues']}

    def test_valid_advance_source_keeps_post_event_and_conditional_exclusions_separate(self):
        self.assertEqual(self.problems(self.manifest), ('PASS', set()))

    def test_omitted_source_item_or_unmapped_item_cannot_pass(self):
        missing = copy.deepcopy(self.manifest)
        segments = missing['expense_reviews'][0]['source_cells'][0]['segments']
        segments[:] = [x for x in segments if x.get('item') != 'students']
        status, problems = self.problems(missing)
        self.assertEqual(status, 'INCOMPLETE')
        self.assertIn('source_cell_incomplete_or_changed', problems)
        unmapped = copy.deepcopy(self.manifest)
        items = unmapped['expense_reviews'][0]['items']
        items[:] = [x for x in items if x['label'] != 'students']
        self.assertIn('source_item_unmapped', self.problems(unmapped)[1])

    def test_unresolved_condition_or_unexplained_exclusion_blocks(self):
        pending = copy.deepcopy(self.manifest)
        pending['expense_reviews'][0]['items'][3]['status'] = 'pending'
        self.assertIn('applicability_pending', self.problems(pending)[1])
        unexplained = copy.deepcopy(self.manifest)
        del unexplained['expense_reviews'][0]['items'][3]['reason']
        self.assertIn('exclusion_reason_missing', self.problems(unexplained)[1])

    def test_wrong_stage_or_unreadable_source_blocks(self):
        wrong = copy.deepcopy(self.manifest)
        wrong['expense_reviews'][0]['source_cells'][0]['stage'] = 'post'
        self.assertIn('source_stage_mismatch', self.problems(wrong)[1])
        missing = copy.deepcopy(self.manifest)
        missing['expense_reviews'][0]['source_cells'][0]['path'] = str(self.source) + '.missing'
        self.assertIn('source_cell_unverifiable', self.problems(missing)[1])

    def test_opt_in_requires_sources_and_cli_returns_failure(self):
        missing = copy.deepcopy(self.manifest)
        del missing['expense_reviews'][0]['source_cells']
        self.assertEqual(packet.audit(missing)['status'], 'PASS')
        self.assertIn('source_cells_missing', self.problems(missing)[1])
        target = Path(self.temp.name) / 'audit.json'
        target.write_text(json.dumps(missing), encoding='utf-8')
        result = subprocess.run([sys.executable, str(module_path), str(target), '--advance-source-check'],
                                capture_output=True, text=True, encoding='utf-8',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('source_cells_missing', result.stdout)


if __name__ == '__main__':
    unittest.main()
