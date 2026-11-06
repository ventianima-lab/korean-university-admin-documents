"""Synthetic fixed-label coverage and merged-cell regression checks."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
import verify_input_coverage as gate

H = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


class TotalLabels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.output = self.root / 'source.hwpx', self.root / 'output.hwpx'
        self.make(self.source, [('계', 2), ('계', 2), ('합계', 1)])
        self.make(self.output, [('계', 2), ('계', 2), ('합계', 1)])
        self.inv = {'source': {'path': str(self.source), 'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(), 'section': 'Contents/section0.xml', 'table': 0}, 'output': {'section': 'Contents/section0.xml', 'table': 0}, 'mappings': [{'source': [i, 0], 'target': [i, 0]} for i in range(3)]}

    def make(self, path, rows):
        root = ET.Element(H + 'sec')
        tbl = ET.SubElement(root, H + 'tbl')
        for row, (text, span) in enumerate(rows):
            tr = ET.SubElement(tbl, H + 'tr')
            cell = ET.SubElement(tr, H + 'tc')
            ET.SubElement(cell, H + 'cellAddr', rowAddr=str(row), colAddr='0')
            ET.SubElement(cell, H + 'cellSpan', rowSpan='1', colSpan=str(span))
            ET.SubElement(cell, H + 't').text = text
        with ZipFile(path, 'w') as z:
            z.writestr('Contents/section0.xml', ET.tostring(root, encoding='utf-8'))

    def test_all_occurrences_and_cli(self):
        self.assertEqual(gate.verify_total_labels(self.output, self.inv)['total_cells'], 3)
        manifest = self.root / 'inventory.json'
        manifest.write_text(json.dumps(self.inv, ensure_ascii=False), encoding='utf-8')
        cmd = [sys.executable, gate.__file__, str(self.output), str(manifest), '--total-labels']
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
        self.make(self.output, [('', 2), ('계', 2), ('합계', 1)])
        self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_omitted_mapping_or_duplicate_target_fails(self):
        for failure in ('omitted', 'duplicate'):
            inv = copy.deepcopy(self.inv)
            if failure == 'omitted':
                inv['mappings'].pop(0)
            else:
                inv['mappings'][0]['target'] = [1, 0]
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                gate.verify_total_labels(self.output, inv)

    def test_missing_row_or_altered_merge_fails(self):
        for rows in [[('계', 2), ('합계', 1)], [('3차', 2), ('계', 2), ('합계', 1)], [('계', 1), ('계', 2), ('합계', 1)]]:
            self.make(self.output, rows)
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                gate.verify_total_labels(self.output, self.inv)

    def test_added_detail_row_allows_independently_mapped_total(self):
        self.make(self.output, [('3차', 2), ('계', 2), ('계', 2), ('합계', 1)])
        for item in self.inv['mappings']:
            item['target'][0] += 1
        self.assertEqual(gate.verify_total_labels(self.output, self.inv)['status'], 'PASS')

    def test_hash_and_cross_table_scope(self):
        inv = copy.deepcopy(self.inv)
        inv['source']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            gate.verify_total_labels(self.output, inv)
        inv = copy.deepcopy(self.inv)
        inv['output']['table'] = 1
        with self.assertRaises(ValueError):
            gate.verify_total_labels(self.output, inv)


if __name__ == '__main__':
    unittest.main()
