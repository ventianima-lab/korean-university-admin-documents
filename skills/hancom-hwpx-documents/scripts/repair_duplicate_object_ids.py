from __future__ import annotations

import argparse
import io
import shutil
import zipfile
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET


OBJECT_TAGS = {
    "tbl", "pic", "fieldBegin", "ole", "equation", "container", "rect", "ellipse",
    "arc", "polygon", "curve", "line", "connectLine", "textart", "video", "chart",
}
REFERENCE_ATTRS = {"beginIDRef", "idRef", "objectIDRef", "subjectIDRef", "targetIDRef"}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def register(data: bytes) -> None:
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(data), events=("start-ns",)):
        if prefix not in {"xml", "xmlns"} and not (prefix or "").startswith("ns"):
            ET.register_namespace(prefix or "", uri)


def duplicate_object_ids(root: ET.Element) -> dict[str, int]:
    values = [n.attrib["id"] for n in root.iter() if local(n.tag) in OBJECT_TAGS and n.attrib.get("id")]
    return {value: count for value, count in Counter(values).items() if count > 1}


def repair(root: ET.Element) -> int:
    used = {
        int(n.attrib["id"])
        for n in root.iter()
        if local(n.tag) in OBJECT_TAGS and n.attrib.get("id", "").isdigit()
    }
    next_id = max(used | {2_000_000_000}) + 1
    seen: set[str] = set()
    changed = 0

    # HWPX references such as fieldEnd/beginIDRef are local to the copied top-level form.
    for top in list(root):
        remap: dict[str, str] = {}
        for node in top.iter():
            if local(node.tag) not in OBJECT_TAGS:
                continue
            old = node.attrib.get("id")
            if not old:
                continue
            if old in seen:
                while next_id in used:
                    next_id += 1
                new = str(next_id)
                next_id += 1
                used.add(int(new))
                node.set("id", new)
                remap[old] = new
                changed += 1
            else:
                seen.add(old)
        if remap:
            for node in top.iter():
                for attr in REFERENCE_ATTRS:
                    value = node.attrib.get(attr)
                    if value in remap:
                        node.set(attr, remap[value])
    return changed


def normalize_object_order(root: ET.Element) -> int:
    changed = 0
    z_order = 0
    field_order = 0
    for node in root.iter():
        if "zOrder" in node.attrib:
            if node.attrib["zOrder"] != str(z_order):
                node.set("zOrder", str(z_order))
                changed += 1
            z_order += 1
        # Hancom uses -1 as a sentinel for formula/non-visual fields.  It is
        # intentionally repeatable and must not be rewritten as a visual order.
        if (
            local(node.tag) == "fieldBegin"
            and "zorder" in node.attrib
            and node.attrib["zorder"].lstrip("-").isdigit()
            and int(node.attrib["zorder"]) >= 0
        ):
            if node.attrib["zorder"] != str(field_order):
                node.set("zorder", str(field_order))
                changed += 1
            field_order += 1
    return changed


def rewrite(path: Path, backup: Path | None) -> None:
    if backup:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    with zipfile.ZipFile(path) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    section = entries["Contents/section0.xml"]
    register(section)
    root = ET.fromstring(section)
    before = duplicate_object_ids(root)
    changed = repair(root)
    order_changed = normalize_object_order(root)
    after = duplicate_object_ids(root)
    if after:
        raise ValueError(f"duplicate object IDs remain: {after}")
    entries["Contents/section0.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    entries.setdefault("Preview/PrvText.txt", b"")
    temp = path.with_suffix(path.suffix + ".repairing")
    with zipfile.ZipFile(temp, "w") as output:
        output.writestr("mimetype", entries["mimetype"], compress_type=zipfile.ZIP_STORED)
        for name, data in entries.items():
            if name != "mimetype":
                output.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(temp) as check:
        if check.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
        for name in ("Contents/header.xml", "Contents/section0.xml", "Contents/content.hpf"):
            ET.fromstring(check.read(name))
    temp.replace(path)
    print({"path": str(path), "duplicates_before": before, "ids_changed": changed, "order_changed": order_changed, "duplicates_after": after})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        backup = args.backup_dir / path.name if args.backup_dir else None
        rewrite(path, backup)


if __name__ == "__main__":
    main()

