"""Synthetic tests for activity-to-date, time and place associations."""
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
