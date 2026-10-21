"""Check actual saved run fonts, not merely font-table presence or numeric IDs.

Usage: verify_font_faces.py document.hwpx inventory.json
Inventory: {fonts:[{text, expected_face, expected_occurrences, source,
languages:["hangul","latin"], match:"substring"}]}. Anchors are literal substrings of paragraph
text; every overlapping run must resolve to the expected face in each language.
Populate expectations from the authoritative master, not the generated copy.
This does not verify installed font availability or rendering.
"""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {"p": "http://www.hancom.co.kr/hwpml/2011/paragraph",
      "h": "http://www.hancom.co.kr/hwpml/2011/head"}


def verify(path, inventory):
    if not inventory.get("fonts"):
        raise ValueError("An independent font inventory is required")
    with ZipFile(path) as package:
        header = ET.fromstring(package.read("Contents/header.xml"))
        fonts = {(ff.get("lang").lower(), f.get("id")): f.get("face")
                 for ff in header.findall(".//h:fontface", NS) for f in ff.findall("h:font", NS)}
        properties = {c.get("id"): c for c in header.findall(".//h:charPr", NS)}
        paragraphs = []
        for name in package.namelist():
            if not (name.startswith("Contents/section") and name.endswith(".xml")):
                continue
            root = ET.fromstring(package.read(name))
            for paragraph in root.findall(".//p:p", NS):
                runs = []
                offset = 0
                for run in paragraph.findall("p:run", NS):
                    text = "".join(t.text or "" for t in run.findall("p:t", NS))
                    if text:
                        runs.append((offset, offset + len(text), run.get("charPrIDRef"), text))
                        offset += len(text)
                paragraphs.append(("".join(r[3] for r in runs), runs))
    result = []
    for expected in inventory["fonts"]:
        if not expected.get("text") or not expected.get("source") or expected.get("expected_occurrences", 0) < 1:
            raise ValueError("Anchor, source and positive occurrence count required")
        anchor = expected["text"]
        count = 0
        for text, runs in paragraphs:
            if expected.get("match") == "paragraph" and text != anchor:
                continue
            start = text.find(anchor)
            while start >= 0:
                count += 1
                end = start + len(anchor)
                for left, right, style, _ in runs:
                    if left >= end or right <= start:
                        continue
                    reference = properties[style].find("h:fontRef", NS)
                    for language in expected.get("languages", ["hangul", "latin"]):
                        face = fonts.get((language, reference.get(language)))
                        if face != expected["expected_face"]:
                            raise ValueError(f"Resolved font mismatch for {anchor!r} ({language}): {face!r}")
                start = text.find(anchor, end)
        if count != expected["expected_occurrences"]:
            raise ValueError(f"Anchor occurrence mismatch for {anchor!r}: {count}")
        result.append({"text": anchor, "occurrences": count, "face": expected["expected_face"]})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    print(json.dumps({"ok": True, "checked": verify(args.document, json.loads(args.inventory.read_text(encoding="utf-8-sig")))}, ensure_ascii=False))
