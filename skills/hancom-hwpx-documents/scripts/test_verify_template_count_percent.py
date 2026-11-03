#!/usr/bin/env python3
"""Behavior tests with synthetic HWPX tables; no real records."""
from __future__ import annotations

import copy
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from verify_template_count_percent import HP, verify


def write_hwpx(path, cells):
    section = ET.Element('section')
    table = ET.SubElement(section, HP + 'tbl')
    rows = {}
    for (row, col), text in cells.items():
        if row not in rows:
            rows[row] = ET.SubElement(table, HP + 'tr')
        cell = ET.SubElement(rows[row], HP + 'tc')
        ET.SubElement(cell, HP + 'cellAddr', {'rowAddr': str(row), 'colAddr': str(col)})
        ET.SubElement(cell, HP + 't').text = text
    with ZipFile(path, 'w') as z:
        z.writestr('Contents/section0.xml', ET.tostring(section))


class TemplateCountPercentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.template = Path(self.tmp.name) / 'template.hwpx'
        self.output = Path(self.tmp.name) / 'output.hwpx'
        self.tcells = {(3, 1): '00명(00%)', (3, 2): '00명(00%)', (3, 3): '00명(00%)'}
        self.ocells = {(8, 4): '2명(66.7%)', (8, 5): '1명(33.3%)', (8, 6): '0명(0%)'}
        self.manifest = {
            'template': {'section': 'Contents/section0.xml', 'table': 0},
            'output': {'section': 'Contents/section0.xml', 'table': 0},
            'rounding_decimals': 1,
            'fields': [
                {'template': [3, 1], 'output': [8, 4], 'count': 2, 'denominator': 3, 'source': 'survey A'},
                {'template': [3, 2], 'output': [8, 5], 'count': 1, 'denominator': 3, 'source': 'survey A'},
                {'template': [3, 3], 'output': [8, 6], 'count': 0, 'denominator': 3, 'source': 'survey A'},
            ],
            'groups': [{'name': 'question', 'output_cells': [[8, 4], [8, 5], [8, 6]], 'denominator': 3}],
        }
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        write_hwpx(self.template, self.tcells)
        write_hwpx(self.output, self.ocells)

    def check_fails(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            verify(self.template, self.output, self.manifest)

    def test_correct_units_counts_rounding_and_group(self):
        result = verify(self.template, self.output, self.manifest)
        self.assertEqual((result['status'], result['template_fields'], result['groups']), ('PASS', 3, 1))

    def test_numbers_only_cannot_pass(self):
        self.ocells[(8, 4)] = '2'
        self.save()
        self.check_fails('Missing count unit or percentage')

    def test_count_and_percentage_must_both_match(self):
        for value in ('2명(66.6%)', '1명(66.7%)'):
            self.ocells[(8, 4)] = value
            self.save()
            self.check_fails('mismatch')

    def test_every_template_cell_must_have_independent_mapping(self):
        self.manifest['fields'].pop()
        self.check_fails('not covered')

    def test_missing_source_cannot_pass(self):
        self.manifest['fields'][1]['source'] = ''
        self.check_fails('evidence is missing')

    def test_group_sum_must_match_denominator(self):
        self.manifest['fields'][0]['count'] = 1
        self.ocells[(8, 4)] = '1명(33.3%)'
        self.save()
        self.check_fails('Count total does not reconcile')

    def test_unrecognized_template_shape_is_not_ignored(self):
        self.tcells[(3, 3)] = '합계 00명(00%)'
        self.save()
        self.check_fails('Unsupported template field shape')

    def configure_balanced_case(self, counts, values):
        self.manifest['rounding_decimals'] = 0
        self.manifest['groups'][0]['rounding'] = 'largest_remainder'
        for entry, count, value in zip(self.manifest['fields'], counts, values):
            entry['count'] = count
            entry['denominator'] = 15
            self.ocells[tuple(entry['output'])] = value
        self.manifest['groups'][0]['denominator'] = 15
        self.save()

    def test_balanced_tied_remainders_can_total_100(self):
        self.configure_balanced_case([13, 1, 1], ['13명(87%)', '1명(7%)', '1명(6%)'])
        self.assertEqual(verify(self.template, self.output, self.manifest)['status'], 'PASS')
        self.ocells[(8, 5)], self.ocells[(8, 6)] = '1명(6%)', '1명(7%)'
        self.save()
        self.assertEqual(verify(self.template, self.output, self.manifest)['status'], 'PASS')

    def test_balanced_percentages_must_total_100(self):
        self.configure_balanced_case([12, 2, 1], ['12명(80%)', '2명(13%)', '1명(6%)'])
        self.check_fails('Balanced percentages do not reconcile')

    def test_balanced_allocation_must_respect_remainders(self):
        self.configure_balanced_case([11, 3, 1], ['11명(74%)', '3명(20%)', '1명(6%)'])
        self.check_fails('remainder allocation is invalid')

    def test_balanced_group_cannot_overlap_an_individual_group(self):
        self.configure_balanced_case([13, 1, 1], ['13명(87%)', '1명(7%)', '1명(6%)'])
        self.manifest['groups'].append({'name': 'overlap', 'output_cells': [[8, 6]], 'denominator': 15})
        self.check_fails('cannot overlap')

    def test_balanced_mode_must_be_explicit(self):
        self.configure_balanced_case([13, 1, 1], ['13명(87%)', '1명(7%)', '1명(6%)'])
        del self.manifest['groups'][0]['rounding']
        self.check_fails('mismatch')

    def test_non_count_percent_table_cannot_pass(self):
        self.tcells = {(3, 1): '만족도 00%'}
        self.save()
        self.check_fails('No count-and-percent fields')


if __name__ == '__main__':
    unittest.main()
