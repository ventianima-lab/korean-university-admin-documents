"""Read every XLSX sheet without resaving; verify exact classification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def text_runs(element):
    return "" if element is None else "".join(t.text or "" for t in element.iterfind(".//m:t", NS))


def inspect(path: Path) -> dict:
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    sheets = []
    with zipfile.ZipFile(path) as package:
        shared = []
        if "xl/sharedStrings.xml" in package.namelist():
            shared = [text_runs(x) for x in ET.fromstring(package.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        relationships = {x.attrib["Id"]: x.attrib for x in ET.fromstring(package.read("xl/_rels/workbook.xml.rels"))}
        workbook = ET.fromstring(package.read("xl/workbook.xml"))
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            rel = relationships[sheet.attrib[REL_ID]]
            if rel.get("TargetMode") == "External":
                raise ValueError("External sheet relationship cannot provide archive evidence")
            target = rel["Target"].replace("\\", "/")
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            xml = ET.fromstring(package.read(member))
            cells = {}
            for cell in xml.findall("m:sheetData/m:row/m:c", NS):
                value = cell.find("m:v", NS)
                raw = value.text or "" if value is not None else ""
                kind = cell.get("t", "n")
                if kind == "s":
                    raw = shared[int(raw)]
                elif kind == "inlineStr":
                    raw = text_runs(cell.find("m:is", NS))
                formula = cell.find("m:f", NS)
                if raw != "" or formula is not None:
                    cells[cell.attrib["r"]] = {"value": raw, "type": kind}
                    if formula is not None:
                        cells[cell.attrib["r"]]["formula"] = formula.text or ""
            sheets.append({"name": sheet.attrib["name"], "state": sheet.get("state", "visible"), "member": member,
                           "populated_cell_count": len(cells), "cells": cells})
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    if before != after:
        raise ValueError("Source changed during inspection")
    return {"source": str(path.resolve()), "sha256": before, "sheet_count": len(sheets), "sheets": sheets}


def check_cells(inventory: dict, expectations: list) -> list:
    sheets = {sheet["name"]: sheet for sheet in inventory["sheets"]}
    results = []
    for name, address, expected in expectations:
        actual = sheets.get(name, {}).get("cells", {}).get(address, {}).get("value")
        results.append({"sheet": name, "cell": address, "expected": expected,
                        "actual": actual, "passed": actual == expected})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-cell", nargs=3, action="append", default=[], metavar=("SHEET", "CELL", "VALUE"))
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error("Evidence output must not overwrite the source workbook")
    result = inspect(args.input)
    result["checks"] = check_cells(result, args.expect_cell)
    result["status"] = "PASSED" if all(c["passed"] for c in result["checks"]) else "FAILED"
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "sheet_count": result["sheet_count"],
                          "sheets": [{k: s[k] for k in ("name", "state", "populated_cell_count")} for s in result["sheets"]],
                          "check_count": len(result["checks"]), "output": str(args.output)}, ensure_ascii=False))
    else:
        print(encoded)
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
