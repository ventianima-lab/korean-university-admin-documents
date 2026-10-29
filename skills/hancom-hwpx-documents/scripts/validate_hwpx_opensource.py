from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_section_opening(path: Path) -> dict:
    """Reject late first-paragraph column controls before native layout testing."""
    ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
    hp = "{" + ns["hp"] + "}"
    objects = {hp + name for name in ("tbl", "pic", "rect", "ellipse", "container",
                                      "line", "ole", "textart", "polygon", "curve")}
    checked = 0
    with ZipFile(path) as package:
        for name in package.namelist():
            if not (name.startswith("Contents/section") and name.endswith(".xml")):
                continue
            root = ET.fromstring(package.read(name))
            first = root.find("hp:p", ns)
            if first is None or first.find("hp:run/hp:secPr", ns) is None:
                continue
            object_seen = False
            for run in first.findall("hp:run", ns):
                for child in run:
                    if child.tag == hp + "ctrl" and child.find("hp:colPr", ns) is not None:
                        if object_seen:
                            raise ValueError(f"{name}: SECTION_OPENING_ORDER: column control follows a drawing or table")
                    elif child.tag in objects:
                        object_seen = True
            checked += 1
    return {"status": "PASS", "checked_sections": checked}


def verify_form_fields(path: Path, expectations: dict) -> dict:
    """Check exact table cells and top-level paragraph text, not preview text."""
    fields = expectations.get("fields", [])
    paragraphs = expectations.get("paragraphs", [])
    if not isinstance(fields, list) or not isinstance(paragraphs, list) or not (fields or paragraphs):
        raise ValueError("Expectations must contain at least one field or paragraph")
    ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
    seen = set()
    roots = {}
    checked_tables = 0
    with ZipFile(path) as package:
        for index, field in enumerate(fields):
            section = field["section"]
            key = (section, field["table"], field["row"], field["col"])
            if key in seen or not field.get("source", "").strip():
                raise ValueError(f"Field {index}: duplicate location or missing source/reason")
            seen.add(key)
            if section not in roots:
                roots[section] = ET.fromstring(package.read(section))
            tables = roots[section].findall(".//hp:tbl", ns)
            table_index = field["table"]
            if not isinstance(table_index, int) or not 0 <= table_index < len(tables):
                raise ValueError(f"Field {index}: invalid table location")
            matches = []
            for cell in tables[table_index].findall("./hp:tr/hp:tc", ns):
                address = cell.find("hp:cellAddr", ns)
                if address is not None and (int(address.get("rowAddr")), int(address.get("colAddr"))) == (field["row"], field["col"]):
                    matches.append(cell)
            if len(matches) != 1:
                raise ValueError(f"Field {index}: cell location is not unique")
            actual = "".join("".join(node.itertext()) for node in matches[0].findall(".//hp:t", ns))
            if actual.strip() != field["expected"].strip():
                raise ValueError(f"Field {index}: saved cell differs from expected value")
        seen_paragraphs = set()
        for index, paragraph in enumerate(paragraphs):
            section = paragraph["section"]
            ordinal = paragraph["paragraph"]
            key = (section, ordinal)
            if (type(ordinal) is not int or ordinal < 0 or key in seen_paragraphs
                    or not paragraph.get("source", "").strip()):
                raise ValueError(f"Paragraph {index}: duplicate or invalid location or missing source/reason")
            seen_paragraphs.add(key)
            if section not in roots:
                roots[section] = ET.fromstring(package.read(section))
            top_level = roots[section].findall("./hp:p", ns)
            if ordinal >= len(top_level):
                raise ValueError(f"Paragraph {index}: invalid paragraph location")
            actual = "".join("".join(node.itertext()) for node in top_level[ordinal].findall("./hp:run/hp:t", ns))
            if actual.strip() != paragraph["expected"].strip():
                raise ValueError(f"Paragraph {index}: saved paragraph differs from expected value")
        table_locations = set()
        for index, table in enumerate(expectations.get("tables", [])):
            section = table["section"]
            key = (section, table["table"])
            expected_rows = table["rows"]
            if (key in table_locations or not table.get("source", "").strip()
                    or type(expected_rows) is not int or expected_rows < 1):
                raise ValueError(f"Table {index}: invalid grouping expectation or missing source")
            table_locations.add(key)
            if section not in roots:
                roots[section] = ET.fromstring(package.read(section))
            tables = roots[section].findall(".//hp:tbl", ns)
            ordinal = table["table"]
            if type(ordinal) is not int or not 0 <= ordinal < len(tables):
                raise ValueError(f"Table {index}: invalid table location")
            target = tables[ordinal]
            actual_rows = len(target.findall("hp:tr", ns))
            if actual_rows != expected_rows or int(target.get("rowCnt", actual_rows)) != expected_rows:
                raise ValueError(f"Table {index}: saved row grouping differs from expected structure")
            checked_tables += 1
    return {"status": "PASS", "checked_fields": len(fields),
            "checked_paragraphs": len(paragraphs), "checked_tables": checked_tables}


def emit_report(payload: dict, report: Path | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rendered, encoding="utf-8")
    print(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate HWPX with python-hwpx.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--roundtrip-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--fields", type=Path, help="JSON cell/paragraph expectations with source/reason")
    parser.add_argument("--fields-only", action="store_true",
                        help="Check saved XML text only; does not validate or render the document")
    args = parser.parse_args()
    if args.fields_only and (not args.fields or args.roundtrip_dir):
        parser.error("--fields-only requires --fields and cannot be combined with --roundtrip-dir")
    expectations = json.loads(args.fields.read_text(encoding="utf-8-sig")) if args.fields else None
    if args.fields_only:
        rows = []
        for source in args.inputs:
            source = source.resolve()
            rows.append({"file": str(source), "sha256": sha256(source), "size": source.stat().st_size,
                         "form_fields": verify_form_fields(source, expectations)})
        emit_report({"engine": "hwpx-xml-fields-only",
                     "scope": "Text checks only; document validation and rendering are separate.",
                     "rows": rows}, args.report)
        return

    from hwpx import HwpxDocument

    if args.roundtrip_dir:
        args.roundtrip_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for source in args.inputs:
        source = source.resolve()
        document = HwpxDocument.open(source)
        original_text = document.text.plain()
        row = {
            "file": str(source),
            "sha256": sha256(source),
            "size": source.stat().st_size,
            "validation": str(document.validate()),
            "text_length": len(original_text),
            "table_count": len(document.tables),
            "section_count": len(document.sections),
            "section_opening": verify_section_opening(source),
        }
        if expectations is not None:
            row["form_fields"] = verify_form_fields(source, expectations)
        if args.roundtrip_dir:
            output = args.roundtrip_dir / source.name
            save_report = document.save_to_path(
                output, mode="preserve", fallback="error", return_report=True
            )
            reopened = HwpxDocument.open(output)
            row["roundtrip"] = {
                "path": str(output),
                "sha256": sha256(output),
                "size": output.stat().st_size,
                "save_report": str(save_report),
                "validation": str(reopened.validate()),
                "text_equal": reopened.text.plain() == original_text,
                "section_opening": verify_section_opening(output),
            }
            if expectations is not None:
                row["roundtrip"]["form_fields"] = verify_form_fields(output, expectations)
            reopened.close()
        rows.append(row)
        document.close()

    emit_report({"engine": "python-hwpx", "rows": rows}, args.report)


if __name__ == "__main__":
    main()
