"""Synthetic regression tests; no record files, native apps or network access."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from verify_form_source_pack import check_pack, digest


class SourcePackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.active = self.root / 'event-business' / '00-forms'
        self.active.mkdir(parents=True)
        self.official = self.root / 'official'
        self.official.mkdir()
        self.manual = self.official / 'manual.hwpx'
        self.manual.write_bytes(b'synthetic manual: plan form / receipt form / later report')
        self.single = self.official / 'application.hwpx'
        self.single.write_bytes(b'synthetic standalone official application')
        self.manual_copy = self.active / 'source-manual.hwpx'
        self.manual_copy.write_bytes(self.manual.read_bytes())
        self.single_copy = self.active / 'source-application.hwpx'
        self.single_copy.write_bytes(self.single.read_bytes())
        self.blank = self.active / 'blank-receipt.hwpx'
        self.blank.write_bytes(b'synthetic extracted blank receipt form')
        self.final = self.active / 'user-working-final.hwpx'
        self.final.write_bytes(b'user-owned live content; no footer edits authorized')
        self.inventory = {
            'schema_version': 1, 'event_id': 'synthetic-event', 'phase': 'advance',
            'mode': 'followup', 'existing_finals': [str(self.final)],
            'sources': [
                {'id': 'manual', 'path': str(self.manual), 'sha256': digest(self.manual),
                 'authority': 'current synthetic programme instructions'},
                {'id': 'application', 'path': str(self.single), 'sha256': digest(self.single),
                 'authority': 'current synthetic official form'}],
            'requirements': [self.requirement('application', 'standalone', 'application', 'whole file'),
                             self.requirement('receipt', 'embedded', 'manual', 'physical page 2, receipt form')]}
        self.pack = {'schema_version': 1, 'event_id': 'synthetic-event', 'phase': 'advance',
                     'sources': [{'source_id': 'manual', 'path': str(self.manual_copy)},
                                 {'source_id': 'application', 'path': str(self.single_copy)}],
                     'forms': [self.mapping('application', self.single_copy, 'whole file'),
                               self.mapping('receipt', self.blank, 'physical page 2, receipt form')]}

    def requirement(self, rid, kind, sid, location):
        return {'id': rid, 'role': rid, 'phase': 'advance', 'status': 'required',
                'basis': {'source_id': 'manual', 'location': 'advance expense row',
                          'reason': 'applicable to this synthetic event and expense'},
                'form': {'source_id': sid, 'location': location, 'kind': kind}}

    def mapping(self, rid, path, location):
        return {'requirement_id': rid, 'path': str(path), 'sha256': digest(path),
                'source_location': location,
                'extraction_review': 'inspected blank derivative against exact source title and region'}

    def problems(self):
        return {r['problem'] for r in check_pack(self.inventory, self.pack, self.active)}

    def test_complete_pack_passes_and_finals_are_never_hashed(self):
        before = self.final.read_bytes()
        real_digest = digest
        def only_sources(path):
            self.assertNotEqual(path, self.final)
            return real_digest(path)
        with patch('verify_form_source_pack.digest', side_effect=only_sources):
            self.assertEqual(self.problems(), set())
        self.assertEqual(self.final.read_bytes(), before)

    def test_visible_folder_passes_without_reading_working_final(self):
        real_digest = digest
        def only_sources(path):
            self.assertNotEqual(path, self.final)
            return real_digest(path)
        with patch('verify_form_source_pack.digest', side_effect=only_sources):
            self.assertEqual(check_pack(self.inventory, self.pack, self.active.parent,
                                        source_dir=self.active), [])

    def test_source_folder_cannot_be_active_root_or_external(self):
        for source in (self.active, self.official):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'separate subfolder'):
                check_pack(self.inventory, self.pack, self.active, source_dir=source)

    def test_copy_elsewhere_in_active_packet_cannot_pass_source_folder(self):
        selected = self.active / 'Official forms and guidance'
        selected.mkdir()
        with self.assertRaisesRegex(ValueError, 'outside selected official-forms'):
            check_pack(self.inventory, self.pack, self.active, source_dir=selected)

    def test_hidden_folder_and_hidden_file_fail(self):
        hidden = self.active / '.hidden-forms'
        hidden.mkdir()
        with self.assertRaisesRegex(ValueError, 'hidden'):
            check_pack(self.inventory, self.pack, self.active, source_dir=hidden)
        hidden_file = self.active / '.hidden-manual.hwpx'
        hidden_file.write_bytes(self.manual.read_bytes())
        self.pack['sources'][0]['path'] = str(hidden_file)
        with self.assertRaisesRegex(ValueError, 'hidden'):
            check_pack(self.inventory, self.pack, self.active.parent, source_dir=self.active)

    def test_windows_hidden_attribute_and_unreadable_source_fail(self):
        import stat
        real_stat = Path.stat
        def hidden_stat(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            if path == self.active:
                from types import SimpleNamespace
                return SimpleNamespace(st_mode=result.st_mode,
                                       st_file_attributes=stat.FILE_ATTRIBUTE_HIDDEN)
            return result
        with patch.object(Path, 'stat', hidden_stat), self.assertRaisesRegex(ValueError, 'hidden'):
            check_pack(self.inventory, self.pack, self.active.parent, source_dir=self.active)
        with patch('verify_form_source_pack.os.access', return_value=False), self.assertRaisesRegex(ValueError, 'unreadable'):
            check_pack(self.inventory, self.pack, self.active.parent, source_dir=self.active)

    def test_source_folder_link_escape_fails(self):
        link = self.active / 'official-forms-link'
        try:
            link.symlink_to(self.official, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'symlink capability unavailable: {error}')
        with self.assertRaisesRegex(ValueError, 'separate subfolder'):
            check_pack(self.inventory, self.pack, self.active, source_dir=link)

    def test_single_main_form_does_not_cover_missing_applicable_form(self):
        self.pack['forms'].pop()
        self.assertIn('applicable_blank_form_missing', self.problems())

    def test_external_temp_copies_fail_active_boundary(self):
        external = self.root / 'temp-master.hwpx'
        external.write_bytes(self.manual.read_bytes())
        self.pack['sources'][0]['path'] = str(external)
        with self.assertRaisesRegex(ValueError, 'outside active'):
            self.problems()

    def test_missing_active_copy_fails_even_with_authored_form(self):
        self.pack['sources'].pop(0)
        self.assertIn('active_official_source_copy_missing', self.problems())

    def test_copied_manual_alone_cannot_be_embedded_blank(self):
        self.pack['forms'][1] = self.mapping('receipt', self.manual_copy, 'physical page 2, receipt form')
        self.assertIn('whole_manual_is_not_extracted_form', self.problems())

    def test_missing_other_embedded_form_is_not_covered_by_same_manual(self):
        self.inventory['requirements'].append(self.requirement('minutes', 'embedded', 'manual', 'physical page 3'))
        self.assertIn('applicable_blank_form_missing', self.problems())

    def test_later_and_inapplicable_forms_are_not_unconditionally_required(self):
        for status, phase in [('later', 'post'), ('not_applicable', 'advance')]:
            row = self.requirement(status, 'embedded', 'manual', 'physical page 4')
            row.update(status=status, phase=phase)
            self.inventory['requirements'].append(row)
        self.assertEqual(self.problems(), set())

    def test_current_phase_cannot_be_marked_later(self):
        row = self.requirement('hidden', 'embedded', 'manual', 'physical page 4')
        row['status'] = 'later'
        self.inventory['requirements'].append(row)
        self.assertIn('current_phase_cannot_be_deferred_as_later', self.problems())

    def test_unresolved_applicability_blocks(self):
        self.inventory['requirements'][0]['status'] = 'unresolved'
        self.assertIn('applicability_unresolved', self.problems())

    def test_altered_original_and_copy_are_detected(self):
        self.manual.write_bytes(b'changed original')
        self.manual_copy.write_bytes(b'changed copy')
        self.assertIn('official_source_hash_mismatch_or_empty', self.problems())
        self.assertIn('active_source_copy_hash_mismatch', self.problems())

    def test_standalone_filled_output_is_not_blank_original(self):
        self.pack['forms'][0] = self.mapping('application', self.blank, 'whole file')
        self.assertIn('standalone_blank_not_source_identical', self.problems())

    def test_source_coordinate_mismatch_blocks(self):
        self.pack['forms'][1]['source_location'] = 'wrong page'
        self.assertIn('form_source_coordinates_mismatch', self.problems())

    def test_changed_derivative_is_detected(self):
        self.blank.write_bytes(b'changed after selection')
        self.assertIn('blank_form_hash_mismatch', self.problems())

    def test_working_final_cannot_be_template(self):
        self.pack['forms'][1] = self.mapping('receipt', self.final, 'physical page 2, receipt form')
        with self.assertRaisesRegex(ValueError, 'protected working final'):
            self.problems()

    def test_duplicate_role_is_not_coverage(self):
        self.pack['forms'].append(copy.deepcopy(self.pack['forms'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.problems()

    def test_extra_unrequired_form_fails(self):
        self.pack['forms'].append(self.mapping('generic-example', self.blank, 'page 9'))
        self.assertIn('mapped_form_not_currently_required', self.problems())

    def test_hardlink_to_external_source_is_not_independent_copy(self):
        self.manual_copy.unlink()
        self.manual_copy.hardlink_to(self.manual)
        self.assertIn('source_copy_is_link_to_original', self.problems())

    def test_resolved_symlink_escape_is_not_active_copy(self):
        link = self.active / 'linked-manual.hwpx'
        try:
            link.symlink_to(self.manual)
        except OSError as error:
            self.skipTest(f'symlink capability unavailable: {error}')
        self.pack['sources'][0]['path'] = str(link)
        with self.assertRaisesRegex(ValueError, 'outside active'):
            self.problems()

    def test_different_event_cannot_reuse_passing_pack(self):
        self.pack['event_id'] = 'other-event'
        with self.assertRaisesRegex(ValueError, 'event_id'):
            self.problems()

    def test_followup_requires_existing_final_inventory(self):
        self.inventory['existing_finals'] = []
        with self.assertRaisesRegex(ValueError, 'existing working finals'):
            self.problems()

    def test_cli_reads_bom_json_and_failure_exit_is_nonzero(self):
        inv, pack = self.root / 'inventory.json', self.root / 'pack.json'
        inv.write_text(json.dumps(self.inventory), encoding='utf-8-sig')
        pack.write_text(json.dumps(self.pack), encoding='utf-8-sig')
        command = [sys.executable, str(Path(__file__).with_name('verify_form_source_pack.py')),
                   '--inventory', str(inv), '--pack', str(pack), '--active-dir', str(self.active)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASSED')
        self.assertFalse(json.loads(result.stdout)['source_dir_checked'])
        self.assertEqual(json.loads(result.stdout)['event_id'], self.inventory['event_id'])
        self.assertEqual(json.loads(result.stdout)['inventory_sha256'], digest(inv))
        self.assertEqual(json.loads(result.stdout)['pack_sha256'], digest(pack))
        self.assertEqual(json.loads(result.stdout)['checker_sha256'], digest(Path(__file__).with_name('verify_form_source_pack.py')))
        visible_command = command[:-2] + ['--active-dir', str(self.active.parent),
                                         '--source-dir', str(self.active)]
        visible_result = subprocess.run(visible_command, capture_output=True, text=True)
        self.assertEqual(visible_result.returncode, 0, visible_result.stdout + visible_result.stderr)
        self.assertTrue(json.loads(visible_result.stdout)['source_dir_checked'])
        self.assertEqual(json.loads(visible_result.stdout)['source_dir'], str(self.active.resolve()))
        self.pack['forms'].pop()
        pack.write_text(json.dumps(self.pack), encoding='utf-8-sig')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['status'], 'FAILED')
        pack.write_text('{invalid json', encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['status'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
