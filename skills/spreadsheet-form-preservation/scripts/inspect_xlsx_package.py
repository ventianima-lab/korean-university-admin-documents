#!/usr/bin/env python3
"""Inspect XLSX package integrity and preservation-sensitive structure."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REQUIRED = {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel_source(name: str) -> str:
    directory, filename = posixpath.split(name)
    parent = posixpath.dirname(directory)
    return posixpath.join(parent, filename[:-5]) if filename.endswith(".rels") else ""


def resolved_target(rels_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(rel_source(rels_name)), target))


def inspect(path: Path) -> dict:
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        name_set = set(names)
        missing = sorted(REQUIRED - name_set)
        if missing:
            errors.append("missing required parts: " + ", ".join(missing))

        roots: dict[str, ET.Element] = {}
        for name in names:
            if name.endswith((".xml", ".rels")):
                try:
                    roots[name] = ET.fromstring(archive.read(name))
                except ET.ParseError as exc:
                    errors.append(f"malformed XML {name}: {exc}")
        for rels_name, root in roots.items():
            if not rels_name.endswith(".rels"):
                continue
            for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                if rel.get("TargetMode", "").lower() == "external":
                    continue
                target = rel.get("Target")
                if not target or resolved_target(rels_name, target) not in name_set:
                    errors.append(f"broken relationship {rels_name} -> {target}")

        workbook = roots.get("xl/workbook.xml")
        rels = roots.get("xl/_rels/workbook.xml.rels")
        relation_targets = {}
        if rels is not None:
            relation_targets = {
                rel.get("Id"): resolved_target("xl/_rels/workbook.xml.rels", rel.get("Target", ""))
                for rel in rels.findall(f"{{{REL_NS}}}Relationship")
            }

        sheets = []
        if workbook is not None:
            for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
                rel_id = sheet.get(f"{{{DOC_REL_NS}}}id")
                sheets.append({
                    "name": sheet.get("name"),
                    "state": sheet.get("state", "visible"),
                    "part": relation_targets.get(rel_id),
                })
        formulas = merges = row_heights = column_widths = validations = 0
        for sheet in sheets:
            root = roots.get(sheet.get("part") or "")
            if root is None:
                continue
            formulas += len(root.findall(f".//{{{MAIN_NS}}}f"))
            merges += len(root.findall(f".//{{{MAIN_NS}}}mergeCell"))
            row_heights += sum(1 for node in root.findall(f".//{{{MAIN_NS}}}row") if node.get("ht") is not None)
            column_widths += sum(1 for node in root.findall(f".//{{{MAIN_NS}}}col") if node.get("width") is not None)
            validations += len(root.findall(f".//{{{MAIN_NS}}}dataValidation"))

        names_nodes = workbook.findall(f".//{{{MAIN_NS}}}definedName") if workbook is not None else []
        sensitive_parts = [
            name for name in names
            if name.startswith(("xl/worksheets/", "xl/charts/", "xl/drawings/", "xl/printerSettings/"))
            or name in {"xl/workbook.xml", "xl/styles.xml", "xl/sharedStrings.xml", "xl/calcChain.xml"}
            or name.endswith(".rels")
        ]
        source = "\n".join(f"{name}:{digest(archive.read(name))}" for name in sorted(sensitive_parts)).encode()
        return {
            "path": str(path.resolve()),
            "valid": not errors,
            "errors": errors,
            "package_sha256": digest(path.read_bytes()),
            "structural_fingerprint": digest(source),
            "sheets": sheets,
            "defined_names": [{"name": node.get("name"), "value": node.text or ""} for node in names_nodes],
            "formulas": formulas,
            "merged_cells": merges,
            "custom_row_heights": row_heights,
            "custom_column_widths": column_widths,
            "data_validations": validations,
            "printer_settings_parts": sorted(name for name in names if name.startswith("xl/printerSettings/")),
            "chart_parts": sorted(name for name in names if name.startswith("xl/charts/")),
            "drawing_parts": sorted(name for name in names if name.startswith("xl/drawings/")),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbooks", nargs="+", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reports = []
    for path in args.workbooks:
        if not path.is_file() or not zipfile.is_zipfile(path):
            reports.append({"path": str(path), "valid": False, "errors": ["file missing or not ZIP-based XLSX"]})
            continue
        try:
            reports.append(inspect(path))
        except (OSError, zipfile.BadZipFile) as exc:
            reports.append({"path": str(path), "valid": False, "errors": [str(exc)]})
    json.dump(reports[0] if len(reports) == 1 else reports, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if all(report.get("valid") for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
