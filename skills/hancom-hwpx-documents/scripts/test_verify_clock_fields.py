"""Synthetic clock-field regression: equal durations cannot replace venue times."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from xml.sax.saxutils import escape
from zipfile import ZipFile

from verify_activity_schedule import verify


class ClockFieldTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic-form.hwpx'
        self.rows = [['08:15~09:00', 'Venue A'], ['13:10~13:55', 'Venue B']]
        self.spec = {'section': 'Contents/section0.xml', 'source': 'synthetic current plan',
                     'clock_fields': []}
        for index, (start, end, venue) in enumerate((('08:15', '09:00', 'Venue A'),
                                                    ('13:10', '13:55', 'Venue B'))):
            self.spec['clock_fields'].append({
                'id': f'session-{index}', 'venue': venue, 'start': start, 'end': end,
                'source': 'independent synthetic itinerary session',
                'template_source': 'synthetic form clock-time column',
                'time_cell': {'table': 0, 'row': index, 'col': 0},
                'venue_cell': {'table': 0, 'row': index, 'col': 1}})
        self.package()

    def package(self):
        rows = []
        for row, values in enumerate(self.rows):
            cells = ''.join(f'<hp:tc><hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
                            f'<hp:subList><hp:p><hp:run><hp:t>{escape(value)}</hp:t>'
                            '</hp:run></hp:p></hp:subList></hp:tc>'
                            for col, value in enumerate(values))
            rows.append('<hp:tr>' + cells + '</hp:tr>')
        xml = ('<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
               '<hp:tbl>' + ''.join(rows) + '</hp:tbl></sec>')
        with ZipFile(self.path, 'w') as package:
            package.writestr('Contents/section0.xml', xml)

    def test_source_backed_intervals_and_venues_pass(self):
        self.assertEqual(verify(self.path, self.spec, require_clock=True)['clock_fields_checked'], 2)

    def test_duration_only_fails_even_when_total_duration_is_correct(self):
        self.rows[0][0] = '45분'
        self.rows[1][0] = '45분 (총 90분)'
        self.package()
        with self.assertRaisesRegex(ValueError, 'not duration alone'):
            verify(self.path, self.spec, require_clock=True)

    def test_duration_copied_into_expected_values_is_rejected(self):
        self.spec['clock_fields'][0]['start'] = '45분'
        with self.assertRaisesRegex(ValueError, 'source-backed start/end'):
            verify(self.path, self.spec)

    def test_swapped_equal_duration_intervals_fail(self):
        self.rows[0][0], self.rows[1][0] = self.rows[1][0], self.rows[0][0]
        self.package()
        with self.assertRaisesRegex(ValueError, 'differs from the venue/session source'):
            verify(self.path, self.spec)

    def test_wrong_venue_fails_despite_correct_times(self):
        self.rows[0][1] = 'Venue B'
        self.package()
        with self.assertRaisesRegex(ValueError, 'venue mismatch'):
            verify(self.path, self.spec)

    def test_missing_template_authority_and_invalid_clock_fail(self):
        for key, value in (('template_source', ''), ('end', '25:00')):
            with self.subTest(key=key):
                spec = copy.deepcopy(self.spec)
                spec['clock_fields'][0][key] = value
                with self.assertRaisesRegex(ValueError, 'template authority and source-backed'):
                    verify(self.path, spec)

    def test_duplicate_time_target_cannot_fake_occurrence_coverage(self):
        self.spec['clock_fields'][1]['time_cell'] = dict(self.spec['clock_fields'][0]['time_cell'])
        with self.assertRaisesRegex(ValueError, 'distinct target'):
            verify(self.path, self.spec)

    def test_multiple_ranges_cannot_hide_a_stale_interval(self):
        self.rows[0][0] += ' / 10:15~11:00'
        self.package()
        with self.assertRaisesRegex(ValueError, 'not duration alone'):
            verify(self.path, self.spec)

    def test_cli_requires_nonempty_clock_mapping(self):
        inventory = Path(self.temp.name) / 'inventory.json'
        command = [sys.executable, '-B', str(Path(__file__).with_name('verify_activity_schedule.py')),
                   str(self.path), str(inventory), '--require-clock']
        options = {'capture_output': True, 'text': True, 'encoding': 'utf-8'}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        inventory.write_text(json.dumps(self.spec), encoding='utf-8')
        self.assertEqual(subprocess.run(command, **options).returncode, 0)
        self.spec.pop('clock_fields')
        inventory.write_text(json.dumps(self.spec), encoding='utf-8')
        failed = subprocess.run(command, **options)
        self.assertEqual(failed.returncode, 1)
        self.assertIn('--require-clock', failed.stdout)


if __name__ == '__main__':
    unittest.main()
