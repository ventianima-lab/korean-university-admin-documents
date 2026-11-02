import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


script = Path(__file__).with_name('verify_required_packet.py')
spec = importlib.util.spec_from_file_location('packet_role_test', script)
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)


def proof(quote, kind='user_instruction'):
    return {'kind': kind, 'reference': 'independent synthetic source',
            'location': 'specified statement', 'quote': quote}


def policy(quote):
    return {'reference': 'synthetic current rule', 'location': 'relevant condition', 'quote': quote}


class RoleExpenseCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.letter = Path(self.temp.name) / 'letter.hwpx'
        self.write_letter('운영 지원 3명')
        fee_conditions = [
            {'kind': 'instructor_fee', 'effect': 'required_if_paid', 'policy': policy('instructor fee row')},
            {'kind': 'consulting_fee', 'effect': 'required_if_paid', 'policy': policy('consulting fee row')},
        ]
        documents = []
        for kind in ('resume', 'background_check'):
            documents.append({'kind': kind, 'status': 'not_applicable',
                              'fee_conditions': copy.deepcopy(fee_conditions),
                              'role_conditions': [{'kind': 'special_lecture', 'matched': 'unknown',
                                                   'policy': policy('special lecture condition')}]})
        self.review = {
            'stage': 'planned',
            'payments': [
                {'group': 'group-a', 'kind': 'instructor_fee', 'category': 'instructor fee',
                 'amount': 0, 'evidence': proof('강사료는 편성하지 않음')},
                {'group': 'group-a', 'kind': 'consulting_fee', 'category': 'consulting fee',
                 'amount': 0, 'evidence': proof('자문료는 편성하지 않음')},
                {'kind': 'other', 'category': 'meeting food', 'amount': 10000,
                 'evidence': proof('회의 식비를 편성함')},
                {'kind': 'other', 'category': 'refreshments', 'amount': 5000,
                 'evidence': proof('다과비를 편성함')},
            ],
            'groups': [{'id': 'group-a',
                        'actual_role': {'kind': 'support', 'evidence': proof('측정 운영을 지원한다')},
                        'letter_labels': [{'path': str(self.letter), 'section': 'Contents/section0.xml',
                                           'paragraph': 0, 'label': '운영 지원 3명'}],
                        'documents': documents}],
        }
        self.manifest = {
            'requirements': [{'id': 'food', 'source': 'synthetic manual'}],
            'artifacts': [{'id': 'food', 'status': 'ready', 'paths': [str(Path(__file__))],
                           'verification': 'reviewed synthetic evidence'}],
            'expense_reviews': [
                {'category': category, 'source': 'synthetic policy',
                 'items': [{'label': 'food evidence', 'status': 'required', 'requirement_id': 'food'}]}
                for category in ('meeting food', 'refreshments')],
            'role_expense_review': self.review,
        }

    def write_letter(self, text):
        xml = ("<hs:sec xmlns:hs='urn:test' xmlns:hp='http://www.hancom.co.kr/hwpml/2011/paragraph'>"
               f'<hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p></hs:sec>')
        with ZipFile(self.letter, 'w') as z:
            z.writestr('Contents/section0.xml', xml)

    def problems(self, manifest=None):
        result = packet.audit(manifest or self.manifest, role_expense_check=True)
        return result['status'], {item['problem'] for item in result['role_expense_issues']}

    def resolve_no_lecture(self):
        for document in self.review['groups'][0]['documents']:
            condition = document['role_conditions'][0]
            condition['matched'] = 'no'
            condition['evidence'] = proof('특강은 진행하지 않고 측정만 지원한다', 'office_confirmation')

    def test_zero_fees_do_not_resolve_role_condition(self):
        status, problems = self.problems()
        self.assertEqual(status, 'INCOMPLETE')
        self.assertIn('personnel_role_condition_pending', problems)

    def test_zero_fee_alone_is_not_role_based_exemption_evidence(self):
        self.resolve_no_lecture()
        for document in self.review['groups'][0]['documents']:
            document['role_conditions'][0]['evidence'] = proof('강사료 0원')
        self.assertIn('personnel_role_condition_evidence_inconclusive', self.problems()[1])

    def test_fee_negation_does_not_negate_an_ongoing_special_lecture(self):
        self.resolve_no_lecture()
        for document in self.review['groups'][0]['documents']:
            document['role_conditions'][0]['evidence'] = proof('특강을 진행하며 강사료는 없음')
        self.assertIn('personnel_role_condition_evidence_inconclusive', self.problems()[1])

    def test_explicit_no_lecture_cannot_be_recorded_as_yes(self):
        self.resolve_no_lecture()
        for document in self.review['groups'][0]['documents']:
            document['status'] = 'required'
            document['role_conditions'][0]['matched'] = 'yes'
        self.assertIn('personnel_role_condition_evidence_conflicts', self.problems()[1])

    def test_external_headcount_alone_cannot_establish_instructor_obligations(self):
        group = self.review['groups'][0]
        group['actual_role']['evidence'] = proof('외부인사 3명')
        for document in group['documents']:
            document['status'] = 'required'
            condition = document['role_conditions'][0]
            condition['matched'] = 'yes'
            condition['evidence'] = proof('외부인사 3명')
        _, problems = self.problems()
        self.assertIn('actual_role_evidence_inconclusive', problems)
        self.assertIn('personnel_role_condition_evidence_inconclusive', problems)
        self.assertIn('personnel_requirement_unsupported', problems)

    def test_assistant_instructor_evidence_cannot_be_downgraded_to_generic_support(self):
        self.resolve_no_lecture()
        group = self.review['groups'][0]
        group['actual_role']['evidence'] = proof('보조강사로 측정 운영을 지원한다')
        self.assertIn('actual_role_evidence_conflicts', self.problems()[1])

    def test_saved_instructor_label_conflicts_with_supported_helper_role(self):
        self.resolve_no_lecture()
        self.write_letter('외부 강사 3명')
        self.review['groups'][0]['letter_labels'][0]['label'] = '외부 강사 3명'
        self.assertIn('letter_role_conflicts_with_evidence', self.problems()[1])

    def test_partial_neutral_label_cannot_hide_an_instructor_label(self):
        self.resolve_no_lecture()
        self.write_letter('외부인사 강사 3명')
        self.review['groups'][0]['letter_labels'][0]['label'] = '외부인사'
        self.assertIn('letter_role_label_changed', self.problems()[1])

    def test_explicitly_excluded_lecture_is_not_a_saved_instructor_role(self):
        self.resolve_no_lecture()
        self.write_letter('특강 없이 측정 지원 3명')
        self.review['groups'][0]['letter_labels'][0]['label'] = '특강 없이 측정 지원 3명'
        self.assertEqual(self.problems(), ('PASS', set()))

    def test_saved_label_must_really_exist_and_be_independently_sourced(self):
        self.resolve_no_lecture()
        self.write_letter('담당자 3명')
        self.assertIn('letter_role_label_changed', self.problems()[1])
        self.write_letter('운영 지원 3명')
        role = self.review['groups'][0]['actual_role']
        role['evidence'] = {'kind': 'prior_record', 'reference': str(self.letter),
                            'location': 'same letter', 'quote': '운영 지원'}
        self.assertIn('letter_used_as_its_own_role_evidence', self.problems()[1])

    def test_explicit_independent_role_decision_allows_supported_exclusion(self):
        self.resolve_no_lecture()
        self.assertEqual(self.problems(), ('PASS', set()))

    def test_unpaid_special_lecture_still_triggers_role_documents(self):
        group = self.review['groups'][0]
        self.write_letter('외부 강사 3명')
        group['letter_labels'][0]['label'] = '외부 강사 3명'
        group['actual_role'] = {'kind': 'instructor', 'evidence': proof('외부 강사가 특강을 진행한다')}
        for document in group['documents']:
            condition = document['role_conditions'][0]
            condition['matched'] = 'yes'
            condition['evidence'] = proof('강사료 없이 특강을 진행한다')
        self.assertIn('personnel_exclusion_conflicts_with_trigger', self.problems()[1])
        for document in group['documents']:
            doc = document['kind']
            document['status'] = 'required'
            document['requirement_id'] = doc
            self.manifest['requirements'].append({'id': doc, 'source': 'synthetic role policy'})
            self.manifest['artifacts'].append({'id': doc, 'status': 'ready', 'paths': [str(Path(__file__))],
                                               'verification': 'synthetic role document'})
        self.assertEqual(self.problems(), ('PASS', set()))

    def test_paid_category_and_fee_trigger_must_be_reviewed(self):
        self.resolve_no_lecture()
        self.review['payments'][0]['amount'] = 25000
        _, problems = self.problems()
        self.assertIn('paid_category_not_reviewed', problems)
        self.assertIn('personnel_exclusion_conflicts_with_trigger', problems)
        self.review['groups'][0]['documents'][0]['fee_conditions'].pop()
        self.assertIn('personnel_fee_condition_coverage_incomplete', self.problems()[1])

    def test_paid_fee_can_require_documents_even_without_a_special_lecture(self):
        self.resolve_no_lecture()
        self.review['payments'][0]['amount'] = 25000
        self.manifest['expense_reviews'].append(
            {'category': 'instructor fee', 'source': 'synthetic fee rule',
             'items': [{'label': 'fee evidence', 'status': 'required', 'requirement_id': 'food'}]})
        for document in self.review['groups'][0]['documents']:
            doc = document['kind']
            document['status'] = 'required'
            document['requirement_id'] = doc
            self.manifest['requirements'].append({'id': doc, 'source': 'synthetic fee policy'})
            self.manifest['artifacts'].append({'id': doc, 'status': 'ready', 'paths': [str(Path(__file__))],
                                               'verification': 'synthetic fee document'})
        self.assertEqual(self.problems(), ('PASS', set()))

    def test_required_fee_and_role_reviews_cannot_be_omitted(self):
        self.resolve_no_lecture()
        self.review['payments'] = [p for p in self.review['payments'] if p['kind'] != 'consulting_fee']
        self.review['groups'][0]['documents'][0]['role_conditions'] = []
        _, problems = self.problems()
        self.assertIn('fee_amount_unverified', problems)
        self.assertIn('personnel_role_conditions_missing', problems)

    def test_optional_user_requested_document_does_not_become_institutional_requirement(self):
        self.resolve_no_lecture()
        doc = self.review['groups'][0]['documents'][0]
        doc['requirement_id'] = 'optional-resume'
        self.manifest['requirements'].append({'id': 'optional-resume', 'source': 'user requested'})
        self.manifest['artifacts'].append({'id': 'optional-resume', 'status': 'ready',
                                           'paths': [str(Path(__file__))], 'verification': 'requested'})
        self.assertIn('personnel_document_in_packet_without_basis', self.problems()[1])
        doc['user_request'] = proof('이력서도 준비해 주세요')
        self.assertEqual(self.problems(), ('PASS', set()))

    def test_table_cell_role_is_checked_from_the_saved_letter(self):
        self.resolve_no_lecture()
        xml = ("<hs:sec xmlns:hs='urn:test' xmlns:hp='http://www.hancom.co.kr/hwpml/2011/paragraph'>"
               "<hp:tbl><hp:tr><hp:tc><hp:p><hp:run><hp:t>외부 강사</hp:t></hp:run></hp:p></hp:tc>"
               "</hp:tr></hp:tbl></hs:sec>")
        with ZipFile(self.letter, 'w') as z:
            z.writestr('Contents/section0.xml', xml)
        self.review['groups'][0]['letter_labels'][0] = {
            'path': str(self.letter), 'section': 'Contents/section0.xml', 'table': 0,
            'row': 0, 'cell': 0, 'label': '외부 강사'}
        self.assertIn('letter_role_conflicts_with_evidence', self.problems()[1])

    def test_option_fails_closed_and_review_auto_enables(self):
        incomplete = copy.deepcopy(self.manifest)
        del incomplete['role_expense_review']
        self.assertEqual(packet.audit(incomplete)['status'], 'PASS')
        self.assertIn('role_expense_review_missing', self.problems(incomplete)[1])
        self.assertEqual(packet.audit(self.manifest)['status'], 'INCOMPLETE')
        target = Path(self.temp.name) / 'inventory.json'
        target.write_text(json.dumps(incomplete), encoding='utf-8')
        result = subprocess.run([sys.executable, str(script), str(target), '--role-expense-check'],
                                capture_output=True, text=True, encoding='utf-8',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('role_expense_review_missing', result.stdout)


if __name__ == '__main__':
    unittest.main()
