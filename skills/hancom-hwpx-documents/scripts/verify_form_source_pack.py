#!/usr/bin/env python3
"""Read-only pre-write gate for a source-bound, event-specific blank form pack.

See references/form-source-pack.md. This checks declared coverage, paths and
bytes; independent inventory/authority/extraction review cannot be automated.
It never reads or hashes user working finals, copies files, or authorizes edits.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty text required")
    return value


def rows(value, label, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label}: {'nonempty ' if nonempty else ''}list required")
    return value


def indexed(value, key, label, nonempty=False):
    result = {}
    for row in rows(value, label, nonempty):
        if not isinstance(row, dict):
            raise ValueError(f"{label}: object required")
        name = text(row.get(key), f"{label}.{key}")
        if name in result:
            raise ValueError(f"{label}: duplicate {name}")
        result[name] = row
    return result


def absolute(value, label, must_exist=True):
    path = Path(text(value, label))
    if not path.is_absolute():
        raise ValueError(f"{label}: absolute path required")
    resolved = path.resolve(strict=must_exist)
    if must_exist and not resolved.is_file():
        raise ValueError(f"{label}: file required")
    return resolved


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def expected_hash(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise ValueError(f"{label}: SHA-256 required")
    return value.lower()


def aliases(a, b):
    return a == b or (a.exists() and b.exists() and a.samefile(b))


def check_pack(inventory, pack, active_dir):
    """Return issues; invalid/incomplete manifests raise ValueError or OSError."""
    if not isinstance(inventory, dict) or not isinstance(pack, dict):
        raise ValueError('inventory and pack must be objects')
    if any(type(doc.get('schema_version')) is not int or doc['schema_version'] != 1
           for doc in (inventory, pack)):
        raise ValueError('schema_version must be 1')
    root_arg = Path(active_dir)
    if not root_arg.is_absolute():
        raise ValueError('active-dir: absolute event folder required')
    root = root_arg.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('active-dir: directory required')
    for key in ('event_id', 'phase'):
        text(inventory.get(key), key)
        if inventory[key] != pack.get(key):
            raise ValueError(f'{key}: inventory/pack mismatch')
    if inventory.get('mode') not in {'create', 'followup'}:
        raise ValueError('mode must be create or followup')
    finals = [absolute(p, 'existing_finals', False) for p in
              rows(inventory.get('existing_finals'), 'existing_finals')]
    if inventory['mode'] == 'followup' and not finals:
        raise ValueError('followup: list existing working finals before reusing pack')
    sources = indexed(inventory.get('sources'), 'id', 'sources', True)
    requirements = indexed(inventory.get('requirements'), 'id', 'requirements', True)
    copies = indexed(pack.get('sources'), 'source_id', 'pack.sources')
    forms = indexed(pack.get('forms'), 'requirement_id', 'pack.forms')
    issues = []

    def issue(problem, role=None):
        entry = {'problem': problem}
        if role is not None:
            entry['id'] = role
        issues.append(entry)

    def active_file(value, label):
        # Resolve symlinks/junctions before testing the active-folder boundary.
        path = absolute(value, label)
        if not path.is_relative_to(root):
            raise ValueError(f'{label}: outside active event folder')
        if any(aliases(path, final) for final in finals):
            raise ValueError(f'{label}: aliases a protected working final')
        if path.stat().st_size == 0:
            raise ValueError(f'{label}: empty file')
        return path

    original_paths, hashes, copy_paths = {}, {}, {}
    for sid, source in sources.items():
        text(source.get('authority'), f'{sid}.authority')
        path = absolute(source.get('path'), f'{sid}.source')
        if any(aliases(path, final) for final in finals):
            raise ValueError(f'{sid}: working final cannot be official blank source')
        sha = expected_hash(source.get('sha256'), f'{sid}.sha256')
        if not path.stat().st_size or digest(path) != sha:
            issue('official_source_hash_mismatch_or_empty', sid)
        original_paths[sid], hashes[sid] = path, sha
    for sid, copied in copies.items():
        if sid not in sources:
            raise ValueError(f'pack.sources: unknown source {sid}')
        path = active_file(copied.get('path'), f'{sid}.copy')
        original = original_paths[sid]
        # A hardlink to an external original is not an independent retained copy.
        if original != path and aliases(original, path):
            issue('source_copy_is_link_to_original', sid)
        if digest(path) != hashes[sid]:
            issue('active_source_copy_hash_mismatch', sid)
        copy_paths[sid] = path

    required = set()
    for rid, req in requirements.items():
        text(req.get('role'), f'{rid}.role')
        phase = text(req.get('phase'), f'{rid}.phase')
        status = req.get('status')
        if status not in {'required', 'not_applicable', 'later', 'unresolved'}:
            raise ValueError(f'{rid}: invalid applicability status')
        basis = req.get('basis')
        if not isinstance(basis, dict) or basis.get('source_id') not in sources:
            raise ValueError(f'{rid}: independent source-bound applicability basis required')
        for key in ('location', 'reason'):
            text(basis.get(key), f'{rid}.basis.{key}')
        if status == 'unresolved':
            issue('applicability_unresolved', rid)
        if status == 'later' and phase == inventory['phase']:
            issue('current_phase_cannot_be_deferred_as_later', rid)
        if status != 'required':
            continue
        required.add(rid)
        if phase != inventory['phase']:
            issue('required_form_phase_mismatch', rid)
        form = req.get('form')
        if not isinstance(form, dict) or form.get('source_id') not in sources:
            raise ValueError(f'{rid}: official form source required')
        sid = form['source_id']
        location = text(form.get('location'), f'{rid}.form.location')
        if form.get('kind') not in {'standalone', 'embedded'}:
            raise ValueError(f'{rid}: kind must be standalone or embedded')
        if sid not in copy_paths:
            issue('active_official_source_copy_missing', rid)
        if rid not in forms:
            issue('applicable_blank_form_missing', rid)
            continue
        mapped = forms[rid]
        path = active_file(mapped.get('path'), f'{rid}.blank')
        sha = expected_hash(mapped.get('sha256'), f'{rid}.blank.sha256')
        if digest(path) != sha:
            issue('blank_form_hash_mismatch', rid)
        if mapped.get('source_location') != location:
            issue('form_source_coordinates_mismatch', rid)
        if form['kind'] == 'standalone':
            if sha != hashes[sid]:
                issue('standalone_blank_not_source_identical', rid)
        else:
            if sha == hashes[sid] or aliases(path, original_paths[sid]):
                issue('whole_manual_is_not_extracted_form', rid)
            text(mapped.get('extraction_review'), f'{rid}.extraction_review')
    for rid in forms.keys() - required:
        issue('mapped_form_not_currently_required', rid)
    if not required:
        issue('no_current_applicable_forms')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--pack', required=True, type=Path)
    parser.add_argument('--active-dir', required=True, type=Path)
    args = parser.parse_args()
    binding = {}
    try:
        inv_bytes, pack_bytes = args.inventory.read_bytes(), args.pack.read_bytes()
        inventory = json.loads(inv_bytes.decode('utf-8-sig'))
        pack = json.loads(pack_bytes.decode('utf-8-sig'))
        binding = {'inventory_sha256': hashlib.sha256(inv_bytes).hexdigest(),
                   'pack_sha256': hashlib.sha256(pack_bytes).hexdigest(),
                   'active_dir': str(args.active_dir.resolve()),
                   'event_id': inventory.get('event_id') if isinstance(inventory, dict) else None,
                   'phase': inventory.get('phase') if isinstance(inventory, dict) else None}
        issues = check_pack(inventory, pack, args.active_dir)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        issues = [{'problem': 'invalid_or_unreadable_preflight', 'detail': str(error)}]
    result = {'gate': 'FORM_SOURCE_PACK', 'status': 'FAILED' if issues else 'PASSED',
              'issues': issues, 'scope': 'pre-write declared source-pack coverage only',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(), **binding}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
