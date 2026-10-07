from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from hwpx import HwpxDocument


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_form_fields(path: Path, expectations: dict) -> dict:
    """Check values at exact cells; an occurrence elsewhere is insufficient."""
    fields = expectations.get("fields", [])
    if not fields:
        raise ValueError("Field expectations must contain at least one field")
    ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
    seen = set()
    roots = {}
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
            actual = "".join(node.text or "" for node in matches[0].findall(".//hp:t", ns))
            if actual.strip() != field["expected"].strip():
                raise ValueError(f"Field {index}: saved cell differs from expected value")
    return {"status": "PASS", "checked_fields": len(fields)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate HWPX with python-hwpx.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--roundtrip-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--fields", type=Path, help="JSON exact-cell expectations with source/reason")
    args = parser.parse_args()
    expectations = json.loads(args.fields.read_text(encoding="utf-8-sig")) if args.fields else None
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
            }
            if expectations is not None:
                row["roundtrip"]["form_fields"] = verify_form_fields(output, expectations)
            reopened.close()
        rows.append(row)
        document.close()

    payload = {"engine": "python-hwpx", "rows": rows}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
