"""Synthetic tests for activity-to-date, time and place associations."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape
from zipfile import ZipFile
import unittest

from verify_activity_schedule import verify

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'form.hwpx'
        self.rows = [['Activity', 'Date', 'Time', 'Place'],
                     ['Meeting', '2027-05-03', '10:00-11:00', 'Room A'],
                     ['Practice', '2027-05-05', '15:00-17:00', 'Hall'],
                     ['Discussion', '2027-05-05', '17:00-18:00', 'Room A']]
        self.spec = {'section': 'Contents/section0.xml', 'table': 0,
                     'source': 'synthetic template and user request', 'headers': self.rows[0],
                     'activities': [{'cells': row, 'source': 'synthetic user request'} for row in self.rows[1:]]}

    def package(self, rows, merged=False):
        xml_rows = []
        for ri, row in enumerate(rows):
            cells = []
            for ci, value in enumerate(row):
                span = '2' if merged and ri == 1 and ci == 0 else '1'
                cells.append(f'<hp:tc><hp:cellAddr rowAddr="{ri}" colAddr="{ci}"/>'
                             f'<hp:cellSpan rowSpan="1" colSpan="{span}"/>'
                             f'<hp:subList><hp:p><hp:run><hp:t>{escape(value)}</hp:t></hp:run></hp:p></hp:subList></hp:tc>')
            xml_rows.append('<hp:tr>' + ''.join(cells) + '</hp:tr>')
        xml = f'<sec xmlns:hp="{HP}"><hp:p><hp:run><hp:tbl rowCnt="{len(rows)}" colCnt="4">' + ''.join(xml_rows) + '</hp:tbl></hp:run></hp:p></sec>'
        with ZipFile(self.path, 'w') as z:
            z.writestr('Contents/section0.xml', xml)

    def test_distinct_activities_and_exact_fields_pass(self):
        self.package(self.rows)
        self.assertEqual(verify(self.path, self.spec)['activities'], 3)

    def test_missing_activity_row_fails(self):
        self.package(self.rows[:-1])
        with self.assertRaisesRegex(ValueError, 'row count'):
            verify(self.path, self.spec)

    def test_swapped_times_fail_even_when_both_exist(self):
        rows = [r[:] for r in self.rows]
        rows[2][2], rows[3][2] = rows[3][2], rows[2][2]
        self.package(rows)
        with self.assertRaisesRegex(ValueError, 'cell mismatch'):
            verify(self.path, self.spec)

    def test_example_only_header_cannot_remain(self):
        rows = [r[:] for r in self.rows]
        rows[0][3] = 'Escort'
        self.package(rows)
        with self.assertRaisesRegex(ValueError, 'cell mismatch'):
            verify(self.path, self.spec)

    def test_merged_cells_are_not_silently_accepted(self):
        self.package(self.rows, merged=True)
        with self.assertRaisesRegex(ValueError, 'Merged'):
            verify(self.path, self.spec)

    def test_activity_without_evidence_is_rejected(self):
        self.package(self.rows)
        self.spec['activities'][0]['source'] = ''
        with self.assertRaisesRegex(ValueError, 'source'):
            verify(self.path, self.spec)

    def test_weekday_gate_cannot_be_skipped_by_a_table_only_pass(self):
        self.package(self.rows)
        with self.assertRaisesRegex(ValueError, 'weekday constraint'):
            verify(self.path, self.spec, require_weekday=True)

    def test_misspelled_constraint_is_not_silently_ignored(self):
        self.package(self.rows)
        self.spec['weekly_constraint'] = []
        with self.assertRaisesRegex(ValueError, 'Unknown inventory'):
            verify(self.path, self.spec)


class WeekdayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'narrative.hwpx'
        self.texts = ['Schedule', '2027-05-04', '5월 11일 (화)', '5.18.', '2027.05.25.(화)']
        self.tokens = ['2027-05-04', '5월 11일', '5.18.', '2027.05.25.']
        self.rule = {
            'weekday': 2, 'source': 'synthetic weekday instruction',
            'year': 2027, 'year_source': 'synthetic year authority',
            'scope_paragraphs': [1, 2, 3, 4],
            'sessions': [{'paragraph': i, 'date_text': token, 'source': 'synthetic session'}
                         for i, token in enumerate(self.tokens, 1)],
        }
        self.spec = {'section': 'Contents/section0.xml', 'source': 'synthetic plan',
                     'weekly_constraints': [self.rule]}

    def package(self, texts=None):
        paragraphs = []
        for value in texts if texts is not None else self.texts:
            split = len(value) // 2
            paragraphs.append('<hp:p><hp:run><hp:t>' + escape(value[:split]) +
                              '</hp:t></hp:run><hp:run><hp:t>' + escape(value[split:]) +
                              '</hp:t></hp:run></hp:p>')
        with ZipFile(self.path, 'w') as z:
            z.writestr('Contents/section0.xml', f'<sec xmlns:hp="{HP}">' + ''.join(paragraphs) + '</sec>')

    def test_sourced_tuesdays_in_split_narrative_pass(self):
        self.package()
        result = verify(self.path, self.spec, require_weekday=True)
        self.assertEqual((result['weekday_constraints_checked'], result['session_dates_checked']), (1, 4))

    def test_matching_inventory_of_wrong_weekdays_fails(self):
        texts = ['Schedule', '2027-05-05', '5월 12일', '5.19.', '2027.05.26.']
        self.package(texts)
        for session, token in zip(self.rule['sessions'], texts[1:]):
            session['date_text'] = token
        with self.assertRaisesRegex(ValueError, 'weekday conflicts'):
            verify(self.path, self.spec, require_weekday=True)

    def test_correct_date_with_wrong_printed_weekday_fails(self):
        texts = self.texts[:]
        texts[2] = '5월 11일 (수)'
        self.package(texts)
        with self.assertRaisesRegex(ValueError, 'Printed weekday'):
            verify(self.path, self.spec)

    def test_unlisted_date_in_selected_paragraph_fails(self):
        texts = self.texts[:]
        texts[1] += ', 5월 11일'
        self.package(texts)
        with self.assertRaisesRegex(ValueError, 'date coverage'):
            verify(self.path, self.spec)

    def test_selected_paragraph_without_session_fails(self):
        self.package()
        self.rule['sessions'].pop()
        with self.assertRaisesRegex(ValueError, 'date coverage'):
            verify(self.path, self.spec)

    def test_wrong_date_text_does_not_match_a_document_substring(self):
        self.package()
        self.rule['sessions'][0]['date_text'] = '05-04'
        with self.assertRaisesRegex(ValueError, 'date coverage'):
            verify(self.path, self.spec)

    def test_trailing_year_or_abbreviated_day_cannot_hide_in_scope(self):
        texts = self.texts[:]
        texts[1] = '05/04/2027'
        self.package(texts)
        self.rule['sessions'][0]['date_text'] = '05/04'
        with self.assertRaisesRegex(ValueError, 'date coverage'):
            verify(self.path, self.spec)
        texts[1] = '5월 4일, 12일'
        self.package(texts)
        self.rule['sessions'][0]['date_text'] = '5월 4일'
        with self.assertRaisesRegex(ValueError, 'Unsupported abbreviated date'):
            verify(self.path, self.spec)

    def test_command_line_weekday_gate_returns_failure_and_success(self):
        self.package()
        inventory = Path(self.tmp.name) / 'inventory.json'
        inventory.write_text(json.dumps(self.spec, ensure_ascii=False), encoding='utf-8')
        command = [sys.executable, '-B', str(Path(__file__).with_name('verify_activity_schedule.py')),
                   str(self.path), str(inventory), '--require-weekday']
        options = {'capture_output': True, 'text': True, 'encoding': 'utf-8'}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        passed = subprocess.run(command, **options)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(json.loads(passed.stdout)['session_dates_checked'], 4)
        self.rule['weekday'] = 3
        inventory.write_text(json.dumps(self.spec, ensure_ascii=False), encoding='utf-8')
        failed = subprocess.run(command, **options)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(json.loads(failed.stdout)['status'], 'VERIFICATION_FAILED')

    def test_missing_weekday_or_year_authority_fails(self):
        self.package()
        for key in ('source', 'year_source'):
            with self.subTest(key=key):
                value = self.rule[key]
                self.rule[key] = ''
                with self.assertRaisesRegex(ValueError, 'source'):
                    verify(self.path, self.spec)
                self.rule[key] = value

    def test_invalid_or_conflicting_year_and_date_fail(self):
        self.package()
        self.rule['year'] = 2028
        with self.assertRaisesRegex(ValueError, 'year mismatch'):
            verify(self.path, self.spec)
        self.rule['year'] = 2027
        texts = self.texts[:]
        texts[1] = '2027-02-30'
        self.package(texts)
        self.rule['sessions'][0]['date_text'] = texts[1]
        with self.assertRaisesRegex(ValueError, 'Invalid schedule date'):
            verify(self.path, self.spec)

    def test_nested_table_paragraph_is_not_counted_as_parent_text(self):
        xml = (f'<sec xmlns:hp="{HP}"><hp:p><hp:run><hp:tbl><hp:tr><hp:tc>'
               '<hp:subList><hp:p><hp:run><hp:t>5월 4일</hp:t></hp:run></hp:p>'
               '</hp:subList></hp:tc></hp:tr></hp:tbl></hp:run></hp:p></sec>')
        with ZipFile(self.path, 'w') as z:
            z.writestr('Contents/section0.xml', xml)
        self.rule['scope_paragraphs'] = [0]
        self.rule['sessions'] = [{'paragraph': 0, 'date_text': '5월 4일', 'source': 'synthetic session'}]
        with self.assertRaisesRegex(ValueError, 'date coverage'):
            verify(self.path, self.spec)
        self.rule['scope_paragraphs'] = [1]
        self.rule['sessions'][0]['paragraph'] = 1
        self.assertEqual(verify(self.path, self.spec)['session_dates_checked'], 1)


if __name__ == '__main__':
    unittest.main()
