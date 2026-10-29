"""Reconcile a real saved list to a staged packet and distinguish roster roles."""
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import json
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

import verify_required_packet as packet


class PacketRoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.letter = self.root / "letter.hwpx"
        self.template = self.root / "official.hwpx"
        self.rosters = [self.root / ("roster%d.hwpx" % i) for i in range(3)]
        self.plan = self.root / "plan.hwpx"
        self.package_letter("붙임  1. 운영계획서 --- 1부.  2. 참석예정자 명단 --- 3부. 끝.")
        self.plan.write_bytes(b"separate plan")
        self.package_roster(self.template)
        for path in self.rosters:
            self.package_roster(path)
        self.entries = [
            {"id": "plan", "title": "운영계획서", "role": "other",
             "members": [{"path": str(self.plan), "locations": ["document"], "evidence": "inspected plan"}]},
            {"id": "rosters", "title": "참석예정자 명단", "role": "planned_roster",
             "members": [{"path": str(p), "locations": ["document"], "evidence": "inspected roster"}
                         for p in self.rosters]},
        ]
        self.attachment = {
            "letter": str(self.letter), "start_marker": "붙임", "end_marker": "끝.",
            "actual_files": [str(self.plan)] + [str(p) for p in self.rosters],
            "paragraphs": [{"section": "Contents/section0.xml", "paragraph": 0, "segments": [
                {"kind": "context", "text": "붙임  1. "},
                {"kind": "item", "text": "운영계획서 --- 1부.", "entries": ["plan"]},
                {"kind": "context", "text": "  2. "},
                {"kind": "item", "text": "참석예정자 명단 --- 3부.", "entries": ["rosters"]},
                {"kind": "context", "text": " 끝."}]}],
            "entries": self.entries,
        }
        self.planned = [{
            "path": str(path), "section": "Contents/section0.xml", "table": 0,
            "header_row": 0, "template_source": str(self.template), "source_location": "form",
            "template_role": "planned_roster", "headers": [
                {"col": 0, "text": "연번", "span": 1},
                {"col": 1, "text": "성명", "span": 1},
                {"col": 2, "text": "소속", "span": 1}],
            "grid": {"first_row": 1, "last_row": 1,
                     "columns": [{"col": 0, "span": 1}, {"col": 1, "span": 1},
                                 {"col": 2, "span": 1}]}} for path in self.rosters]
        self.artifacts = [{"status": "ready", "paths": [str(p) for p in self.rosters]}]

    def package_letter(self, text):
        root = ET.Element("{" + packet.HP[1:-1] + "}sec")
        p = ET.SubElement(root, packet.HP + "p")
        run = ET.SubElement(p, packet.HP + "run")
        ET.SubElement(run, packet.HP + "t").text = text
        with ZipFile(self.letter, "w") as z:
            z.writestr("Contents/section0.xml", ET.tostring(root, encoding="utf-8"))

    def package_roster(self, path, headers=("연번", "성명", "소속"), content="학생"):
        root = ET.Element(packet.HP + "sec")
        table = ET.SubElement(root, packet.HP + "tbl")
        for rownum, values in enumerate((headers, ("1", content, "학과"))):
            row = ET.SubElement(table, packet.HP + "tr")
            for col, value in enumerate(values):
                cell = ET.SubElement(row, packet.HP + "tc")
                ET.SubElement(cell, packet.HP + "cellAddr", rowAddr=str(rownum), colAddr=str(col))
                run = ET.SubElement(cell, packet.HP + "run")
                ET.SubElement(run, packet.HP + "t").text = value
        with ZipFile(path, "w") as z:
            z.writestr("Contents/section0.xml", ET.tostring(root, encoding="utf-8"))

    def issues(self, check):
        return {i["problem"] for i in packet.check_attachment_list(check)}

    def test_matching_packet_and_signature_free_roster_pass(self):
        self.assertEqual(self.issues(self.attachment), set())
        self.assertEqual(packet.check_planned_rosters(self.planned, self.artifacts), [])

    def test_count_mismatch_and_unlisted_extra_fail(self):
        wrong = copy.deepcopy(self.attachment)
        wrong["entries"][1]["members"].pop()
        self.assertIn("attachment_count_mismatch", self.issues(wrong))
        self.assertIn("unlisted_actual_attachment", self.issues(wrong))
        extra = self.root / "extra.hwpx"
        extra.write_bytes(b"extra")
        wrong = copy.deepcopy(self.attachment)
        wrong["actual_files"].append(str(extra))
        self.assertIn("unlisted_actual_attachment", self.issues(wrong))

    def test_missing_or_twice_counted_unit_fails(self):
        wrong = copy.deepcopy(self.attachment)
        wrong["actual_files"].remove(str(self.rosters[0]))
        self.assertIn("listed_attachment_not_in_packet", self.issues(wrong))
        wrong = copy.deepcopy(self.attachment)
        wrong["entries"][1]["members"][1] = copy.deepcopy(wrong["entries"][1]["members"][0])
        self.assertIn("attachment_unit_counted_twice", self.issues(wrong))

    def test_combined_file_can_hold_three_independently_identified_documents(self):
        combined = self.root / "combined.hwpx"
        combined.write_bytes(b"synthetic combined attachment")
        grouped = copy.deepcopy(self.attachment)
        grouped["entries"][1]["members"] = [
            {"path": str(combined), "locations": ["first form", "second form", "third form"],
             "evidence": "inspected each synthetic document"}]
        grouped["actual_files"] = [str(self.plan), str(combined)]
        self.assertEqual(self.issues(grouped), set())

    def test_candidate_must_match_independent_saved_list(self):
        self.package_letter("붙임  1. 사용자 수정 계획서 --- 1부. 끝.")
        self.assertIn("attachment_paragraph_differs", self.issues(self.attachment))

    def test_grouped_items_require_each_and_individual_units(self):
        self.package_letter("붙임  운영계획서·참석예정자 명단 --- 각 1부. 끝.")
        group = copy.deepcopy(self.attachment)
        group["entries"][1]["members"] = group["entries"][1]["members"][:1]
        group["actual_files"] = group["actual_files"][:2]
        group["paragraphs"][0]["segments"] = [
            {"kind": "context", "text": "붙임  "},
            {"kind": "item", "text": "운영계획서·참석예정자 명단 --- 각 1부.",
             "entries": ["plan", "rosters"]},
            {"kind": "context", "text": " 끝."}]
        self.assertEqual(self.issues(group), set())
        group["paragraphs"][0]["segments"][1]["text"] = "운영계획서·참석예정자 명단 --- 1부."
        self.assertIn("attachment_count_ambiguous", self.issues(group))

    def test_signin_sheet_and_blank_extra_signature_column_fail(self):
        self.package_roster(self.rosters[0], content="학생 (서명)")
        issues = packet.check_planned_rosters(self.planned, self.artifacts)
        self.assertIn("planned_roster_signature_text", {i["problem"] for i in issues})
        self.package_roster(self.rosters[0], headers=("연번", "성명", "소속", ""))
        issues = packet.check_planned_rosters(self.planned, self.artifacts)
        self.assertIn("planned_roster_header_mismatch", {i["problem"] for i in issues})
        with ZipFile(self.rosters[0]) as source:
            root = ET.fromstring(source.read("Contents/section0.xml"))
        rows = list(root.iter(packet.HP + "tr"))
        rows[0].remove(rows[0].findall(packet.HP + "tc")[-1])
        extra = ET.SubElement(rows[1], packet.HP + "tc")
        ET.SubElement(extra, packet.HP + "cellAddr", rowAddr="1", colAddr="3")
        with ZipFile(self.rosters[0], "w") as target:
            target.writestr("Contents/section0.xml", ET.tostring(root, encoding="utf-8"))
        issues = packet.check_planned_rosters(self.planned, self.artifacts)
        self.assertIn("planned_roster_grid_mismatch", {i["problem"] for i in issues})

    def test_signin_form_source_and_label_are_not_planned_rosters(self):
        wrong = copy.deepcopy(self.planned)
        wrong[0]["template_role"] = "signature_sheet"
        self.assertIn("planned_roster_wrong_source_role",
                      {i["problem"] for i in packet.check_planned_rosters(wrong, self.artifacts)})
        wrong_list = copy.deepcopy(self.attachment)
        wrong_list["entries"][1]["title"] = "참석자 서명부"
        self.assertIn("planned_roster_listed_as_signature", self.issues(wrong_list))
        wrong_list = copy.deepcopy(self.attachment)
        wrong_list["paragraphs"][0]["segments"][3]["text"] = "참석예정자 명단 서명부 --- 3부."
        self.assertIn("planned_roster_listed_as_signature", self.issues(wrong_list))

    def test_end_to_end_gate_fails_when_planned_roster_is_omitted(self):
        def checks(paths):
            return [{"path": str(p), "not_applicable": True, "master": str(self.template),
                     "source": "inspected synthetic template", "reason": "no title band"}
                    for p in paths]
        manifest = {
            "requirements": [{"id": "plan", "source": "manual"},
                             {"id": "rosters", "source": "manual"}],
            "artifacts": [
                {"id": "plan", "status": "ready", "paths": [str(self.plan)],
                 "verification": "inspected", "title_band_checks": checks([self.plan])},
                {"id": "rosters", "status": "ready", "paths": [str(p) for p in self.rosters],
                 "verification": "inspected", "title_band_checks": checks(self.rosters)}],
            "expense_reviews": [{"category": "programme", "source": "manual",
                                 "items": [{"label": "plan", "status": "required", "requirement_id": "plan"},
                                           {"label": "rosters", "status": "required", "requirement_id": "rosters"}]}],
            "attachment_check": copy.deepcopy(self.attachment),
            "planned_rosters": copy.deepcopy(self.planned),
        }
        self.assertEqual(packet.audit(manifest, attachment_check=True, planned_roster_check=True)["status"], "PASS")
        manifest["planned_rosters"].pop()
        result = packet.audit(manifest, attachment_check=True, planned_roster_check=True)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["planned_roster_issues"][0]["problem"],
                         "planned_roster_attachment_mapping_mismatch")
        target = self.root / "inventory.json"
        target.write_text(json.dumps(manifest), encoding="utf-8")
        script = Path(packet.__file__)
        cli = subprocess.run([sys.executable, str(script), str(target), "--attachment-check",
                              "--planned-roster-check"], capture_output=True, text=True,
                             encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(cli.returncode, 1, cli.stderr)


if __name__ == "__main__":
    unittest.main()
