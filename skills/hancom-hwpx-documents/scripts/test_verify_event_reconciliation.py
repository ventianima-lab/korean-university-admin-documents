"""Synthetic tests for a confirmed correction across independently inventoried surfaces."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile
import unittest

from verify_activity_schedule import verify, verify_reconciliation


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.spec = {'event': {'id': 'event-a', 'start': '09:20', 'end': '11:20',
                               'source': 'synthetic user confirmation'},
                     'required_surfaces': [], 'surfaces': []}
        for surface_id, kind in [('document-a', 'document'), ('document-b', 'document'),
                                 ('calendar', 'calendar'), ('page', 'page')]:
            self.spec['required_surfaces'].append({'id': surface_id, 'kind': kind})
            old_time = ('09:20', '11:20') if surface_id == 'document-b' else ('14:10', '16:10')
            before = {'surface_id': surface_id, 'records': [
                {'record_id': 'target', 'event_id': 'event-a', 'start': old_time[0], 'end': old_time[1],
                 'conflict_display': 'keep venue warning|time unresolved', 'venue': 'Room A', 'notes': 'keep'},
                {'record_id': 'other', 'event_id': 'event-b', 'start': '14:10', 'end': '16:10',
                 'conflict_display': 'time unresolved', 'venue': 'Room B', 'notes': 'untouched'}]}
            after = copy.deepcopy(before)
            after['records'][0].update(start='09:20', end='11:20', conflict_display='keep venue warning|')
            surface = {'id': surface_id, 'kind': kind, 'target_record_ids': ['target'],
                       'before': {}, 'after': {},
                       'conflict_corrections': [{'stale': 'time unresolved', 'replacement': ''}]}
            self.spec['surfaces'].append(surface)
            self.save(surface, 'before', before)
            self.save(surface, 'after', after)

    def save(self, surface, phase, data, update_hash=True):
        name = surface['id'] + '-' + phase + '.json'
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8')
        (self.root / name).write_bytes(raw)
        if update_hash:
            surface[phase] = {'path': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                              'source': 'synthetic capture'}

    def edit(self, surface_index, phase, action, update_hash=True):
        surface = self.spec['surfaces'][surface_index]
        data = json.loads((self.root / surface[phase]['path']).read_text(encoding='utf-8'))
        action(data)
        self.save(surface, phase, data, update_hash=update_hash)

    def verify(self):
        return verify_reconciliation(self.spec, self.root)

    def test_confirmed_target_and_other_event_same_old_time_pass(self):
        files = list(self.root.glob('*.json'))
        before = {path: path.read_bytes() for path in files}
        result = self.verify()
        self.assertEqual((result['surfaces_checked'], result['target_records_checked'],
                          result['unrelated_records_checked']), (4, 4, 4))
        self.assertEqual(before, {path: path.read_bytes() for path in files})

    def test_wrong_target_time_in_one_document_fails(self):
        self.edit(1, 'after', lambda d: d['records'][0].update(start='14:10', end='16:10'))
        with self.assertRaisesRegex(ValueError, 'Target interval'):
            self.verify()

    def test_other_event_with_same_old_time_cannot_change(self):
        self.edit(2, 'after', lambda d: d['records'][1].update(start='09:20', end='11:20'))
        with self.assertRaisesRegex(ValueError, 'unrelated record changed'):
            self.verify()

    def test_old_conflict_display_blocks_completion(self):
        self.edit(3, 'after', lambda d: d['records'][0].update(conflict_display='keep venue warning|time unresolved'))
        with self.assertRaisesRegex(ValueError, 'conflict display remains'):
            self.verify()

    def test_unrelated_warning_and_target_metadata_cannot_be_erased(self):
        self.edit(2, 'after', lambda d: d['records'][0].update(conflict_display=''))
        with self.assertRaisesRegex(ValueError, 'protected fields'):
            self.verify()
        self.edit(2, 'after', lambda d: d['records'][0].update(conflict_display='keep venue warning|', notes='lost'))
        with self.assertRaisesRegex(ValueError, 'protected fields'):
            self.verify()

    def test_missing_surface_and_missing_conflict_check_fail(self):
        surface = self.spec['surfaces'].pop()
        with self.assertRaisesRegex(ValueError, 'required surface is missing'):
            self.verify()
        self.spec['surfaces'].append(surface)
        surface['conflict_corrections'] = []
        with self.assertRaisesRegex(ValueError, 'stale-conflict check'):
            self.verify()

    def test_wrong_identity_and_unlisted_target_occurrence_fail(self):
        self.edit(0, 'after', lambda d: d['records'][0].update(event_id='event-b'))
        with self.assertRaisesRegex(ValueError, 'identity or occurrence coverage'):
            self.verify()
        self.edit(0, 'after', lambda d: d['records'][0].update(event_id='event-a'))
        for phase in ('before', 'after'):
            self.edit(0, phase, lambda d: d['records'].append(
                {'record_id': 'omitted', 'event_id': 'event-a', 'start': '09:20', 'end': '11:20',
                 'conflict_display': ''}))
        with self.assertRaisesRegex(ValueError, 'identity or occurrence coverage'):
            self.verify()

    def test_duplicate_record_and_missing_authority_fail(self):
        self.edit(0, 'after', lambda d: d['records'].append(copy.deepcopy(d['records'][0])))
        with self.assertRaisesRegex(ValueError, 'Duplicate snapshot record'):
            self.verify()
        self.spec['event']['source'] = ''
        with self.assertRaisesRegex(ValueError, 'independently confirmed'):
            self.verify()

    def test_ambiguous_repeated_conflict_marker_fails_closed(self):
        self.edit(0, 'before', lambda d: d['records'][0].update(
            conflict_display='time unresolved|time unresolved'))
        self.edit(0, 'after', lambda d: d['records'][0].update(conflict_display='|'))
        with self.assertRaisesRegex(ValueError, 'Ambiguous stale-conflict marker'):
            self.verify()

    def test_snapshot_hash_detects_changed_capture(self):
        self.edit(0, 'after', lambda d: d['records'][0].update(venue='different'), update_hash=False)
        with self.assertRaisesRegex(ValueError, 'Snapshot hash mismatch'):
            self.verify()

    def test_synthetic_hwpx_fields_are_verified_before_cross_surface_snapshot(self):
        hp = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
        section = 'Contents/section0.xml'
        headers = ['Activity', 'Time']
        def make_hwpx(name, rows):
            xml_rows = []
            for ri, row in enumerate([headers] + rows):
                cells = []
                for ci, value in enumerate(row):
                    cells.append(f'<hp:tc><hp:cellAddr rowAddr="{ri}" colAddr="{ci}"/>'
                                 f'<hp:cellSpan rowSpan="1" colSpan="1"/><hp:subList>'
                                 f'<hp:p><hp:run><hp:t>{escape(value)}</hp:t></hp:run></hp:p>'
                                 '</hp:subList></hp:tc>')
                xml_rows.append('<hp:tr>' + ''.join(cells) + '</hp:tr>')
            xml = (f'<sec xmlns:hp="{hp}"><hp:p><hp:run>'
                   f'<hp:tbl rowCnt="{len(rows)+1}" colCnt="2">' + ''.join(xml_rows) +
                   '</hp:tbl></hp:run></hp:p></sec>')
            path = self.root / name
            with ZipFile(path, 'w') as package:
                package.writestr(section, xml)
            return path
        def snapshot(path):
            with ZipFile(path) as package:
                root = ET.fromstring(package.read(section))
            rows = list(root.iter('{' + hp + '}tr'))[1:]
            records = []
            for row in rows:
                values = [''.join(t.itertext()) for t in row.iter('{' + hp + '}t')]
                start, end = values[1].split('-')
                target = values[0] == 'Target'
                records.append({'record_id': 'target' if target else 'other',
                                'event_id': 'event-a' if target else 'event-b',
                                'start': start, 'end': end, 'conflict_display': '',
                                'source_location': 'schedule row ' + values[0]})
            return {'surface_id': 'document-a', 'records': records}
        old = make_hwpx('before.hwpx', [['Target', '14:10-16:10'], ['Other', '14:10-16:10']])
        current = make_hwpx('after.hwpx', [['Target', '09:20-11:20'], ['Other', '14:10-16:10']])
        inventory = {'section': section, 'source': 'synthetic authority', 'table': 0, 'headers': headers,
                     'activities': [{'cells': row, 'source': 'synthetic authority'} for row in
                                    [['Target', '09:20-11:20'], ['Other', '14:10-16:10']]]}
        self.assertEqual(verify(current, inventory)['activities'], 2)
        surface = self.spec['surfaces'][0]
        self.save(surface, 'before', snapshot(old))
        self.save(surface, 'after', snapshot(current))
        self.assertEqual(self.verify()['status'], 'PASS')
        changed = make_hwpx('wrong.hwpx', [['Target', '09:20-11:20'], ['Other', '09:20-11:20']])
        with self.assertRaisesRegex(ValueError, 'Schedule cell mismatch'):
            verify(changed, inventory)
        self.save(surface, 'after', snapshot(changed))
        with self.assertRaisesRegex(ValueError, 'unrelated record changed'):
            self.verify()

    def test_all_independently_listed_occurrences_are_checked(self):
        for phase in ('before', 'after'):
            self.edit(0, phase, lambda d: d['records'].append(
                {'record_id': 'second-target', 'event_id': 'event-a',
                 'start': '09:20', 'end': '11:20', 'conflict_display': ''}))
        self.spec['surfaces'][0]['target_record_ids'].append('second-target')
        self.assertEqual(self.verify()['target_records_checked'], 5)
        self.edit(0, 'after', lambda d: d['records'][-1].update(start='14:10'))
        with self.assertRaisesRegex(ValueError, 'Target interval'):
            self.verify()

    def test_cli_pass_and_failure(self):
        inventory = self.root / 'inventory.json'
        inventory.write_text(json.dumps(self.spec), encoding='utf-8')
        cmd = [sys.executable, '-B', str(Path(__file__).with_name('verify_activity_schedule.py')),
               '--reconcile', str(inventory)]
        options = {'capture_output': True, 'text': True, 'encoding': 'utf-8'}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        passed = subprocess.run(cmd, **options)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(json.loads(passed.stdout)['surfaces_checked'], 4)
        self.spec['event']['start'] = '14:10'
        inventory.write_text(json.dumps(self.spec), encoding='utf-8')
        failed = subprocess.run(cmd, **options)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(json.loads(failed.stdout)['status'], 'VERIFICATION_FAILED')


if __name__ == '__main__':
    unittest.main()
