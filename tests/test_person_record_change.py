"""Synthetic provided-value invocations; no real documents or personal records."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = (Path(__file__).resolve().parents[1] / 'skills' /
          'hancom-hwpx-documents/scripts/verify_roster_fields.py')
spec = importlib.util.spec_from_file_location('roster_fields', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PersonRecordChangeTests(unittest.TestCase):
    def setUp(self):
        self.source = [
            {'key': 'p-a', 'name': 'LABEL-A', 'role': 'staff',
             'identifier': 'TOKEN-A', 'age': 'AGE-A', 'sex': 'SEX-A', 'premium': 70},
            {'key': 'p-b', 'name': 'LABEL-B', 'role': 'learner',
             'identifier': 'TOKEN-B', 'age': 'AGE-B', 'sex': 'SEX-B', 'premium': 130},
        ]
        # Source/user inventory, independently specified before candidate values.
        self.dependencies = {'headcount': 1, 'header.count': 1,
                             'summary.keys': ['p-b'], 'row.numbers': [1],
                             'filename': 'roster_1-person', 'extract.keys': ['p-b'],
                             'premium_total': 130}

    def check(self, rows, dependencies=None, **kwargs):
        return module.check_person_record_change(
            self.source, rows, operation=kwargs.pop('operation', 'exclude_person'),
            key_field='key', target_keys=['p-a'],
            expected_dependencies=self.dependencies,
            output_dependencies=self.dependencies if dependencies is None else dependencies,
            **kwargs)

    def test_name_only_removal_fails(self):
        rows = [dict(self.source[0], name=''), self.source[1]]
        with self.assertRaises(ValueError):
            self.check(rows, dict(self.dependencies, headcount=2))

    def test_whole_record_and_all_dependencies_pass(self):
        self.assertEqual(self.check([self.source[1]])['status'], 'PASS')

    def test_each_stale_current_dependency_fails(self):
        stale = {'headcount': 2, 'header.count': 2, 'summary.keys': ['p-a', 'p-b'],
                 'row.numbers': [2], 'filename': 'roster_2-person',
                 'extract.keys': ['p-a', 'p-b'], 'premium_total': 200}
        for key, value in stale.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check([self.source[1]], dict(self.dependencies, **{key: value}))

    def test_missing_dependency_fails(self):
        values = dict(self.dependencies)
        del values['extract.keys']
        with self.assertRaises(ValueError):
            self.check([self.source[1]], values)

    def test_other_person_field_change_fails(self):
        with self.assertRaises(ValueError):
            self.check([dict(self.source[1], identifier='WRONG-TOKEN')])

    def test_spelling_correction_retains_membership(self):
        self.dependencies = {'headcount': 2, 'filename': 'roster_2-person',
                             'summary.names': ['LABEL-A2', 'LABEL-B'], 'premium_total': 200}
        rows = [dict(self.source[0], name='LABEL-A2'), self.source[1]]
        self.assertEqual(self.check(rows, operation='correct_name',
                                    name_edits={'p-a': 'LABEL-A2'})['records'], 2)
        with self.assertRaises(ValueError):
            self.check([self.source[1]], operation='correct_name',
                       name_edits={'p-a': 'LABEL-A2'})

    def test_unknown_premium_stays_issuer_dependency(self):
        self.source[1]['premium'] = None
        self.dependencies['premium_total'] = None
        result = self.check([self.source[1]])
        self.assertEqual(result['premium_status'], 'issuer_dependency')
        self.dependencies['premium_total'] = 100
        with self.assertRaises(ValueError):
            self.check([self.source[1]])

    def test_prorated_premium_fails_even_if_candidate_matches(self):
        self.dependencies['premium_total'] = 100
        with self.assertRaises(ValueError):
            self.check([self.source[1]])


if __name__ == '__main__':
    unittest.main()
