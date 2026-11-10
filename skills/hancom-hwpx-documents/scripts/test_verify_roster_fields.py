import copy
import hashlib
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from verify_roster_fields import HP, check_roster_fields, check_person_record_order


def source(text):
    return {"kind": "verified_reference", "reference": "synthetic independent source",
            "location": "field", "quote": text}


def value(field, text, authorization=None):
    result = {"kind": "value", "field": field, "text": text, "source": source(text)}
    if authorization:
        result["authorization"] = authorization
    return result


def literal(text):
    return {"kind": "literal", "text": text, "source": source('x' + text)}


class PersonRecordOrderTest(unittest.TestCase):
    def test_whole_record_sort_and_population_separation(self):
        original = [dict(person_id='S1', role='student', name='Person A', contact='contact A'),
                    dict(person_id='I1', role='instructor', name='Person B', contact='contact B'),
                    dict(person_id='H1', role='head', name='Person C', contact='contact C'),
                    dict(person_id='A1', role='assistant', name='Person D', contact='contact D')]
        order = ['head', 'instructor', 'assistant', 'student']
        good = [original[i].copy() for i in (2,1,3,0)]
        self.assertEqual(check_person_record_order(original,good,order,'person_id')['status'],'PASS')
        wrong=copy.deepcopy(good);wrong[0]['contact'],wrong[1]['contact']=wrong[1]['contact'],wrong[0]['contact']
        with self.assertRaises(ValueError):check_person_record_order(original,wrong,order,'person_id')
        wrong=copy.deepcopy(good);wrong[0]['person_id'],wrong[1]['person_id']=wrong[1]['person_id'],wrong[0]['person_id']
        with self.assertRaises(ValueError):check_person_record_order(original,wrong,order,'person_id')
        with self.assertRaises(ValueError):check_person_record_order(original,good[1:],order,'person_id')
        insurance=[x for x in original if x['role']!='head']
        self.assertEqual(check_person_record_order(insurance,good[1:],order,'person_id')['records'],3)
        reverse=list(reversed(order));rev=sorted(original,key=lambda x:reverse.index(x['role']))
        self.assertEqual(check_person_record_order(original,rev,reverse,'person_id')['status'],'PASS')


class RosterFieldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'master.hwpx'
        self.target = self.root / 'roster.hwpx'
        self.write_roster(self.source, 'A001')
        self.write_roster(self.target, 'A001')
        self.roster = {
            'path': str(self.target), 'section': 'Contents/section0.xml', 'table': 0,
            'template_source': str(self.source),
            'headers': [{'col': 0, 'text': '연번', 'span': 1},
                        {'col': 1, 'text': '학번 또는 직급(위)', 'span': 1}],
            'grid': {'first_row': 1, 'last_row': 1,
                     'columns': [{'col': 0, 'span': 1}, {'col': 1, 'span': 1}]},
            'source_header': {'section': 'Contents/section0.xml', 'table': 0, 'row': 0,
                              'columns': [{'col': 0, 'source_col': 0, 'text': '연번'},
                                          {'col': 1, 'source_col': 1, 'text': '학번 또는 직급(위)'}]},
            'expected_cells': [{'row': 1, 'col': 0, 'parts': [value('연번', '1')]},
                               {'row': 1, 'col': 1, 'parts': [value('학번', 'A001')]}],
        }

    def write_roster(self, path, data, heading='학번 또는 직급(위)'):
        root = ET.Element(HP + 'sec')
        table = ET.SubElement(root, HP + 'tbl')
        for r, values in enumerate((('연번', heading), ('1', data))):
            row = ET.SubElement(table, HP + 'tr')
            for c, text in enumerate(values):
                cell = ET.SubElement(row, HP + 'tc')
                ET.SubElement(cell, HP + 'cellAddr', rowAddr=str(r), colAddr=str(c))
                ET.SubElement(cell, HP + 't').text = text
        with ZipFile(path, 'w') as package:
            package.writestr('Contents/section0.xml', ET.tostring(root, encoding='utf-8'))

    def problems(self):
        return {item['problem'] for item in check_roster_fields(self.roster)}

    def test_explicit_grade_request_is_respected(self):
        self.write_roster(self.target, 'A001 (2학년)')
        auth = {'kind': 'explicit_user_instruction', 'quote': '학년도 함께 표시해 주세요',
                'reference': 'synthetic user instruction'}
        self.roster['expected_cells'][1]['parts'] = [value('학번', 'A001'), literal(' ('),
                                                      value('학년', '2학년', auth), literal(')')]
        self.assertEqual(self.problems(), set())
        self.roster['expected_cells'][1]['parts'][2].pop('authorization')
        self.assertIn('planned_roster_unrequested_field', self.problems())

    def test_other_unrequested_field_is_not_added_to_an_id_cell(self):
        self.write_roster(self.target, 'A001 (야간)')
        self.roster['expected_cells'][1]['parts'] = [value('학번', 'A001'), literal(' ('),
                                                      value('과정', '야간'), literal(')')]
        self.assertIn('planned_roster_unrequested_field', self.problems())

    def test_exact_user_edited_snapshot_protects_existing_content(self):
        self.write_roster(self.target, 'A001 (2학년)')
        snapshot = self.root / 'user-baseline.hwpx'
        snapshot.write_bytes(self.target.read_bytes())
        item = self.roster['expected_cells'][1]
        item['parts'] = [{'kind': 'value', 'field': '학번', 'text': 'A001 (2학년)',
                          'source': {'kind': 'user_edited_snapshot'}}]
        item['user_snapshot'] = {'kind': 'user_edited_snapshot', 'path': str(snapshot),
                                 'sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                                 'reference': 'synthetic user-edited baseline',
                                 'section': 'Contents/section0.xml', 'table': 0, 'row': 1, 'col': 1}
        self.assertEqual(self.problems(), set())
        item['user_snapshot']['sha256'] = '0' * 64
        self.assertIn('planned_roster_user_snapshot_unverifiable', self.problems())
        self.assertIn('planned_roster_unrequested_field', self.problems())

    def test_blank_cells_do_not_accept_unsolicited_placeholders(self):
        self.write_roster(self.target, '')
        item = self.roster['expected_cells'][1]
        item['parts'] = []
        self.assertEqual(self.problems(), set())
        self.write_roster(self.target, '-')
        self.assertIn('planned_roster_cell_value_mismatch', self.problems())
        item['parts'] = [literal('-')]
        self.assertIn('planned_roster_literal_without_value', self.problems())
        item['literal_authorization'] = {'kind': 'explicit_user_instruction',
                                         'quote': '빈칸에 - 표시', 'reference': 'synthetic instruction'}
        self.assertEqual(self.problems(), set())

    def test_source_header_and_each_cell_are_independently_checked(self):
        self.assertEqual(self.problems(), set())
        altered = copy.deepcopy(self.roster['source_header']['columns'][1])
        altered['source_col'], altered['text'] = 0, '연번'
        self.roster['source_header']['columns'][1] = altered
        self.assertIn('planned_roster_target_header_not_authorized', self.problems())
        self.roster['source_header']['columns'][1] = {'col': 1, 'source_col': 1,
                                                       'text': '학번 또는 직급(위)'}
        self.roster['expected_cells'].pop()
        self.assertIn('planned_roster_cell_inventory_coverage', self.problems())

    def test_grade_in_the_actual_source_header_needs_no_exception(self):
        self.write_roster(self.source, '2학년', '학년')
        self.write_roster(self.target, '2학년', '학년')
        self.roster['headers'][1]['text'] = '학년'
        self.roster['source_header']['columns'][1]['text'] = '학년'
        self.roster['expected_cells'][1]['parts'] = [value('학년', '2학년')]
        self.assertEqual(self.problems(), set())


if __name__ == '__main__':
    unittest.main()
