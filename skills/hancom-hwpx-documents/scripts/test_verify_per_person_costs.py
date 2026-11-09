"""Role confirmations must expose every independently counted group."""
import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
from verify_per_person_costs import verify_role_summary, verify, verify_carry_forward


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


class PurposeSpecificPopulationTests(unittest.TestCase):
    def test_party_insurance_and_lunch_use_independent_population_maps(self):
        people = ([{"name": f"A{i}", "role": "group_a"} for i in range(6)]
                  + [{"name": f"B{i}", "role": "group_b"} for i in range(4)]
                  + [{"name": "G0", "role": "guest"}])
        instruction = ("Synthetic instruction for event-alpha only: party and lunch include "
                       "groups A/B and the guest; insurance includes groups A/B and excludes the guest.")

        def population(purpose, roles, names, total, source=instruction):
            return {"roles": roles, "total": total, "named_people": names,
                    "text": f"{purpose} {total}명: " + ", ".join(f"{r} {n}명" for r, n in roles.items()),
                    "source": source, "people_source": source}

        party = population("party", {"group_a": 6, "group_b": 4, "guest": 1}, people, 11)
        insurance = population("insurance", {"group_a": 6, "group_b": 4}, people[:-1], 10)
        lunch = population("lunch", {"group_a": 6, "group_b": 4, "guest": 1}, people, 11)
        for purpose, spec, total in (("party", party, 11), ("insurance", insurance, 10),
                                     ("lunch", lunch, 11)):
            with self.subTest(purpose=purpose):
                self.assertEqual(verify_role_summary(spec)["total"], total)
        # Propagating the party total and role counts must not replace the
        # independently sourced insurance population, even when arithmetic agrees.
        copied = {**insurance, "roles": party["roles"], "total": party["total"], "text": party["text"]}
        with self.assertRaisesRegex(ValueError, "approved total"):
            verify_role_summary(copied)
        reduced_lunch = {**lunch, "roles": insurance["roles"], "total": 10, "text": insurance["text"]}
        with self.assertRaisesRegex(ValueError, "approved total"):
            verify_role_summary(reduced_lunch)
        # A different explicit instruction may include the same role in insurance.
        other = population("insurance", party["roles"], people, 11,
                           "Synthetic event-beta instruction: insurance includes groups A/B and the guest.")
        self.assertEqual(verify_role_summary(other)["total"], 11)


class CarryForwardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = Path(self.temp.name) / "financial-fields.hwpx"
        self.texts = ["9000원", "9000원", "200원", "300원", "500원", "800원", "800원", "", ""]
        self.formula_fields = {}
        self._write_package()

    def tearDown(self):
        self.temp.cleanup()

    def _write_package(self):
        rows = ""
        for i, text in enumerate(self.texts):
            formula = ""
            if i in self.formula_fields:
                last_result, command = self.formula_fields[i]
                formula = (f'<hp:ctrl><hp:fieldBegin id="f{i}" type="FORMULA"><hp:parameters>'
                           f'<hp:stringParam name="Command">{command}</hp:stringParam>'
                           f'<hp:stringParam name="LastResult">{last_result}</hp:stringParam>'
                           f'</hp:parameters></hp:fieldBegin></hp:ctrl>')
            rows += (f'<hp:tr><hp:tc><hp:cellAddr rowAddr="{i}" colAddr="0"/><hp:subList><hp:p>'
                     f'<hp:run>{formula}<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr>')
        xml = f'<?xml version="1.0"?><hp:root xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:tbl>{rows}</hp:tbl></hp:root>'
        with ZipFile(self.saved, "w") as package:
            package.writestr("Contents/section0.xml", xml)

    def binding(self, row):
        return {"path": str(self.saved), "table": 0, "row": row, "col": 0, "paragraph": 0}

    def inventory(self):
        return {"stages": {
            "prior_authorized": {
                "source_total": {"amount": 9000, "source": "independent approval record"},
                "rows": [{"id": "approved_budget", "amount": 9000, "basis": "approved_budget",
                          "source": "approval record row", "bindings": [self.binding(0)]}],
                "total_bindings": [self.binding(1)]},
            "prior_actual": {
                "source_total": {"amount": 500, "source": "independent settled-period total"},
                "rows": [
                    {"id": "receipt_a", "amount": 200, "basis": "receipt", "source": "receipt A",
                     "bindings": [self.binding(2)]},
                    {"id": "receipt_b", "amount": 300, "basis": "receipt", "source": "receipt B",
                     "bindings": [self.binding(3)]}],
                "total_bindings": [self.binding(4)]},
            "current_planned": {
                "source_total": {"amount": 800, "source": "independent current plan approval"},
                "rows": [{"id": "planned_line", "amount": 800, "basis": "approved_plan",
                          "source": "approved current plan row", "bindings": [self.binding(5)]}],
                "total_bindings": [self.binding(6)]}},
            "future_evidence_blanks": [
                {**self.binding(7), "reason": "actual attendance has not occurred"},
                {**self.binding(8), "reason": "future signature is not yet available"}]}

    def test_prior_actual_and_current_plan_pass_while_future_evidence_stays_blank(self):
        checked = verify_carry_forward(self.inventory())
        self.assertEqual(checked["stages"]["prior_actual"]["total"], 500)
        self.assertEqual(checked["stages"]["current_planned"]["total"], 800)
        self.assertEqual(checked["future_evidence_blanks"], 2)

    def test_blank_known_cumulative_actual_fails(self):
        self.texts[4] = ""
        self._write_package()
        with self.assertRaisesRegex(ValueError, "only one monetary amount"):
            verify_carry_forward(self.inventory())

    def test_current_plan_cannot_replace_saved_prior_actual(self):
        spec = self.inventory()
        spec["stages"]["prior_actual"]["rows"][0]["bindings"] = [self.binding(5)]
        with self.assertRaisesRegex(ValueError, "disagrees with source amount"):
            verify_carry_forward(spec)

    def test_prior_planned_basis_cannot_be_counted_as_receipt_actual(self):
        spec = self.inventory()
        spec["stages"]["prior_actual"]["rows"][0]["basis"] = "approved_plan"
        with self.assertRaisesRegex(ValueError, "Wrong financial basis"):
            verify_carry_forward(spec)

    def test_signed_settlement_rows_are_an_allowed_actual_basis(self):
        spec = self.inventory()
        stage = spec["stages"]["prior_actual"]
        stage["source_total"]["source"] = "signed prior-period settlement total"
        for row in stage["rows"]:
            row["basis"] = "settlement_record"
            row["source"] = "signed settlement actual row"
        self.assertEqual(verify_carry_forward(spec)["stages"]["prior_actual"]["total"], 500)

    def test_bare_amount_in_header_unit_format_passes(self):
        self.texts[2] = "200"
        self.texts[4] = "500"
        self._write_package()
        self.assertEqual(verify_carry_forward(self.inventory())["stages"]["prior_actual"]["total"], 500)

    def test_non_amount_paragraphs_fail_fullmatch(self):
        for value in ("2026.11.04", "=200", "200원 300원"):
            with self.subTest(value=value):
                self.texts[2] = value
                self._write_package()
                with self.assertRaisesRegex(ValueError, "only one monetary amount"):
                    verify_carry_forward(self.inventory())

    def test_compact_calendar_date_is_not_accepted_as_amount(self):
        self.texts[2] = "20261104"
        self._write_package()
        with self.assertRaisesRegex(ValueError, "looks like a date"):
            verify_carry_forward(self.inventory())

    def test_consistent_formula_caches_are_preserved_and_pass(self):
        self.formula_fields[6] = ("800", "=SUM(A1:A2)??%g,;;800")
        self._write_package()
        self.assertEqual(verify_carry_forward(self.inventory())["stages"]["current_planned"]["total"], 800)

    def test_formula_last_result_mismatch_fails(self):
        self.formula_fields[6] = ("300", "=SUM(A1:A2)??%g,;;800")
        self._write_package()
        with self.assertRaisesRegex(ValueError, "FORMULA LastResult"):
            verify_carry_forward(self.inventory())

    def test_formula_command_cached_result_mismatch_fails(self):
        self.formula_fields[6] = ("800", "=SUM(A1:A2)??%g,;;300")
        self._write_package()
        with self.assertRaisesRegex(ValueError, "FORMULA Command cached result"):
            verify_carry_forward(self.inventory())

    def test_stage_source_total_is_checked_independently(self):
        spec = self.inventory()
        spec["stages"]["prior_actual"]["source_total"]["amount"] = 600
        with self.assertRaisesRegex(ValueError, "not independently stated total"):
            verify_carry_forward(spec)

    def test_future_evidence_field_must_remain_blank(self):
        self.texts[7] = "서명"
        self._write_package()
        with self.assertRaisesRegex(ValueError, "must remain blank"):
            verify_carry_forward(self.inventory())

    def test_carry_forward_cli_mode(self):
        spec_path = Path(self.temp.name) / "inventory.json"
        spec_path.write_text(json.dumps(self.inventory(), ensure_ascii=False), encoding="utf-8")
        script = Path(__file__).with_name("verify_per_person_costs.py")
        result = subprocess.run([sys.executable, str(script), str(spec_path), "--carry-forward-check"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"prior_actual"', result.stdout)


if __name__ == "__main__":
    unittest.main()
