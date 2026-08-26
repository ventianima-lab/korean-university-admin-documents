"""Invalidate stale HWPX line-layout caches without changing document styles."""

from __future__ import annotations

import argparse
import copy
import io
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def local_name(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def register_namespaces(xml_bytes: bytes) -> None:
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(xml_bytes), events=("start-ns",)):
        ET.register_namespace(prefix, uri)


def invalidate_layout(root: ET.Element) -> tuple[int, int]:
    paragraphs = 0
    line_arrays = 0
    for paragraph in (element for element in root.iter() if local_name(element) == "p"):
        removed = False
        for child in list(paragraph):
            if local_name(child) == "linesegarray":
                paragraph.remove(child)
                line_arrays += 1
                removed = True
        if removed:
            paragraphs += 1

    dirty_cells = 0
    for table_cell in (element for element in root.iter() if local_name(element) == "tc"):
        table_cell.set("dirty", "1")
        dirty_cells += 1
    return paragraphs, dirty_cells


def rewrite_package(source: Path, destination: Path) -> tuple[int, int, int]:
    with zipfile.ZipFile(source, "r") as archive:
        members = archive.infolist()
        files = {member.filename: archive.read(member.filename) for member in members}

    section_names = [
        name
        for name in files
        if name.startswith("Contents/section") and name.endswith(".xml")
    ]
    total_paragraphs = 0
    total_cells = 0
    for name in section_names:
        register_namespaces(files[name])
        root = ET.fromstring(files[name])
        paragraphs, cells = invalidate_layout(root)
        total_paragraphs += paragraphs
        total_cells += cells
        files[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w") as output:
        for member in members:
            cloned = copy.copy(member)
            if member.filename == "mimetype":
                cloned.compress_type = zipfile.ZIP_STORED
            output.writestr(cloned, files[member.filename])

    return len(section_names), total_paragraphs, total_cells


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--backup-suffix", default=".pre-reflow.hwpx")
    args = parser.parse_args()

    if args.in_place == (args.output is not None):
        parser.error("choose exactly one of --output or --in-place")

    source = args.input.resolve()
    if args.in_place:
        backup = source.with_name(source.stem + args.backup_suffix)
        shutil.copy2(source, backup)
        with tempfile.NamedTemporaryFile(
            dir=source.parent, suffix=".hwpx", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            counts = rewrite_package(source, temporary)
            temporary.replace(source)
        finally:
            temporary.unlink(missing_ok=True)
        destination = source
        print(f"backup={backup}")
    else:
        destination = args.output.resolve()
        counts = rewrite_package(source, destination)

    print(
        f"output={destination}\nsections={counts[0]}\n"
        f"paragraphs_reflowed={counts[1]}\ncells_marked_dirty={counts[2]}"
    )


if __name__ == "__main__":
    main()

