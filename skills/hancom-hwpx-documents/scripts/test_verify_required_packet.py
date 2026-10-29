import importlib.util
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


if __name__ == '__main__':
    unittest.main()
