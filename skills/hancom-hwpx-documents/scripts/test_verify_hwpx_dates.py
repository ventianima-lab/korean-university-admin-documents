#!/usr/bin/env python3
"""Synthetic date-preservation regression tests; no real records are used."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

import verify_hwpx_dates as dates
import verify_hwpx_followup as followup

PART = 'Contents/section0.xml'
HP = dates.HP[1:-1]


class DateChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.before = Path(self.temp.name)/'before.hwpx'
        self.after = Path(self.temp.name)/'after.hwpx'

    def package(self, path, cells, amount='100', tail=''):
        rows = []
        for row, text in enumerate(cells):
            rows.append('<hp:tr><hp:tc><hp:cellAddr rowAddr="'+str(row)+'" colAddr="0"/>'
                        '<hp:subList><hp:p><hp:run><hp:t>'+escape(text)+
                        '</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr>')
        xml = ('<sec xmlns:hp="'+HP+'"><hp:p><hp:run><hp:t>unchanged title</hp:t>'
               '</hp:run></hp:p><hp:p><hp:run><hp:tbl>'+''.join(rows)+
               '</hp:tbl><hp:t>budget '+amount+'</hp:t></hp:run></hp:p>'+tail+'</sec>')
        with ZipFile(path, 'w') as z:
            z.writestr(PART, xml)
            z.writestr('Contents/header.xml', '<header/>')

    def mapping(self, row, old_tokens, new_tokens, **override):
        location = f'table=0/row={row}/col=0/p=0'
        change = {'section': PART, 'before': location, 'after': location,
                  'old': old_tokens, 'new': new_tokens,
                  'source': 'User explicitly requested this synthetic event date change'}
        change.update(override)
        return {'changes': [change]}

    def test_budget_change_preserves_filled_signer_date(self):
        self.package(self.before, ['2027. 5. 12.', '27. 5. 1.'], amount='100')
        self.package(self.after, ['2027. 5. 12.', '27. 5. 1.'], amount='200')
        result = followup.verify(self.before, self.after, {PART: {1}}, {PART: {1}})
        self.assertEqual(result['dates']['protected_date_fields'], 2)

    def test_cleared_date_inside_excluded_budget_block_is_rejected(self):
        self.package(self.before, ['2027. 5. 12.'], amount='100')
        self.package(self.after, [''], amount='200')
        with self.assertRaisesRegex(ValueError, 'Unrequested date'):
            followup.verify(self.before, self.after, {PART: {1}}, {PART: {1}})

    def test_authorized_event_change_preserves_independent_signature(self):
        self.package(self.before, ['2027. 5. 12.', '2027년 5월 1일'])
        self.package(self.after, ['2027. 5. 19.', '2027년 5월 1일'])
        change = self.mapping(0, ['2027. 5. 12.'], ['2027. 5. 19.'])
        result = followup.verify(self.before, self.after, {PART: {1}}, {PART: {1}}, change)
        self.assertEqual(result['dates']['explicit_date_changes'], 1)
        self.package(self.after, ['2027. 5. 19.', ''])
        with self.assertRaisesRegex(ValueError, 'Unrequested date'):
            dates.verify(self.before, self.after, change)

    def test_deletion_replacement_placeholder_and_inferred_insertion_fail(self):
        for old, new in [('2027. 5. 12.', ''), ('2027. 5. 12.', '2027. 5. 19.'),
                         ('2027. 5. 12.', '2027.  .  .'), ('', '2027. 5. 12.'),
                         ('2027.', ''), ('20270512', ''), ('5월 12일', '')]:
            with self.subTest(old=old, new=new):
                self.package(self.before, [old])
                self.package(self.after, [new])
                with self.assertRaises(ValueError): dates.verify(self.before, self.after)

    def test_duplicate_count_and_field_association_are_protected(self):
        for before, after in [(['2027-05-12', '2027-05-12'], ['2027-05-12', '']),
                              (['2027/05/12', ''], ['', '2027/05/12'])]:
            self.package(self.before, before)
            self.package(self.after, after)
            with self.assertRaises(ValueError): dates.verify(self.before, self.after)

    def test_split_runs_and_linebreak_tails_are_checked(self):
        old = ('<hp:p><hp:run><hp:t>2027.</hp:t></hp:run><hp:run>'
               '<hp:t> 5. 12.</hp:t></hp:run></hp:p><hp:p><hp:run>'
               '<hp:t>signing<hp:lineBreak/>2027년 5월 1일</hp:t></hp:run></hp:p>')
        self.package(self.before, [], tail=old)
        self.package(self.after, [], tail=old)
        self.assertEqual(dates.verify(self.before, self.after)['protected_date_fields'], 2)
        for lost in [' 5. 12.', '2027년 5월 1일']:
            self.package(self.after, [], tail=old.replace(lost, ''))
            with self.assertRaises(ValueError): dates.verify(self.before, self.after)

    def test_only_exact_sourced_authorizations_pass(self):
        self.package(self.before, ['2027. 5. 12.'])
        self.package(self.after, ['2027. 5. 19.'])
        for override in [{'source': ''}, {'old': ['2027. 5. 11.']},
                         {'section': 'Contents/section9.xml'}]:
            with self.subTest(override=override), self.assertRaises(ValueError):
                dates.verify(self.before, self.after,
                             self.mapping(0, ['2027. 5. 12.'], ['2027. 5. 19.'], **override))
        duplicate = self.mapping(0, ['2027. 5. 12.'], ['2027. 5. 19.'])
        duplicate['changes'].append(self.mapping(0, [], [])['changes'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate date authorization'):
            dates.verify(self.before, self.after, duplicate)

    def test_explicit_clear_requires_exact_field_authorization(self):
        self.package(self.before, ['2027. 5. 12.', '2027. 5. 1.'])
        self.package(self.after, ['', '2027. 5. 1.'])
        change = self.mapping(0, ['2027. 5. 12.'], [])
        self.assertEqual(dates.verify(self.before, self.after, change)['explicit_date_changes'], 1)

    def test_cli_failure_is_readonly_and_does_not_log_date_values(self):
        self.package(self.before, ['2027. 5. 12.'])
        self.package(self.after, [''])
        paths = [self.before, self.after]
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        result = subprocess.run([sys.executable, str(Path(dates.__file__)), *map(str, paths)],
                                capture_output=True, text=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['status'], 'VERIFICATION_FAILED')
        self.assertNotIn('2027. 5. 12.', result.stdout)
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])


if __name__ == '__main__':
    unittest.main()
