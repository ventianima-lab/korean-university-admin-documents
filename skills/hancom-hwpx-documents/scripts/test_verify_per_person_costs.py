"""Role confirmations must expose every independently counted group."""
import unittest
import tempfile
from pathlib import Path
from zipfile import ZipFile
from verify_per_person_costs import verify_role_summary
from verify_per_person_costs import verify


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

    def roster_confirmation(self, names=None, total=3, roles=None):
        return {**self.confirmation("3명: 담당자 1명, 참여자 2명", roles or {"담당자": 1, "참여자": 2}, total),
                "named_people": names if names is not None else
                [{"name": "담당자A", "role": "담당자"}] +
                [{"name": f"참여자{i}", "role": "참여자"} for i in range(1, 3)],
                "people_source": "independently transcribed planned roster"}

    def test_named_roster_and_corrected_total_pass(self):
        self.assertEqual(verify_role_summary(self.roster_confirmation())["total"], 3)

    def test_stale_approved_total_fails(self):
        with self.assertRaisesRegex(ValueError, "approved total"):
            verify_role_summary(self.roster_confirmation(total=6))
        spec = self.roster_confirmation()
        spec["approved_total"] = 4
        with self.assertRaisesRegex(ValueError, "approved_total disagrees"):
            verify_role_summary(spec)

    def test_missing_or_extra_person_fails(self):
        names = self.roster_confirmation()["named_people"]
        with self.assertRaisesRegex(ValueError, "approved total"):
            verify_role_summary(self.roster_confirmation(names=names[:-1]))
        with self.assertRaisesRegex(ValueError, "approved total"):
            verify_role_summary(self.roster_confirmation(names=names + [{"name": "extra", "role": "산업체"}], total=5))

    def test_duplicate_name_fails(self):
        names = self.roster_confirmation()["named_people"]
        names[1]["name"] = names[0]["name"]
        with self.assertRaisesRegex(ValueError, "Duplicate name"):
            verify_role_summary(self.roster_confirmation(names=names))

    def test_role_mismatch_fails(self):
        names = self.roster_confirmation()["named_people"]
        names[0]["role"] = "산업체"
        with self.assertRaisesRegex(ValueError, "role grouping"):
            verify_role_summary(self.roster_confirmation(names=names))

    def test_named_roster_checks_every_saved_cost_binding(self):
        xml = '''<?xml version="1.0"?><hp:root xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:tbl><hp:tr><hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p><hp:run><hp:t>3명×1200원×1회</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr></hp:tbl></hp:root>'''
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder) / "cost.hwpx"
            with ZipFile(saved, "w") as package:
                package.writestr("Contents/section0.xml", xml)
            item = {"roles": {"담당자": 1, "참여자": 2}, "named_people": self.roster_confirmation()["named_people"],
                    "people_source": "independently transcribed planned roster", "approved_total": 3,
                    "unit_price": 1200, "servings": 1, "amount": 3600, "source": "approved costing",
                    "bindings": [{"path": str(saved), "table": 0, "row": 0, "col": 0, "paragraph": 0}]}
            self.assertEqual(verify({"items": [item]})[0]["factors"], (3, 1200, 1))


if __name__ == "__main__":
    unittest.main()
