import copy
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
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('source_cells_missing', result.stdout)


if __name__ == '__main__':
    unittest.main()
