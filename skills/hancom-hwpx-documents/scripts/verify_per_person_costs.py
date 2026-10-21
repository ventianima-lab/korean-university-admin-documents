"""Read-only check of saved HWPX costing factors against independent role counts.

JSON: items[{roles:{role:count}, source, unit_price, servings, amount,
bindings:[{path, section, table, row, col, paragraph}]}]. Indexes are zero-based;
row/col use cellAddr. Populate roles from evidence, never from draft factors.
Checks arithmetic and persisted factors, not policy eligibility or actual attendance.
"""
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {"h": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


def verify(spec):
    if not spec.get("items"):
        raise ValueError("No independent costing items")
    result = []
    for item in spec["items"]:
        if not item.get("source") or not item.get("roles") or not item.get("bindings"):
            raise ValueError("Source, role breakdown and saved bindings are required")
        values = [*item["roles"].values(), item["unit_price"], item["servings"], item["amount"]]
        if any(type(v) is not int or v < 0 for v in values):
            raise ValueError("Counts and amounts must be nonnegative integers")
        count = sum(item["roles"].values())
        factors = (count, item["unit_price"], item["servings"])
        if min(factors) <= 0 or count * item["unit_price"] * item["servings"] != item["amount"]:
            raise ValueError("Role-based costing amount mismatch")
        for binding in item["bindings"]:
            with ZipFile(binding["path"]) as package:
                root = ET.fromstring(package.read(binding.get("section", "Contents/section0.xml")))
            table = root.findall(".//h:tbl", NS)[binding["table"]]
            cells = [c for c in table.findall("h:tr/h:tc", NS)
                     if (int(c.find("h:cellAddr", NS).get("rowAddr")),
                         int(c.find("h:cellAddr", NS).get("colAddr"))) ==
                     (binding["row"], binding["col"])]
            if len(cells) != 1:
                raise ValueError("Costing cell not unique")
            para = cells[0].findall("h:subList/h:p", NS)[binding["paragraph"]]
            text = "".join(t.text or "" for t in para.findall(".//h:t", NS))
            normalized = re.sub(r"[\s,]", "", text)
            matches = re.findall(r"(\d+)명[×xX*](\d+)원[×xX*](\d+)회", normalized)
            if len(matches) != 1 or tuple(map(int, matches[0])) != factors:
                raise ValueError(f"Saved factors disagree with independent roles: {text}")
            result.append({"path": binding["path"], "factors": factors, "amount": item["amount"]})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    print(json.dumps({"ok": True, "checked": verify(json.loads(args.inventory.read_text(encoding="utf-8-sig")))}, ensure_ascii=False))
