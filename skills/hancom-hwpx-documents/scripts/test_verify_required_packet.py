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
        self.assertEqual(packet.audit(m)['status'], 'PASS')

    def test_duplicate_role_and_unexplained_status_fail(self):
        m = {'requirements': [{'id': 'x', 'source': 'manual'}],
             'artifacts': [{'id': 'x', 'status': 'not_applicable', 'paths': [], 'verification': 'not used'}]}
        self.assertEqual(packet.audit(m)['status'], 'PASS')
        m['artifacts'].append(dict(m['artifacts'][0]))
        with self.assertRaises(ValueError):
            packet.audit(m)


if __name__ == '__main__':
    unittest.main()
