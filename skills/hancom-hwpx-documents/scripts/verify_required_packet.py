#!/usr/bin/env python3
"""Reconcile independently listed document requirements with prepared files.

The JSON input has `requirements` (id, source) and `artifacts` (id, status,
paths, verification). Status is ready, pending, user_action, or not_applicable.
expense_reviews maps each applicable cost category and its independently
transcribed checklist items to requirement roles. For each ready HWPX file,
title_band_checks binds an independently selected official master to each title
area. Optional --advance-source-check compares each transcribed checklist cell
and mapped rows. Applicability, source scope, authenticity, layout and
institutional acceptance still require independent review.
"""
import argparse
import json
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from verify_title_band import check_title_band


def check_advance_sources(reviews):
    """Compare independently classified segments with each selected HWPX cell.

    This checks transcription and mappings, not which source or conditions apply.
    """
    issues = []
    if not isinstance(reviews, list) or not reviews:
        return [{'problem': 'source_review_missing'}]
    for review in reviews:
        category = review.get('category', '')
        items = {item.get('label') for item in review.get('items', []) if isinstance(item, dict)}
        cells = review.get('source_cells')
        if not isinstance(cells, list) or not cells:
            issues.append({'category': category, 'problem': 'source_cells_missing'})
            continue
        if not any(isinstance(c, dict) and c.get('stage') == 'advance' for c in cells):
            issues.append({'category': category, 'problem': 'advance_source_cell_missing'})
        for cell in cells:
            if not isinstance(cell, dict):
                issues.append({'category': category, 'problem': 'invalid_source_cell'})
                continue
            stage = cell.get('stage')
            if stage not in {'advance', 'post'}:
                issues.append({'category': category, 'problem': 'invalid_stage'})
                continue
            if not all(isinstance(cell.get(k), str) and cell[k].strip() for k in
                       ('path', 'section', 'activity_context', 'applicability_basis')):
                issues.append({'category': category, 'problem': 'source_context_missing'})
                continue
            indexes = [cell.get(k) for k in ('table', 'row', 'cell')]
            if any(type(i) is not int or i < 0 for i in indexes):
                issues.append({'category': category, 'problem': 'invalid_source_location'})
                continue
            try:
                with ZipFile(cell['path']) as package:
                    root = ET.fromstring(package.read(cell['section']))
                tables = [e for e in root.iter() if e.tag.endswith('}tbl')]
                rows = [e for e in tables[indexes[0]] if e.tag.endswith('}tr')]
                columns = [e for e in rows[indexes[1]] if e.tag.endswith('}tc')]
                text = ''.join(e.text or '' for e in columns[indexes[2]].iter() if e.tag.endswith('}t'))
            except (OSError, BadZipFile, ET.ParseError, KeyError, IndexError, TypeError) as error:
                issues.append({'category': category, 'problem': 'source_cell_unverifiable', 'detail': str(error)})
                continue
            norm = lambda s: ''.join(s.split())
            normalized = norm(text)
            if ('[시행전]' in normalized and stage != 'advance') or ('[시행후]' in normalized and stage != 'post'):
                issues.append({'category': category, 'problem': 'source_stage_mismatch'})
            segments = cell.get('segments')
            if not isinstance(segments, list) or not segments:
                issues.append({'category': category, 'problem': 'source_segments_missing'})
                continue
            valid = all(isinstance(s, dict) and isinstance(s.get('text'), str) and s['text'].strip()
                        and s.get('kind') in {'context', 'item'} for s in segments)
            if not valid:
                issues.append({'category': category, 'problem': 'source_segment_invalid'})
                continue
            if norm(''.join(s['text'] for s in segments)) != normalized:
                issues.append({'category': category, 'problem': 'source_cell_incomplete_or_changed'})
            required_segments = [s for s in segments if s['kind'] == 'item']
            if not required_segments:
                issues.append({'category': category, 'problem': 'source_items_missing'})
            if stage == 'advance':
                for segment in required_segments:
                    if segment.get('item') not in items:
                        issues.append({'category': category, 'problem': 'source_item_unmapped',
                                       'item': segment.get('item')})
    return issues


HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
SECTION = re.compile(r"Contents/section[0-9]+\.xml")


def _paragraph_text(paragraph):
    return "".join("".join(t.itertext()) for run in paragraph.findall(HP + "run")
                   for t in run.findall(HP + "t"))


def check_attachment_list(check):
    """Compare the covering list with independently inspected packet units.

    A location is one verified document unit, not necessarily one file or page.
    """
    if not isinstance(check, dict):
        return [{"problem": "attachment_check_missing"}]
    letter, paragraphs, entries, actual = (check.get(k) for k in
                                            ("letter", "paragraphs", "entries", "actual_files"))
    if not isinstance(letter, str) or not isinstance(paragraphs, list) or not paragraphs:
        raise ValueError("attachment check needs a letter and attachment paragraphs")
    if not isinstance(entries, list) or not entries or not isinstance(actual, list):
        raise ValueError("attachment check needs entries and actual_files")
    if not all(isinstance(x, str) and x.strip() for x in actual):
        raise ValueError("actual_files must be nonempty paths")
    actual_paths = [Path(x).resolve() for x in actual]
    if len(set(actual_paths)) != len(actual_paths):
        raise ValueError("Duplicate actual attachment file")
    issues = []
    for path in actual_paths:
        if not path.is_file() or path.stat().st_size == 0:
            issues.append({"problem": "actual_attachment_missing", "path": str(path)})
    roles = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Attachment entry must be an object")
        key, title, members = entry.get("id"), entry.get("title"), entry.get("members")
        if (not isinstance(key, str) or not key.strip() or key in roles
                or not isinstance(title, str) or not title.strip() or not isinstance(members, list)
                or not members or entry.get("role") not in {"planned_roster", "other"}):
            raise ValueError("Attachment entry needs a unique id, title and members")
        roles[key] = entry
        if entry.get("role") == "planned_roster" and re.search(r"서명|날인|출석부|사인|signature", title, re.I):
            issues.append({"problem": "planned_roster_listed_as_signature", "entry": key})
    used_paths, used_locations, used_roles = set(), set(), set()
    for key, entry in roles.items():
        for member in entry["members"]:
            if (not isinstance(member, dict) or not isinstance(member.get("path"), str)
                    or not isinstance(member.get("locations"), list) or not member["locations"]
                    or not all(isinstance(x, str) and x.strip() for x in member["locations"])
                    or not isinstance(member.get("evidence"), str) or not member["evidence"].strip()):
                raise ValueError("Each attachment member needs a path, per-unit locations and evidence")
            path = Path(member["path"]).resolve()
            used_paths.add(path)
            if not path.is_file() or path.stat().st_size == 0:
                issues.append({"problem": "listed_attachment_missing", "entry": key})
            for location in member["locations"]:
                loc = (path, location.strip())
                if loc in used_locations:
                    issues.append({"problem": "attachment_unit_counted_twice", "entry": key})
                used_locations.add(loc)
    for path in actual_paths:
        if path not in used_paths:
            issues.append({"problem": "unlisted_actual_attachment", "path": str(path)})
    for path in used_paths:
        if path not in actual_paths:
            issues.append({"problem": "listed_attachment_not_in_packet", "path": str(path)})

    with ZipFile(letter) as package:
        previous = None
        roots = {}
        all_text = ""
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                raise ValueError("Attachment paragraph must be an object")
            part, index, segments = (paragraph.get(k) for k in ("section", "paragraph", "segments"))
            if not isinstance(part, str) or not SECTION.fullmatch(part) or type(index) is not int or index < 0:
                raise ValueError("Invalid attachment paragraph location")
            if previous is not None and (part != previous[0] or index != previous[1] + 1):
                raise ValueError("Attachment paragraphs must be contiguous in one section")
            previous = (part, index)
            if part not in roots:
                roots[part] = ET.fromstring(package.read(part))
            candidates = roots[part].findall("./" + HP + "p")
            if index >= len(candidates):
                raise ValueError("Attachment paragraph location does not exist")
            text = _paragraph_text(candidates[index])
            if (not isinstance(segments, list) or not segments
                    or not all(isinstance(x, dict) and isinstance(x.get("text"), str)
                               and x.get("kind") in {"context", "item"} for x in segments)):
                raise ValueError("Invalid attachment paragraph segments")
            if "".join(x["text"] for x in segments) != text:
                issues.append({"problem": "attachment_paragraph_differs", "paragraph": index})
            all_text += text
            for segment in segments:
                if segment["kind"] == "context":
                    continue
                ids = segment.get("entries")
                if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
                    raise ValueError("Each attachment item needs distinct entry ids")
                if any(key not in roles or key in used_roles for key in ids):
                    raise ValueError("Attachment entry is absent or repeated")
                if (any(roles[key]["role"] == "planned_roster" for key in ids)
                        and re.search(r"서명|날인|출석부|사인|signature", segment["text"], re.I)):
                    issues.append({"problem": "planned_roster_listed_as_signature", "entries": ids})
                matches = re.findall(r"(?<![0-9])([1-9][0-9]*)\s*부", segment["text"])
                if len(matches) != 1 or (len(ids) > 1 and not re.search(r"각\s*[1-9][0-9]*\s*부", segment["text"])):
                    issues.append({"problem": "attachment_count_ambiguous", "entries": ids})
                    continue
                quantity = int(matches[0])
                cursor = 0
                for key in ids:
                    title = roles[key]["title"]
                    at = segment["text"].find(title, cursor)
                    if at < 0:
                        issues.append({"problem": "attachment_title_mismatch", "entry": key})
                    else:
                        cursor = at + len(title)
                    count = sum(len(member["locations"]) for member in roles[key]["members"])
                    if count != quantity:
                        issues.append({"problem": "attachment_count_mismatch", "entry": key,
                                       "listed_count": quantity, "mapped_units": count})
                    used_roles.add(key)
    if set(roles) != used_roles:
        issues.append({"problem": "attachment_entry_unmapped", "entries": sorted(set(roles) - used_roles)})
    for key, mode in (("start_marker", "start"), ("end_marker", "end")):
        marker = check.get(key)
        if not isinstance(marker, str) or not marker.strip():
            raise ValueError("Attachment check needs start and end markers")
        if (mode == "start" and not all_text.lstrip().startswith(marker)
                or mode == "end" and not all_text.rstrip().endswith(marker)):
            issues.append({"problem": "attachment_boundary_mismatch", "boundary": mode})
    return issues


def selected_signature_template(roster):
    """Validate a recorded selection, not the truth or meaning of its quoted evidence."""
    selection = roster.get("user_template_selection")
    if not isinstance(selection, dict) or selection.get("kind") != "explicit_user_instruction":
        return False
    template_id, quote, reference = (selection.get(k) for k in ("template_id", "quote", "reference"))
    location = roster.get("source_location")
    if not all(isinstance(value, str) and value.strip() for value in (template_id, quote, reference, location)):
        return False
    normalize = lambda value: re.sub(r"\s+", "", value).casefold()
    return normalize(template_id) in normalize(quote) and normalize(template_id) in normalize(location)


def check_planned_rosters(rosters, artifacts):
    """Check standalone advance rosters when the user prohibits signature fields."""
    if not isinstance(rosters, list) or not rosters:
        return [{"problem": "planned_roster_check_missing"}]
    ready_paths = {Path(p).resolve() for item in artifacts if item.get("status") == "ready"
                   for p in item.get("paths", [])}
    issues = []
    seen, adapted_paths = set(), set()
    discovered_tables, auxiliary_tables = {}, {}
    for roster in rosters:
        if not isinstance(roster, dict):
            raise ValueError("Planned roster must be an object")
        path, section, table, row, headers = (roster.get(k) for k in
                                              ("path", "section", "table", "header_row", "headers"))
        source = roster.get("template_source")
        grid = roster.get("grid")
        if (not isinstance(path, str) or not isinstance(section, str) or not SECTION.fullmatch(section)
                or type(table) is not int or table < 0 or type(row) is not int or row < 0
                or not isinstance(source, str) or not Path(source).is_file()
                or not isinstance(roster.get("source_location"), str) or not roster["source_location"].strip()
                or not isinstance(headers, list) or not headers or not isinstance(grid, dict)):
            raise ValueError("Planned roster needs saved/source paths, source location and header cells")
        first, last, columns = grid.get("first_row"), grid.get("last_row"), grid.get("columns")
        if (type(first) is not int or type(last) is not int or first < 0 or last < first
                or not isinstance(columns, list) or not columns
                or not all(isinstance(c, dict) and type(c.get("col")) is int and c["col"] >= 0
                           and type(c.get("span")) is int and c["span"] > 0 for c in columns)
                or len({c["col"] for c in columns}) != len(columns)):
            raise ValueError("Planned roster needs independently checked participant grid rows and columns")
        saved = Path(path).resolve()
        coordinate = (saved, section, table)
        if coordinate in seen:
            raise ValueError("Duplicate planned roster table")
        seen.add(coordinate)
        if saved not in ready_paths:
            issues.append({"problem": "planned_roster_not_ready_artifact", "path": str(saved)})
        if roster.get("template_role") == "signature_sheet" and selected_signature_template(roster):
            adapted_paths.add(saved)
        elif roster.get("template_role") != "planned_roster":
            issues.append({"problem": "planned_roster_wrong_source_role", "path": str(saved)})
        auxiliary = roster.get("non_roster_tables", [])
        if not isinstance(auxiliary, list):
            raise ValueError("non_roster_tables must be a list")
        for item in auxiliary:
            if (not isinstance(item, dict) or not isinstance(item.get("section"), str)
                    or not SECTION.fullmatch(item["section"]) or type(item.get("table")) is not int
                    or item["table"] < 0 or not isinstance(item.get("evidence"), str)
                    or not item["evidence"].strip()):
                raise ValueError("Each non-roster table needs coordinates and inspection evidence")
            aux_coord = (saved, item["section"], item["table"])
            if aux_coord in auxiliary_tables:
                raise ValueError("Duplicate non-roster table")
            auxiliary_tables[aux_coord] = item["evidence"]
        try:
            with ZipFile(saved) as package:
                section_names = [name for name in package.namelist() if SECTION.fullmatch(name)]
                roots = {name: ET.fromstring(package.read(name)) for name in section_names}
                all_text = "".join("".join(t.itertext()) for root in roots.values()
                                   for t in root.iter(HP + "t"))
                root = roots[section]
            discovered_tables[saved] = {(saved, name, i) for name, item in roots.items()
                                        for i, _ in enumerate(item.iter(HP + "tbl"))}
            if re.search(r"서\s*명|날\s*인|\(\s*인\s*\)|사\s*인|싸\s*인|signature", all_text, re.I):
                issues.append({"problem": "planned_roster_signature_text", "path": str(saved)})
            tables = list(root.iter(HP + "tbl"))
            target = tables[table]
            cells = []
            for tr in target.findall(HP + "tr"):
                for cell in tr.findall(HP + "tc"):
                    addr = cell.find(HP + "cellAddr")
                    if addr is not None and int(addr.get("rowAddr")) == row:
                        span = cell.find(HP + "cellSpan")
                        cells.append({"col": int(addr.get("colAddr")),
                                      "text": "".join("".join(t.itertext()) for t in cell.iter(HP + "t")).strip(),
                                      "span": int(span.get("colSpan", "1")) if span is not None else 1})
            if not all(isinstance(h, dict) and type(h.get("col")) is int
                       and isinstance(h.get("text"), str) and type(h.get("span")) is int
                       and h["span"] > 0 for h in headers):
                raise ValueError("Invalid expected roster header")
            if cells != headers:
                issues.append({"problem": "planned_roster_header_mismatch", "path": str(saved)})
            for grid_row in range(first, last + 1):
                actual_columns = []
                for tr in target.findall(HP + "tr"):
                    for cell in tr.findall(HP + "tc"):
                        addr = cell.find(HP + "cellAddr")
                        if addr is not None and int(addr.get("rowAddr")) == grid_row:
                            span = cell.find(HP + "cellSpan")
                            actual_columns.append({"col": int(addr.get("colAddr")),
                                                   "span": int(span.get("colSpan", "1")) if span is not None else 1})
                if actual_columns != columns:
                    issues.append({"problem": "planned_roster_grid_mismatch",
                                   "path": str(saved), "row": grid_row})
        except (OSError, BadZipFile, ET.ParseError, KeyError, IndexError, TypeError) as error:
            issues.append({"problem": "planned_roster_unverifiable", "detail": str(error)})
    for saved in adapted_paths:
        actual = discovered_tables.get(saved, set())
        targets = {item for item in seen if item[0] == saved}
        other = {item for item in auxiliary_tables if item[0] == saved}
        for _, section, table in sorted(actual - targets - other):
            issues.append({"problem": "planned_roster_table_unaccounted", "path": str(saved),
                           "section": section, "table": table})
        for _, section, table in sorted((other - actual) | (other & targets)):
            issues.append({"problem": "planned_roster_table_inventory_mismatch", "path": str(saved),
                           "section": section, "table": table})
    return issues


def audit(manifest, advance_source_check=False, attachment_check=False, planned_roster_check=False):
    requirements = manifest.get('requirements')
    artifacts = manifest.get('artifacts')
    if not isinstance(requirements, list) or not requirements or not isinstance(artifacts, list):
        raise ValueError('requirements and artifacts must be lists; requirements cannot be empty')
    required = {}
    for item in requirements:
        key = item.get('id', '').strip()
        if not key or key in required or not item.get('source', '').strip():
            raise ValueError('requirement needs a unique id and source')
        required[key] = item
    found = {}
    for item in artifacts:
        key = item.get('id', '').strip()
        if key not in required or key in found:
            raise ValueError('artifact role is duplicate or absent from requirements')
        state = item.get('status')
        if state not in {'ready', 'pending', 'user_action', 'not_applicable'}:
            raise ValueError('invalid artifact status')
        if not item.get('verification', '').strip():
            raise ValueError('every role needs evidence or a specific outstanding action')
        paths = item.get('paths', [])
        if not isinstance(paths, list) or (state == 'ready' and not paths):
            raise ValueError('ready roles need at least one file path')
        bad = [str(p) for p in paths if not Path(p).is_file() or Path(p).stat().st_size == 0]
        title_issues = []
        checks = item.get('title_band_checks', [])
        if (not isinstance(checks, list) or any(not isinstance(c, dict) or
                not isinstance(c.get('path'), str) or not c['path'].strip() for c in checks)):
            raise ValueError('title_band_checks must be a list of entries with paths')
        for path in paths if state == 'ready' else []:
            candidate = Path(path)
            if candidate.suffix.lower() != '.hwpx' or str(path) in bad:
                continue
            selected = [c for c in checks if Path(c.get('path', '')).resolve() == candidate.resolve()]
            if len(selected) != 1:
                title_issues.append({'path': str(path), 'problem': 'title_band_check_missing_or_duplicate'})
                continue
            check = selected[0]
            if check.get('not_applicable') is True:
                if (not check.get('reason', '').strip() or not check.get('source', '').strip()
                        or not Path(check.get('master', '')).is_file()):
                    title_issues.append({'path': str(path), 'problem': 'no_title_band_needs_master_and_reason'})
                continue
            bands = check.get('bands', [])
            if not isinstance(bands, list) or not bands:
                title_issues.append({'path': str(path), 'problem': 'title_band_locations_missing'})
                continue
            for band in bands:
                try:
                    result = check_title_band(candidate, band)
                    if result['status'] != 'PASS':
                        title_issues.append({'path': str(path), 'problem': 'title_band_modified',
                                             'cells': result['issues']})
                except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError) as error:
                    title_issues.append({'path': str(path), 'problem': 'title_band_unverifiable',
                                         'detail': str(error)})
        found[key] = {'id': key, 'status': state, 'missing_files': bad, 'title_band_issues': title_issues}
    results = []
    for key in required:
        results.append(found.get(key, {'id': key, 'status': 'missing_role', 'missing_files': [], 'title_band_issues': []}))
    expense_issues = []
    reviews = manifest.get('expense_reviews')
    if not isinstance(reviews, list) or not reviews:
        expense_issues.append({'problem': 'expense_category_review_missing'})
    else:
        categories = set()
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError('expense review must be an object')
            category = review.get('category', '').strip()
            source = review.get('source', '').strip()
            items = review.get('items')
            if not category or not source or category in categories or not isinstance(items, list) or not items:
                raise ValueError('expense review needs unique category, source and checklist items')
            categories.add(category)
            labels = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError('expense checklist item must be an object')
                label = item.get('label', '').strip()
                state = item.get('status')
                if not label or label in labels or state not in {'required', 'pending', 'not_applicable'}:
                    raise ValueError('expense checklist item needs unique label and valid status')
                labels.add(label)
                if state == 'pending':
                    expense_issues.append({'category': category, 'item': label, 'problem': 'applicability_pending'})
                elif state == 'not_applicable':
                    if not item.get('reason', '').strip():
                        expense_issues.append({'category': category, 'item': label, 'problem': 'exclusion_reason_missing'})
                elif item.get('requirement_id') not in required:
                    expense_issues.append({'category': category, 'item': label, 'problem': 'required_role_missing'})
                elif found.get(item['requirement_id'], {}).get('status') == 'not_applicable':
                    expense_issues.append({'category': category, 'item': label, 'problem': 'required_role_marked_not_applicable'})
    source_issues = check_advance_sources(reviews) if advance_source_check else []
    attachment_issues = check_attachment_list(manifest.get('attachment_check')) if attachment_check else []
    roster_issues = check_planned_rosters(manifest.get('planned_rosters'), artifacts) if planned_roster_check else []
    if attachment_check and planned_roster_check and not attachment_issues and not roster_issues:
        planned_paths = {Path(m['path']).resolve() for entry in manifest['attachment_check']['entries']
                         if entry['role'] == 'planned_roster' for m in entry['members']}
        roster_paths = {Path(roster['path']).resolve() for roster in manifest['planned_rosters']}
        if planned_paths != roster_paths:
            roster_issues.append({'problem': 'planned_roster_attachment_mapping_mismatch'})
    complete = (not source_issues and not expense_issues and not attachment_issues and not roster_issues
                and all(r['status'] in {'ready', 'not_applicable'} and
                        not r['missing_files'] and not r['title_band_issues'] for r in results))
    result = {'status': 'PASS' if complete else 'INCOMPLETE', 'requirements': results,
              'expense_review_issues': expense_issues, 'source_check_issues': source_issues}
    if attachment_check:
        result['attachment_check_issues'] = attachment_issues
    if planned_roster_check:
        result['planned_roster_issues'] = roster_issues
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--advance-source-check', action='store_true',
                   help='check advance checklist source-cell transcription and mapped rows')
    p.add_argument('--attachment-check', action='store_true',
                   help='reconcile exact covering-list paragraphs, named units and actual packet files')
    p.add_argument('--planned-roster-check', action='store_true',
                   help='check standalone advance rosters have the expected headers and no signature text')
    args = p.parse_args()
    try:
        result = audit(json.loads(args.manifest.read_text(encoding='utf-8-sig')), args.advance_source_check,
                       args.attachment_check, args.planned_roster_check)
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError, IndexError) as error:
        p.exit(2, f'PACKET_INVENTORY_ERROR: {error}\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
