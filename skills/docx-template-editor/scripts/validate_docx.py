#!/usr/bin/env python3
"""Validate DOCX package integrity and report review-sensitive structures."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REQUIRED = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relationship_source(rels_name: str) -> str:
    directory, filename = posixpath.split(rels_name)
    if not directory.endswith("_rels") or not filename.endswith(".rels"):
        return ""
    parent = posixpath.dirname(directory)
    source_name = filename[:-5]
    return posixpath.join(parent, source_name) if parent else source_name


def resolve_target(rels_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    source = relationship_source(rels_name)
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def validate(path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
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
                if not target:
                    errors.append(f"empty relationship target in {rels_name}")
                    continue
                resolved = resolve_target(rels_name, target)
                if resolved.startswith("../") or resolved not in name_set:
                    errors.append(f"broken relationship {rels_name} -> {target}")

        document = roots.get("word/document.xml")
        if document is None:
            paragraphs = tables = comments = insertions = deletions = controls = 0
        else:
            paragraphs = len(document.findall(f".//{{{W_NS}}}p"))
            tables = len(document.findall(f".//{{{W_NS}}}tbl"))
            comments = len(document.findall(f".//{{{W_NS}}}commentRangeStart"))
            insertions = len(document.findall(f".//{{{W_NS}}}ins"))
            deletions = len(document.findall(f".//{{{W_NS}}}del"))
            controls = len(document.findall(f".//{{{W_NS}}}sdt"))

        settings = roots.get("word/settings.xml")
        track_revisions = bool(settings is not None and settings.find(f".//{{{W_NS}}}trackRevisions") is not None)
        structural_parts = [
            name for name in names
            if name.startswith("word/") and (
                name.endswith(".rels") or
                posixpath.basename(name) in {
                    "document.xml", "styles.xml", "numbering.xml", "settings.xml",
                    "comments.xml", "footnotes.xml", "endnotes.xml"
                } or name.startswith(("word/header", "word/footer"))
            )
        ]
        fingerprint_source = "\n".join(
            f"{name}:{sha256(archive.read(name))}" for name in sorted(structural_parts)
        ).encode("utf-8")

        if comments and "word/comments.xml" not in name_set:
            errors.append("comment anchors exist but word/comments.xml is missing")
        if (insertions or deletions) and not track_revisions:
            warnings.append("tracked-change elements exist while trackRevisions is not enabled")

        return {
            "path": str(path.resolve()),
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "package_sha256": sha256(path.read_bytes()),
            "structural_fingerprint": sha256(fingerprint_source),
            "parts": len(names),
            "paragraphs": paragraphs,
            "tables": tables,
            "comment_anchors": comments,
            "insertions": insertions,
            "deletions": deletions,
            "content_controls": controls,
            "track_revisions": track_revisions,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="+", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reports = []
    for path in args.documents:
        if not path.is_file():
            reports.append({"path": str(path), "valid": False, "errors": ["file not found"]})
            continue
        if not zipfile.is_zipfile(path):
            reports.append({"path": str(path), "valid": False, "errors": ["not a ZIP-based DOCX"]})
            continue
        try:
            reports.append(validate(path))
        except (OSError, zipfile.BadZipFile) as exc:
            reports.append({"path": str(path), "valid": False, "errors": [str(exc)]})
    payload = reports[0] if len(reports) == 1 else reports
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if all(report.get("valid") for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
