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

    def test_non_count_percent_table_cannot_pass(self):
        self.tcells = {(3, 1): '만족도 00%'}
        self.save()
        self.check_fails('No count-and-percent fields')


if __name__ == '__main__':
    unittest.main()
