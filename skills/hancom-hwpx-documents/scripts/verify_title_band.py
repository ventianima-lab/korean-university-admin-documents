#!/usr/bin/env python3
"""Read-only comparison of originally blank title-band cells in two HWPX tables.

The caller selects the exact authoritative master, both table locations, the
first business-field row, and an existing title anchor. This is not a general
classifier: choose the band from the real template and inspect the page too.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS = {"hp": HP}


def _table(path, section, ordinal):
    if type(ordinal) is not int or ordinal < 0:
        raise ValueError("table ordinal must be a nonnegative integer")
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read(section))
    tables = root.findall(".//hp:tbl", NS)
    if ordinal >= len(tables):
        raise ValueError("table ordinal does not exist")
    return tables[ordinal]


def _cells(table):
    cells = {}
    for cell in table.findall("./hp:tr/hp:tc", NS):
        address = cell.find("hp:cellAddr", NS)
        if address is None:
            raise ValueError("table cell lacks an address")
        key = (int(address.get("rowAddr")), int(address.get("colAddr")))
        if key in cells:
            raise ValueError("duplicate cell address")
        cells[key] = "".join("".join(t.itertext()) for t in cell.findall(".//hp:t", NS)).strip()
    return cells


def check_title_band(candidate, band):
    """Return a result for the given selected title band; never change a file."""
    master = Path(band["master"])
    candidate = Path(candidate)
    cutoff = band["first_content_row"]
    title = (band["title_row"], band["title_col"])
    if type(cutoff) is not int or cutoff < 1 or any(type(x) is not int or x < 0 for x in title):
        raise ValueError("invalid title or first-content-row location")
    if title[0] >= cutoff or not str(band.get("source", "")).strip():
        raise ValueError("title anchor must be inside the band and cite its master")
    master_sha = hashlib.sha256(master.read_bytes()).hexdigest()
    candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    original = _cells(_table(master, band["master_section"], band["master_table"]))
    edited = _cells(_table(candidate, band["target_section"], band["target_table"]))
    if not any(row == cutoff for row, col in original) or not any(row == cutoff for row, col in edited):
        raise ValueError("first business-field row was not found in both tables")
    if not original.get(title) or edited.get(title) != original[title]:
        raise ValueError("title anchor differs from the selected authoritative master")
    protected = {key for key, text in original.items() if key[0] < cutoff and not text}
    if not protected:
        raise ValueError("no blank cells identified in the title band")
    exceptions = {}
    for item in band.get("exceptions", []):
        key = (item.get("row"), item.get("col"))
        if (key not in protected or key in exceptions or not item.get("source", "").strip()
                or not item.get("expected", "").strip()):
            raise ValueError("each explicit exception needs a unique blank cell, value and user source")
        exceptions[key] = item["expected"].strip()
    issues = []
    for key in sorted(protected):
        expected = exceptions.get(key, "")
        if key not in edited:
            issues.append({"row": key[0], "col": key[1], "problem": "missing_cell"})
        elif edited[key] != expected:
            issues.append({"row": key[0], "col": key[1], "problem": "unexpected_text"})
    for key in sorted(set(edited) - set(original)):
        if key[0] < cutoff and edited[key]:
            issues.append({"row": key[0], "col": key[1], "problem": "new_cell_text"})
    if (hashlib.sha256(master.read_bytes()).hexdigest() != master_sha or
            hashlib.sha256(candidate.read_bytes()).hexdigest() != candidate_sha):
        raise ValueError("master or candidate changed during inspection")
    return {"status": "PASS" if not issues else "FAIL", "checked_blank_cells": len(protected),
            "issues": issues, "candidate_sha256": candidate_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("band_json", type=Path, help="Private JSON title-band location from the authoritative template")
    args = parser.parse_args()
    try:
        band = json.loads(args.band_json.read_text(encoding="utf-8-sig"))
        result = check_title_band(args.candidate, band)
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError) as exc:
        parser.exit(2, "TITLE_BAND_ERROR: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
