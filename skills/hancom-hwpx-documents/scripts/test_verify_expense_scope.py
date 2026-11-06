"""Synthetic regression: roster membership cannot override lunch-only costing."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from verify_per_person_costs import verify


class ExpenseScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = Path(self.temp.name) / "synthetic-costs.hwpx"
        self.spec = {"expense_scope": {
            "revision": "current-restriction", "source": "synthetic latest instruction",
            "rows": [], "restrictions": [{"role": "provider", "only_item_ids": ["lunch"],
                                          "source": "synthetic instruction: provider lunch only"}]},
            "items": []}
        for index, key in enumerate(("lunch", "dinner", "admission", "ride", "snack")):
            roles = {"learners": 3, "staff": 1}
            if key == "lunch":
                roles["provider"] = 1
            self.spec["expense_scope"]["rows"].append({
                "id": key, "roles": dict(roles), "source": "independent synthetic scope row"})
            self.spec["items"].append({"id": key, "scope_revision": "current-restriction",
                "roles": roles, "source": "synthetic costing evidence", "unit_price": 1200,
                "servings": 1, "amount": sum(roles.values()) * 1200,
                "bindings": [{"path": str(self.saved), "table": 0, "row": index,
                              "col": 0, "paragraph": 0}]})
        self.write_saved()

    def tearDown(self):
        self.temp.cleanup()

    def write_saved(self):
        rows = []
        for index, item in enumerate(self.spec["items"]):
            value = f'{sum(item["roles"].values())}명×1200원×1회'
            rows.append(f'<hp:tr><hp:tc><hp:cellAddr rowAddr="{index}" colAddr="0"/>'
                        f'<hp:subList><hp:p><hp:run><hp:t>{value}</hp:t></hp:run></hp:p>'
                        '</hp:subList></hp:tc></hp:tr>')
        xml = ('<hp:root xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
               '<hp:tbl>' + ''.join(rows) + '</hp:tbl></hp:root>')
        with ZipFile(self.saved, "w") as package:
            package.writestr("Contents/section0.xml", xml)

    def test_current_scope_passes_with_different_item_populations(self):
        checked = verify(self.spec, require_scope=True)
        self.assertEqual([row["factors"][0] for row in checked], [5, 4, 4, 4, 4])

    def test_correct_arithmetic_cannot_hide_inherited_provider_costs(self):
        for index in range(1, 5):
            with self.subTest(item=index):
                trial = copy.deepcopy(self.spec)
                trial["items"][index]["roles"]["provider"] = 1
                trial["items"][index]["amount"] = 6000
                with self.assertRaisesRegex(ValueError, "latest expense scope"):
                    verify(trial, require_scope=True)

    def test_copying_wrong_roles_into_expected_map_still_violates_only(self):
        self.spec["expense_scope"]["rows"][2]["roles"]["provider"] = 1
        with self.assertRaisesRegex(ValueError, "Only-item exclusion"):
            verify(self.spec)

    def test_old_scenario_revision_is_rejected(self):
        self.spec["items"][0]["scope_revision"] = "superseded-all-persons"
        with self.assertRaisesRegex(ValueError, "Stale expense scope"):
            verify(self.spec)

    def test_missing_scope_is_rejected_when_required(self):
        self.spec.pop("expense_scope")
        with self.assertRaisesRegex(ValueError, "Latest independent expense scope"):
            verify(self.spec, require_scope=True)

    def test_omitted_cost_row_cannot_pass_partial_inventory(self):
        self.spec["items"].pop()
        with self.assertRaisesRegex(ValueError, "omit independent scope"):
            verify(self.spec)

    def test_unknown_allowlist_item_and_missing_restriction_fail(self):
        trial = copy.deepcopy(self.spec)
        trial["expense_scope"]["restrictions"][0]["only_item_ids"] = ["old-lunch"]
        with self.assertRaisesRegex(ValueError, "unknown item IDs"):
            verify(trial)
        self.spec["expense_scope"]["restrictions"] = []
        with self.assertRaisesRegex(ValueError, "only-item restrictions are required"):
            verify(self.spec)

    def test_saved_stale_factor_fails_even_with_correct_scope(self):
        with ZipFile(self.saved) as package:
            xml = package.read("Contents/section0.xml").decode()
        xml = xml.replace("4명", "5명", 1)
        with ZipFile(self.saved, "w") as package:
            package.writestr("Contents/section0.xml", xml)
        with self.assertRaisesRegex(ValueError, "Saved factors disagree"):
            verify(self.spec, require_scope=True)

    def test_cli_requires_scope_and_preserves_backward_compatibility(self):
        inventory = Path(self.temp.name) / "inventory.json"
        script = Path(__file__).with_name("verify_per_person_costs.py")
        def run():
            inventory.write_text(json.dumps(self.spec), encoding="utf-8")
            return subprocess.run([sys.executable, str(script), str(inventory), "--scope-check"],
                                  capture_output=True, text=True)
        self.assertEqual(run().returncode, 0)
        self.spec.pop("expense_scope")
        self.assertNotEqual(run().returncode, 0)
        self.assertEqual(len(verify(self.spec)), 5)


if __name__ == "__main__":
    unittest.main()
