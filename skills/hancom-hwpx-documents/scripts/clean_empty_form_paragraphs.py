from __future__ import annotations

import argparse
import copy
import io
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":", 1)[-1]


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter() if local_name(node.tag) == "t")


def remove_empty_paragraphs(
    section_xml: bytes,
    anchors: list[str],
    remove_empty_before: list[str],
) -> tuple[bytes, list[dict[str, object]]]:
    for _event, namespace in ET.iterparse(io.BytesIO(section_xml), events=("start-ns",)):
        prefix, uri = namespace
        ET.register_namespace(prefix or "", uri)
    root = ET.fromstring(section_xml)
    parent_map = {child: parent for parent in root.iter() for child in parent}
    reports: list[dict[str, object]] = []

    for cell_index, cell in enumerate(node for node in root.iter() if local_name(node.tag) == "tc"):
        cell_text = text_of(cell)
        matched = [anchor for anchor in anchors if anchor in cell_text]
        if not matched:
            continue

        paragraphs = [node for node in cell.iter() if local_name(node.tag) == "p"]
        nonempty_count = sum(bool(text_of(p).strip()) for p in paragraphs)
        removed = 0

        if nonempty_count:
            for paragraph in paragraphs:
                if text_of(paragraph).strip():
                    continue
                parent = parent_map.get(paragraph)
                if parent is not None:
                    parent.remove(paragraph)
                    removed += 1

        for paragraph in [node for node in cell.iter() if local_name(node.tag) == "p"]:
            for child in list(paragraph):
                if local_name(child.tag) == "linesegarray":
                    paragraph.remove(child)

        if "dirty" in cell.attrib:
            cell.set("dirty", "1")

        reports.append(
            {
                "cell_index": cell_index,
                "anchors": matched,
                "removed_empty_paragraphs": removed,
                "dirty_attribute_present": "dirty" in cell.attrib,
            }
        )

    for anchor in remove_empty_before:
        target = next(
            (node for node in root.iter() if local_name(node.tag) == "p" and anchor in text_of(node)),
            None,
        )
        removed = 0
        if target is not None:
            parent = parent_map.get(target)
            if parent is not None:
                siblings = list(parent)
                index = siblings.index(target)
                if index > 0:
                    previous = siblings[index - 1]
                    if local_name(previous.tag) == "p" and not text_of(previous).strip():
                        parent.remove(previous)
                        removed = 1
        reports.append(
            {
                "top_level_anchor": anchor,
                "removed_empty_paragraph_before": removed,
            }
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), reports


def rewrite_hwpx(
    source: Path,
    output: Path,
    anchors: list[str],
    remove_empty_before: list[str],
) -> list[dict[str, object]]:
    if output.exists():
        raise FileExistsError(output)

    with zipfile.ZipFile(source, "r") as src:
        names = src.namelist()
        if not names or names[0] != "mimetype":
            raise ValueError("mimetype is not the first ZIP entry")
        section_name = "Contents/section0.xml"
        if section_name not in names:
            raise ValueError(f"missing {section_name}")

        updated_section, reports = remove_empty_paragraphs(
            src.read(section_name), anchors, remove_empty_before
        )

        with zipfile.ZipFile(output, "w") as dst:
            for info in src.infolist():
                data = updated_section if info.filename == section_name else src.read(info.filename)
                cloned = copy.copy(info)
                dst.writestr(cloned, data)

    with zipfile.ZipFile(output, "r") as check:
        first = check.infolist()[0]
        if first.filename != "mimetype" or first.compress_type != zipfile.ZIP_STORED:
            raise ValueError("output mimetype entry is not first and uncompressed")
        ET.fromstring(check.read("Contents/section0.xml"))

    return reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--anchor", action="append", required=True)
    parser.add_argument("--remove-empty-before", action="append", default=[])
    args = parser.parse_args()

    reports = rewrite_hwpx(
        args.source, args.output, args.anchor, args.remove_empty_before
    )
    for report in reports:
        print(report)
    if not reports:
        print("No anchor cells matched", file=sys.stderr)
        return 2
    cell_reports = [report for report in reports if "removed_empty_paragraphs" in report]
    if any(int(report["removed_empty_paragraphs"]) == 0 for report in cell_reports):
        print("At least one matched cell had no empty paragraph to remove", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

