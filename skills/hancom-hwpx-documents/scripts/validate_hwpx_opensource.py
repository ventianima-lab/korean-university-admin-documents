from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from hwpx import HwpxDocument


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate HWPX with python-hwpx.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--roundtrip-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
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

