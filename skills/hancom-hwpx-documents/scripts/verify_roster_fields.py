"""Compare planned-roster cells with source headings and independent field values.

The private inventory must cover every grid cell. These checks do not establish
the authenticity of a quoted user instruction or the authority of a source.
"""
import hashlib
import re
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
SECTION = re.compile(r"Contents/section[0-9]+\.xml")
GRADE = re.compile(r"(?:[0-9]+|[일이삼사오육칠팔구십]+)\s*학\s*년")


def _normal(text):
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


def _cell(path, section, table, row, col):
    if (not isinstance(path, str) or not path.strip() or not isinstance(section, str)
            or not SECTION.fullmatch(section)
            or any(type(n) is not int or n < 0 for n in (table, row, col))):
        raise ValueError("invalid roster cell location")
    with ZipFile(path) as package:
        root = ET.fromstring(package.read(section))
    target = list(root.iter(HP + "tbl"))[table]
    for tr in target.findall(HP + "tr"):
        for cell in tr.findall(HP + "tc"):
            addr = cell.find(HP + "cellAddr")
            if addr is not None and int(addr.get("rowAddr")) == row and int(addr.get("colAddr")) == col:
                return "".join("".join(t.itertext()) for t in cell.iter(HP + "t"))
    raise ValueError("roster cell does not exist")


def _instruction(authorization, field):
    if not isinstance(authorization, dict) or authorization.get("kind") != "explicit_user_instruction":
        return False
    quote, reference = authorization.get("quote"), authorization.get("reference")
    return (isinstance(quote, str) and isinstance(reference, str) and quote.strip() and reference.strip()
            and _normal(field) in _normal(quote))


def _user_snapshot(snapshot, saved, expected):
    if not isinstance(snapshot, dict) or snapshot.get("kind") != "user_edited_snapshot":
        return False
    path, digest, reference = (snapshot.get(k) for k in ("path", "sha256", "reference"))
    if (not isinstance(path, str) or not path.strip() or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
            or not isinstance(reference, str) or not reference.strip()):
        return False
    try:
        source = Path(path).resolve()
        if source == saved or hashlib.sha256(source.read_bytes()).hexdigest().lower() != digest.lower():
            return False
        return _cell(path, snapshot.get("section"), snapshot.get("table"),
                     snapshot.get("row"), snapshot.get("col")) == expected
    except (OSError, ValueError, IndexError, TypeError, KeyError, BadZipFile, ET.ParseError):
        return False


def _evidence(evidence, text, saved, snapshot_valid):
    if not isinstance(evidence, dict):
        return False
    if evidence.get("kind") == "user_edited_snapshot":
        return snapshot_valid
    if evidence.get("kind") == "verified_reference":
        reference, location, quote = (evidence.get(k) for k in ("reference", "location", "quote"))
        return (all(isinstance(v, str) and v.strip() for v in (reference, location, quote))
                and text in quote and reference != str(saved))
    if evidence.get("kind") == "source_cell":
        path = evidence.get("path")
        try:
            if not isinstance(path, str) or Path(path).resolve() == saved:
                return False
            return _cell(path, evidence.get("section"), evidence.get("table"),
                         evidence.get("row"), evidence.get("col")) == text
        except (OSError, ValueError, IndexError, TypeError, KeyError, BadZipFile, ET.ParseError):
            return False
    return False


def check_roster_fields(roster):
    """Fail closed when source headings, cells, or authorized additions are unverified."""
    issues = []
    saved = Path(roster["path"]).resolve()
    grid = roster["grid"]

    def issue(problem, row=None, col=None):
        item = {"problem": problem, "path": str(saved)}
        if row is not None:
            item["row"] = row
        if col is not None:
            item["col"] = col
        issues.append(item)

    source_header = roster.get("source_header")
    if not isinstance(source_header, dict) or not isinstance(source_header.get("columns"), list):
        return [{"problem": "planned_roster_source_header_missing", "path": str(saved)}]
    expected_columns = {item["col"] for item in grid["columns"]}
    target_headers = {item["col"]: item["text"] for item in roster["headers"]}
    mapped = {}
    header_additions = {}
    for mapping in source_header["columns"]:
        if (not isinstance(mapping, dict) or type(mapping.get("col")) is not int
                or type(mapping.get("source_col")) is not int
                or not isinstance(mapping.get("text"), str) or not mapping["text"].strip()
                or mapping["col"] in mapped):
            issue("planned_roster_source_header_invalid")
            continue
        try:
            actual = _cell(roster["template_source"], source_header.get("section"),
                           source_header.get("table"), source_header.get("row"), mapping["source_col"])
        except (OSError, ValueError, IndexError, TypeError, KeyError, BadZipFile, ET.ParseError):
            issue("planned_roster_source_header_unverifiable", col=mapping["col"])
            continue
        if actual.strip() != mapping["text"].strip():
            issue("planned_roster_source_header_mismatch", col=mapping["col"])
            continue
        target_header = target_headers.get(mapping["col"], "")
        if _normal(actual) != _normal(target_header):
            auth = mapping.get("header_authorization")
            added = auth.get("field") if isinstance(auth, dict) else None
            allowed = (isinstance(added, str) and added.strip() and _normal(added) in _normal(target_header)
                       and _instruction(auth, added))
            snapshot = _user_snapshot(mapping.get("user_header_snapshot"), saved, target_header)
            if not allowed and not snapshot:
                issue("planned_roster_target_header_not_authorized", col=mapping["col"])
            elif allowed:
                header_additions[mapping["col"]] = _normal(added)
            else:
                header_additions[mapping["col"]] = _normal(target_header)
        mapped[mapping["col"]] = actual
    if set(mapped) != expected_columns:
        issue("planned_roster_source_header_coverage")

    expectations = roster.get("expected_cells")
    if not isinstance(expectations, list):
        return issues + [{"problem": "planned_roster_cell_inventory_missing", "path": str(saved)}]
    expected_coords = {(row, col) for row in range(grid["first_row"], grid["last_row"] + 1)
                       for col in expected_columns}
    seen = set()
    for entry in expectations:
        if (not isinstance(entry, dict) or type(entry.get("row")) is not int
                or type(entry.get("col")) is not int or not isinstance(entry.get("parts"), list)):
            issue("planned_roster_cell_inventory_invalid")
            continue
        row, col = entry["row"], entry["col"]
        coordinate = (row, col)
        if coordinate in seen or coordinate not in expected_coords:
            issue("planned_roster_cell_inventory_invalid", row, col)
            continue
        seen.add(coordinate)
        try:
            actual = _cell(str(saved), roster["section"], roster["table"], row, col)
        except (OSError, ValueError, IndexError, TypeError, KeyError, BadZipFile, ET.ParseError):
            issue("planned_roster_cell_unverifiable", row, col)
            continue
        snapshot_valid = _user_snapshot(entry.get("user_snapshot"), saved, actual)
        if "user_snapshot" in entry and not snapshot_valid:
            issue("planned_roster_user_snapshot_unverifiable", row, col)
        pieces = []
        for part in entry["parts"]:
            if not isinstance(part, dict) or not isinstance(part.get("text"), str) or not part["text"]:
                issue("planned_roster_cell_part_invalid", row, col)
                continue
            text = part["text"]
            pieces.append(text)
            if part.get("kind") == "literal":
                if any(not c.isspace() and unicodedata.category(c)[0] not in "PS" for c in text):
                    issue("planned_roster_literal_contains_data", row, col)
                if not _evidence(part.get("source"), text, saved, snapshot_valid):
                    issue("planned_roster_literal_source_unverified", row, col)
                continue
            field = part.get("field")
            if part.get("kind") != "value" or not isinstance(field, str) or not field.strip():
                issue("planned_roster_cell_part_invalid", row, col)
                continue
            if not _evidence(part.get("source"), text, saved, snapshot_valid):
                issue("planned_roster_value_source_unverified", row, col)
            header = mapped.get(col, "")
            authorized = (_instruction(part.get("authorization"), field)
                          or (_normal(field) in header_additions.get(col, "")))
            if not snapshot_valid and _normal(field) not in _normal(header) and not authorized:
                issue("planned_roster_unrequested_field", row, col)
            if (not snapshot_valid and GRADE.search(text) and "학년" not in _normal(header)
                    and not (_normal(field) == "학년" and authorized)):
                issue("planned_roster_unrequested_field", row, col)
        if "".join(pieces) != actual:
            issue("planned_roster_cell_value_mismatch", row, col)
        if (actual and entry["parts"] and all(p.get("kind") == "literal" for p in entry["parts"]
                                              if isinstance(p, dict))
                and not snapshot_valid and not _instruction(entry.get("literal_authorization"), actual)):
            issue("planned_roster_literal_without_value", row, col)
    if seen != expected_coords:
        issue("planned_roster_cell_inventory_coverage")
    return issues
