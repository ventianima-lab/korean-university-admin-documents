"""Synthetic read-only shared-calendar-source checks."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from verify_calendar_shared_sources import verify


class SharedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.doc = self.root / 'shared.hwpx'
        self.doc.write_bytes(b'synthetic current document')
        self.other = self.root / 'other.hwpx'
        self.other.write_bytes(b'unrelated document')
        self.digest = hashlib.sha256(self.doc.read_bytes()).hexdigest()
        self.snapshot = {'version': 7, 'events': []}
        for i in range(13):
            self.snapshot['events'].append({'id': f'event-{i}', 'title': 'synthetic', 'notes': 'preserve',
                'sources': [{'id': f'source-{i}', 'path': str(self.doc), 'sha256': self.digest},
                            {'id': 'other', 'path': str(self.other), 'sha256': 'unrelated stale'}]})

    def run_check(self):
        return verify(self.snapshot, [self.doc])

    def test_one_stale_reference_fails_and_identifies_precise_link(self):
        self.snapshot['events'][9]['sources'][0]['sha256'] = 'a' * 64
        result = self.run_check()
        self.assertEqual(result['status'], 'VERIFICATION_FAILED')
        self.assertEqual(result['references_checked'], 13)
        self.assertEqual(result['issues'], [{'event_id': 'event-9', 'source_id': 'source-9', 'reason': 'hash_mismatch'}])

    def test_only_one_link_updated_leaves_twelve_failures(self):
        for event in self.snapshot['events'][1:]:
            event['sources'][0]['sha256'] = 'a' * 64
        result = self.run_check()
        self.assertEqual(result['status'], 'VERIFICATION_FAILED')
        self.assertEqual(result['references_checked'], 13)
        self.assertEqual(len(result['issues']), 12)
        self.assertNotIn('event-0', {issue['event_id'] for issue in result['issues']})

    def test_all_updated_pass_and_inputs_unchanged(self):
        original = copy.deepcopy(self.snapshot)
        contents = {p: p.read_bytes() for p in (self.doc, self.other)}
        result = self.run_check()
        self.assertEqual((result['status'], result['references_checked']), ('PASS', 13))
        self.assertEqual(original, self.snapshot)
        self.assertEqual(contents, {p: p.read_bytes() for p in contents})

    def test_multiple_references_in_one_event_all_checked(self):
        self.snapshot['events'][0]['sources'].append({'id': 'additional', 'path': str(self.doc), 'sha256': 'b' * 64})
        result = self.run_check()
        self.assertEqual(result['references_checked'], 14)
        self.assertEqual(result['issues'][0]['source_id'], 'additional')

    def test_missing_and_invalid_hash_fail(self):
        for bad in (None, '', 'bad'):
            with self.subTest(bad=bad):
                source = self.snapshot['events'][0]['sources'][0]
                if bad is None:
                    source.pop('sha256', None)
                else:
                    source['sha256'] = bad
                self.assertEqual(self.run_check()['issues'][0]['reason'], 'missing_or_invalid_hash')

    def test_file_content_changed_fails_existing_links(self):
        self.doc.write_bytes(b'synthetic damaged bytes')
        result = self.run_check()
        self.assertEqual(result['status'], 'VERIFICATION_FAILED')
        self.assertEqual(len(result['issues']), 13)

    def test_missing_selected_file_fails(self):
        self.doc.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.run_check()

    def test_missing_unrelated_file_and_url_only_source_are_ignored(self):
        self.other.unlink()
        self.snapshot['events'][0]['sources'].append({'id': 'web', 'url': 'https://example.org/'})
        self.assertEqual(self.run_check()['status'], 'PASS')

    def test_no_link_fails_closed(self):
        self.assertEqual(verify(self.snapshot, [self.other])['status'], 'VERIFICATION_FAILED')
        self.snapshot['events'].clear()
        self.assertEqual(self.run_check()['issues'][0]['reason'], 'no_matching_reference')

    def test_multiple_selected_documents_checked_separately(self):
        digest = hashlib.sha256(self.other.read_bytes()).hexdigest()
        for event in self.snapshot['events']:
            event['sources'][1]['sha256'] = digest
        self.assertEqual(verify(self.snapshot, [self.doc, self.other])['references_checked'], 26)
        self.snapshot['events'][-1]['sources'][1]['sha256'] = 'f' * 64
        self.assertEqual(verify(self.snapshot, [self.doc, self.other])['status'], 'VERIFICATION_FAILED')

    def test_source_path_alias_and_case_of_hash(self):
        self.snapshot['events'][0]['sources'][0].update(path=str(self.root / '.' / 'shared.hwpx'), sha256=self.digest.upper())
        self.assertEqual(self.run_check()['status'], 'PASS')

    def test_existing_hardlink_alias_is_checked(self):
        alias = self.root / 'alias.hwpx'
        try:
            os.link(self.doc, alias)
        except OSError:
            self.skipTest('Hard links unavailable in temporary directory')
        self.snapshot['events'][0]['sources'][0].update(path=str(alias), sha256='b' * 64)
        result = self.run_check()
        self.assertEqual(result['references_checked'], 13)
        self.assertEqual(result['issues'][0]['event_id'], 'event-0')

    def test_unmatched_selected_file_and_duplicate_selected_file_fail(self):
        unlinked = self.root / 'unlinked.hwpx'
        unlinked.write_bytes(b'not referenced')
        self.assertEqual(verify(self.snapshot, [self.doc, unlinked])['issues'],
                         [{'document_index': 1, 'reason': 'no_matching_reference'}])
        with self.assertRaisesRegex(ValueError, 'unique'):
            verify(self.snapshot, [self.doc, self.doc])
        with self.assertRaisesRegex(ValueError, 'absolute'):
            verify(self.snapshot, [Path('relative.hwpx')])

    def test_duplicate_or_invalid_inventory_fails_closed(self):
        for mutation in ('event', 'source', 'relative', 'sources', 'version', 'failed_response'):
            with self.subTest(mutation=mutation):
                snapshot = copy.deepcopy(self.snapshot)
                if mutation == 'event': snapshot['events'].append(copy.deepcopy(snapshot['events'][0]))
                if mutation == 'source': snapshot['events'][0]['sources'].append(copy.deepcopy(snapshot['events'][0]['sources'][0]))
                if mutation == 'relative': snapshot['events'][0]['sources'][0]['path'] = 'shared.hwpx'
                if mutation == 'sources': snapshot['events'][0]['sources'] = None
                if mutation == 'version': snapshot['version'] = True
                if mutation == 'failed_response': snapshot['ok'] = False
                with self.assertRaises(ValueError): verify(snapshot, [self.doc])

    def test_file_changes_during_check_fail(self):
        from verify_calendar_shared_sources import _digest
        def change_after_first(path):
            result = _digest(path)
            if path.read_bytes() == b'synthetic current document':
                path.write_bytes(b'changed during check')
            return result
        with patch('verify_calendar_shared_sources._digest', side_effect=change_after_first):
            with self.assertRaisesRegex(ValueError, 'changed during'):
                self.run_check()

    def test_cli_pass_fail_and_read_only(self):
        inventory = self.root / 'snapshot.json'
        inventory.write_text(json.dumps(self.snapshot), encoding='utf-8')
        command = [sys.executable, '-B', str(Path(__file__).with_name('verify_calendar_shared_sources.py')),
                   str(inventory), '--document', str(self.doc)]
        options = {'capture_output': True, 'text': True, 'encoding': 'utf-8'}
        if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NO_WINDOW
        old = {p: p.read_bytes() for p in (inventory, self.doc, self.other)}
        result = subprocess.run(command, **options)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['references_checked'], 13)
        self.assertEqual(old, {p: p.read_bytes() for p in old})
        self.snapshot['events'][1]['sources'][0]['sha256'] = '0' * 64
        inventory.write_text(json.dumps(self.snapshot), encoding='utf-8')
        old = {p: p.read_bytes() for p in (inventory, self.doc, self.other)}
        result = subprocess.run(command, **options)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'VERIFICATION_FAILED')
        self.assertEqual(old, {p: p.read_bytes() for p in old})

    def test_cli_malformed_and_missing_snapshot_fail(self):
        inventory = self.root / 'bad.json'
        inventory.write_text('{', encoding='utf-8')
        command = [sys.executable, '-B', str(Path(__file__).with_name('verify_calendar_shared_sources.py')),
                   str(inventory), '--document', str(self.doc)]
        options = {'capture_output': True, 'text': True, 'encoding': 'utf-8'}
        if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NO_WINDOW
        self.assertEqual(subprocess.run(command, **options).returncode, 1)
        inventory.unlink()
        self.assertEqual(subprocess.run(command, **options).returncode, 1)


if __name__ == '__main__':
    unittest.main()
