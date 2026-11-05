"""Read-only check of saved HWPX costing factors against independent role counts.

JSON: items[{roles:{role:count}, source, unit_price, servings, amount,
bindings:[{path, section, table, row, col, paragraph}]}]. Indexes are zero-based;
row/col use cellAddr. Populate roles from evidence, never from draft factors.
Checks arithmetic and persisted factors, not policy eligibility or actual attendance.
With --role-summary, JSON: {roles:{role:count}, total, text, source} checks that a
user-facing confirmation explicitly shows each role count and the approved total.
When named_people is supplied, role-summary uses total as its approved total;
approved_total may be included only when it agrees with total. Costing items use
their own approved_total field.
With --carry-forward-check, JSON stages prior_authorized, prior_actual and
current_planned each contain source_total:{amount,source}, rows:[{id,amount,
basis,source,bindings:[...]}], and total_bindings:[...]. Bindings locate saved
HWPX paragraphs. Optional future_evidence_blanks:[{path,section,table,row,col,
paragraph,reason}] verifies deliberately blank unsupported evidence separately.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {"h": "http://www.hancom.co.kr/hwpml/2011/paragraph"}

STAGE_BASIS = {
    "prior_authorized": {"approved_budget"},
    "prior_actual": {"receipt", "settlement_record"},
    "current_planned": {"approved_plan"},
}


def _bound_paragraph(binding):
    with ZipFile(binding["path"]) as package:
        root = ET.fromstring(package.read(binding.get("section", "Contents/section0.xml")))
    table = root.findall(".//h:tbl", NS)[binding["table"]]
    cells = [c for c in table.findall("h:tr/h:tc", NS)
             if (int(c.find("h:cellAddr", NS).get("rowAddr")),
                 int(c.find("h:cellAddr", NS).get("colAddr"))) ==
             (binding["row"], binding["col"])]
    if len(cells) != 1:
        raise ValueError("Bound cell not unique")
    return cells[0].findall("h:subList/h:p", NS)[binding["paragraph"]]


def _bound_text(binding):
    para = _bound_paragraph(binding)
    return "".join(t.text or "" for t in para.findall(".//h:t", NS))


def _parse_amount(text, context):
    normalized = re.sub(r"\s+", "", text)
    match = re.fullmatch(r"((?:\d+|\d{1,3}(?:,\d{3})+))원?", normalized)
    if not match:
        raise ValueError(f"{context} must contain only one monetary amount: {text}")
    digits = match.group(1)
    ungrouped = digits.replace(",", "")
    if len(ungrouped) == 8 and "," not in digits:
        try:
            parsed = datetime.strptime(ungrouped, "%Y%m%d")
        except ValueError:
            parsed = None
        if parsed is not None and parsed.strftime("%Y%m%d") == ungrouped:
            raise ValueError(f"{context} looks like a date, not an amount: {text}")
    return int(ungrouped)


def _saved_amount(binding):
    paragraph = _bound_paragraph(binding)
    text = "".join(t.text or "" for t in paragraph.findall(".//h:t", NS))
    visible = _parse_amount(text, "Saved financial field")
    for field in paragraph.findall(".//h:fieldBegin", NS):
        if field.get("type", "").upper() != "FORMULA":
            continue
        params = {node.get("name"): "".join(node.itertext())
                  for node in field.iter() if node.get("name")}
        last_result = params.get("LastResult")
        if last_result is not None:
            cached = _parse_amount(last_result, "FORMULA LastResult")
            if cached != visible:
                raise ValueError(f"Visible amount {visible} disagrees with FORMULA LastResult {cached}")
        command = params.get("Command", "")
        if ";;" in command:
            suffix = command.rsplit(";;", 1)[1]
            try:
                cached = _parse_amount(suffix, "FORMULA Command cached result")
            except ValueError:
                cached = None  # Only compare a recognized numeric result suffix.
            if cached is not None and cached != visible:
                raise ValueError(f"Visible amount {visible} disagrees with FORMULA Command cached result {cached}")
    return visible, text


def verify_carry_forward(spec):
    """Reconcile independently sourced historical and planned financial stages."""
    stages = spec.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGE_BASIS):
        raise ValueError("All three financial stages are required: prior_authorized, prior_actual, current_planned")
    checked = {}
    for stage, required_basis in STAGE_BASIS.items():
        entry = stages[stage]
        source_total = entry.get("source_total")
        rows = entry.get("rows")
        if not isinstance(source_total, dict) or not source_total.get("source"):
            raise ValueError(f"Independent source total required for {stage}")
        total = source_total.get("amount")
        if type(total) is not int or total < 0:
            raise ValueError(f"Source total must be a nonnegative integer for {stage}")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"Source-backed financial rows required for {stage}")
        row_ids = set()
        row_sum = 0
        for row in rows:
            row_id = row.get("id")
            amount = row.get("amount")
            if not isinstance(row_id, str) or not row_id.strip() or row_id in row_ids:
                raise ValueError(f"Financial row IDs must be unique and nonempty for {stage}")
            row_ids.add(row_id)
            if type(amount) is not int or amount < 0 or not row.get("source"):
                raise ValueError(f"Each financial row needs a nonnegative amount and independent source for {stage}")
            if row.get("basis") not in required_basis:
                raise ValueError(f"Wrong financial basis for {stage}: expected one of {sorted(required_basis)}")
            bindings = row.get("bindings")
            if not isinstance(bindings, list) or not bindings:
                raise ValueError(f"Saved row bindings are required for {stage}/{row_id}")
            row_sum += amount
            for binding in bindings:
                saved, text = _saved_amount(binding)
                if saved != amount:
                    raise ValueError(f"Saved {stage}/{row_id} amount {saved} disagrees with source amount {amount}: {text}")
        if row_sum != total:
            raise ValueError(f"{stage} source rows sum to {row_sum}, not independently stated total {total}")
        total_bindings = entry.get("total_bindings")
        if not isinstance(total_bindings, list) or not total_bindings:
            raise ValueError(f"Saved total bindings are required for {stage}")
        for binding in total_bindings:
            saved, text = _saved_amount(binding)
            if saved != total:
                raise ValueError(f"Saved {stage} total {saved} disagrees with source total {total}: {text}")
        checked[stage] = {"row_count": len(rows), "total": total,
                          "saved_rows": sum(len(row["bindings"]) for row in rows),
                          "saved_totals": len(total_bindings)}

    blank_count = 0
    for binding in spec.get("future_evidence_blanks", []):
        if not binding.get("reason"):
            raise ValueError("Each future evidence blank needs a source-based reason")
        text = _bound_text(binding)
        if text.strip():
            raise ValueError(f"Unsupported future evidence field must remain blank: {text}")
        blank_count += 1
    return {"stages": checked, "future_evidence_blanks": blank_count}


def verify_role_summary(spec):
    """Check the independently sourced roles appear in the confirmation itself."""
    roles = spec.get("roles")
    summary = spec.get("text")
    total = spec.get("total")
    if not isinstance(roles, dict) or not roles or not isinstance(summary, str) or not spec.get("source"):
        raise ValueError("Confirmation text, independent role counts and source are required")
    if type(total) is not int or total <= 0:
        raise ValueError("A positive total count is required")
    if "approved_total" in spec and spec["approved_total"] != total:
        raise ValueError("approved_total disagrees with role-summary total")
    _verify_named_people(roles, spec.get("named_people"), total,
                         spec.get("people_source"), required=False)
    for role, count in roles.items():
        if not isinstance(role, str) or not role or type(count) is not int or count <= 0:
            raise ValueError("Role labels and counts must be explicit and positive")
        pattern = re.escape(role) + r"\s*[:：]?\s*" + str(count) + r"\s*명"
        if not re.search(pattern, summary):
            raise ValueError(f"Role or count missing from confirmation: {role}")
    if sum(roles.values()) != total:
        raise ValueError("Role counts do not sum to the stated total")
    if not re.search(r"(?<!\d)" + str(total) + r"\s*명", summary):
        raise ValueError("Total count missing from confirmation")
    return {"total": total, "roles": roles}


def _verify_named_people(roles, people, approved_total, people_source, required=True):
    """Ground role counts in a distinct named inventory when one is supplied."""
    if people is None:
        if required:
            raise ValueError("Independent named_people inventory is required")
        return None
    if not isinstance(people, list) or not people or not people_source:
        raise ValueError("Named people and their independent source are required")
    names = []
    grouped = {}
    for person in people:
        if not isinstance(person, dict):
            raise ValueError("Each named person must have name and role")
        name, role = person.get("name"), person.get("role")
        if not isinstance(name, str) or not name.strip() or not isinstance(role, str) or not role.strip():
            raise ValueError("Each named person must have a nonempty name and role")
        name = name.strip()
        if name in names:
            raise ValueError(f"Duplicate name in named_people: {name}")
        names.append(name)
        grouped[role] = grouped.get(role, 0) + 1
    if type(approved_total) is not int or approved_total <= 0 or len(names) != approved_total:
        raise ValueError("Named roster count disagrees with independently approved total")
    if grouped != roles:
        raise ValueError("Named roster role grouping disagrees with independent role counts")
    return {"total": len(names), "roles": grouped}

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
        _verify_named_people(item["roles"], item.get("named_people"),
                             item.get("approved_total"), item.get("people_source"), required=False)
        if item.get("named_people") is not None and item["approved_total"] != count:
            raise ValueError("Independent approved total disagrees with costing role count")
        factors = (count, item["unit_price"], item["servings"])
        if min(factors) <= 0 or count * item["unit_price"] * item["servings"] != item["amount"]:
            raise ValueError("Role-based costing amount mismatch")
        for binding in item["bindings"]:
            text = _bound_text(binding)
            normalized = re.sub(r"[\s,]", "", text)
            matches = re.findall(r"(\d+)명[×xX*](\d+)원[×xX*](\d+)회", normalized)
            if len(matches) != 1 or tuple(map(int, matches[0])) != factors:
                raise ValueError(f"Saved factors disagree with independent roles: {text}")
            result.append({"path": binding["path"], "factors": factors, "amount": item["amount"]})
    return result




def verify_uniform_divisibility(spec):
    """Check a source-backed total against a uniform whole-won unit cost.

    A divisible total does not itself establish a price. Return an unresolved
    status unless an independently supported unit price is also supplied.
    """
    trusted = {'user_confirmed', 'verified_fact', 'verified_calculation'}
    if not isinstance(spec, dict) or set(spec) - {'total','quantity','quantity_unit','frequency','unit_price'}:
        raise ValueError('Uniform costing cannot accept invented or extra components')
    def field(name, expected_unit, optional=False):
        entry = spec.get(name)
        if entry is None and optional:
            return None
        if (not isinstance(entry, dict) or set(entry) != {'value','unit','provenance','source'} or type(entry.get('value')) is not int or
                entry['value'] <= 0 or entry.get('unit') != expected_unit or
                entry.get('provenance') not in trusted or
                not isinstance(entry.get('source'), str) or not entry['source'].strip()):
            raise ValueError('Independent source, trusted provenance, positive integer and exact unit are required for ' + name)
        return entry['value']
    total = field('total', '원')
    quantity = field('quantity', spec.get('quantity_unit'))
    if not isinstance(spec.get('quantity_unit'), str) or not spec['quantity_unit'].strip() or spec['quantity_unit'] in ('원', '회', '회차'):
        raise ValueError('A distinct non-session quantity unit is required')
    frequency = field('frequency', '회')
    price = field('unit_price', '원', optional=True)
    units = quantity * frequency
    remainder = total % units
    if remainder:
        result = {'status':'UNRESOLVED', 'reason':'non_integer_won_unit_price',
                  'units':units, 'remainder':remainder}
        if price is not None:
            result['source_price_total'] = price * units
            result['target_difference'] = total - price * units
        return result
    if price is None:
        return {'status':'UNRESOLVED', 'reason':'unit_price_source_needed',
                'units':units, 'remainder':0}
    if price * units != total:
        return {'status':'UNRESOLVED', 'reason':'source_unit_price_disagrees',
                'units':units, 'remainder':0, 'source_price_total':price * units,
                'target_difference':total - price * units}
    return {'status':'PASS', 'units':units, 'remainder':0,
            'scope':'integer arithmetic only; source authority, budget eligibility and approval require independent review'}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--role-summary", action="store_true", help="Check a user-facing role/count confirmation before asking")
    modes.add_argument("--carry-forward-check", action="store_true", help="Reconcile prior finance and current planned amounts with saved fields")
    modes.add_argument("--unit-divisibility-check", action="store_true", help="Check source-backed total and whole-won uniform unit cost without inventing items")
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8-sig"))
    checked = (verify_role_summary(inventory) if args.role_summary else
               verify_carry_forward(inventory) if args.carry_forward_check else
               verify_uniform_divisibility(inventory) if args.unit_divisibility_check else verify(inventory))
    ok = not args.unit_divisibility_check or checked['status'] == 'PASS'
    print(json.dumps({"ok": ok, "checked": checked}, ensure_ascii=False))
    if not ok:
        raise SystemExit(1)
