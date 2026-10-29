"""Role confirmations must expose every independently counted group."""
import unittest
from verify_per_person_costs import verify_role_summary


class RoleConfirmationTests(unittest.TestCase):
    def confirmation(self, text, roles=None, total=5):
        return {"text": text, "roles": roles or {"교수": 1, "산업체": 4},
                "total": total, "source": "synthetic attendance source"}

    def test_role_breakdown_and_total_pass(self):
        got = verify_role_summary(self.confirmation("회의 5명: 교수 1명, 산업체 4명"))
        self.assertEqual(got["total"], 5)

    def test_total_alone_does_not_hide_missing_professor(self):
        with self.assertRaisesRegex(ValueError, "Role or count missing"):
            verify_role_summary(self.confirmation("회의 5명: 산업체 4명"))

    def test_correct_labels_cannot_hide_wrong_sum(self):
        with self.assertRaisesRegex(ValueError, "do not sum"):
            verify_role_summary(self.confirmation("회의 6명: 교수 1명, 산업체 4명", total=6))

    def test_added_assistant_must_appear_in_question(self):
        roles = {"학생": 8, "교수": 1, "산업체": 4, "조교": 1}
        with self.assertRaisesRegex(ValueError, "Role or count missing"):
            verify_role_summary(self.confirmation("석식 14명: 학생 8명, 교수 1명, 산업체 4명", roles, 14))
        self.assertEqual(verify_role_summary(self.confirmation(
            "석식 14명: 학생 8명, 교수 1명, 산업체 4명, 조교 1명", roles, 14))["total"], 14)

    def test_unstated_total_does_not_pass(self):
        with self.assertRaisesRegex(ValueError, "Total count missing"):
            verify_role_summary(self.confirmation("교수 1명, 산업체 4명"))


if __name__ == "__main__":
    unittest.main()
