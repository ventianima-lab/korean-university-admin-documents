from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_CONTROL_ROOT = Path.cwd()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def norm_department(value: object) -> str:
    """Normalize optional sortable folder prefixes used by department roots."""
    return re.sub(r"^\d+[_\s-]+", "", norm(value))


def terms_for(query: str) -> list[str]:
    return [term for term in re.split(r"[\s,;/|]+", norm(query)) if term]


def contains_terms(haystack: str, terms: list[str], match: str) -> bool:
    if not terms:
        return True
    checks = [term in haystack for term in terms]
    return all(checks) if match == "all" else any(checks)


def read_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def filter_row(row: dict[str, str], args: argparse.Namespace) -> bool:
    department = row.get("possible_department", "") or row.get("detected_department", "")
    checks = (
        (args.year, row.get("possible_year", "") or row.get("detected_year", "")),
        (args.work_type, row.get("possible_work_type", "") or row.get("detected_work_type", "")),
        (args.extension, row.get("extension", "")),
    )
    return (
        (not args.department or norm_department(args.department) in norm_department(department))
        and all(not wanted or norm(wanted) in norm(actual) for wanted, actual in checks)
    )


def excerpt(text: str, terms: list[str], radius: int = 150) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    lower = clean.casefold()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not positions:
        return clean[: radius * 2]
    start = max(0, min(positions) - radius)
    end = min(len(clean), start + radius * 2)
    return clean[start:end]


def metadata_score(row: dict[str, str], query: str, terms: list[str]) -> tuple[int, list[str]]:
    filename = norm(row.get("file_name", ""))
    path = norm(row.get("relative_path", ""))
    classes = norm(" ".join([
        row.get("possible_department", ""), row.get("possible_year", ""),
        row.get("possible_semester", ""), row.get("possible_work_type", ""),
    ]))
    phrase = norm(query)
    score = 0
    evidence: list[str] = []
    if phrase and phrase in filename:
        score += 120
        evidence.append("exact_filename_phrase")
    elif phrase and phrase in path:
        score += 90
        evidence.append("exact_path_phrase")
    filename_hits = sum(term in filename for term in terms)
    path_hits = sum(term in path for term in terms)
    class_hits = sum(term in classes for term in terms)
    if filename_hits:
        score += filename_hits * 25
        evidence.append("filename_match")
    if path_hits:
        score += path_hits * 12
        evidence.append("path_match")
    if class_hits:
        score += class_hits * 5
        evidence.append("classification_match")
    return score, evidence


def discover_content_indexes(control_root: Path) -> list[Path]:
    current = control_root / "01_색인결과" / "운영색인" / "current" / "current_document_index.csv"
    root = control_root / "01_색인결과" / "통합색인"
    paths = [current] if current.exists() else []
    if root.exists():
        paths.extend(p for p in root.rglob("document_index.csv") if "test" not in str(p).casefold() and p.stat().st_size > 100)
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search current department metadata and historical document-content indexes.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    parser.add_argument("--department", default="")
    parser.add_argument("--year", default="")
    parser.add_argument("--work-type", default="")
    parser.add_argument("--extension", default="")
    parser.add_argument("--match", choices=("all", "any"), default="all")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--no-content", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    inventory = args.control_root / "01_색인결과" / "운영색인" / "current" / "current_inventory.csv"
    if not inventory.exists():
        raise SystemExit(f"Current operational index not found: {inventory}")

    query_terms = terms_for(args.query)
    if not query_terms:
        raise SystemExit("Query must contain at least one searchable term.")

    current_by_path: dict[str, dict[str, str]] = {}
    current_by_sha: dict[str, list[dict[str, str]]] = defaultdict(list)
    results: dict[str, dict[str, object]] = {}

    for row in read_rows(inventory):
        current_by_path[norm(row.get("full_path", ""))] = row
        if row.get("sha256"):
            current_by_sha[row["sha256"].casefold()].append(row)
        if not filter_row(row, args):
            continue
        haystack = norm(" ".join([
            row.get("file_name", ""), row.get("relative_path", ""),
            row.get("possible_department", ""), row.get("possible_year", ""),
            row.get("possible_semester", ""), row.get("possible_work_type", ""),
        ]))
        if not contains_terms(haystack, query_terms, args.match):
            continue
        score, evidence = metadata_score(row, args.query, query_terms)
        key = norm(row.get("full_path", ""))
        results[key] = {"row": row, "score": score, "evidence": evidence, "content_excerpt": "", "content_sources": set(), "_content_seen": set()}

    content_indexes = [] if args.no_content else discover_content_indexes(args.control_root)
    for content_path in content_indexes:
        for doc in read_rows(content_path):
            if not filter_row(doc, args):
                continue
            content_haystack = norm(" ".join([
                doc.get("text_preview", ""), doc.get("labels", ""),
                doc.get("relative_path", ""), doc.get("detected_department", ""),
                doc.get("detected_year", ""), doc.get("detected_semester", ""),
                doc.get("detected_work_type", ""),
            ]))
            if not contains_terms(content_haystack, query_terms, args.match):
                continue

            resolved: list[dict[str, str]] = []
            sha = doc.get("sha256", "").casefold()
            if sha and sha in current_by_sha:
                resolved = current_by_sha[sha]
            else:
                live = current_by_path.get(norm(doc.get("full_path", "")))
                if live:
                    resolved = [live]
            for row in resolved:
                if not filter_row(row, args):
                    continue
                key = norm(row.get("full_path", ""))
                item = results.setdefault(key, {"row": row, "score": 0, "evidence": [], "content_excerpt": "", "content_sources": set(), "_content_seen": set()})
                text = doc.get("text_preview", "")
                evidence_key = (sha, norm(text))
                if evidence_key in item["_content_seen"]:
                    item["content_sources"].add(str(content_path))
                    continue
                item["_content_seen"].add(evidence_key)
                phrase_hit = norm(args.query) in norm(text)
                term_hits = sum(term in norm(text) for term in query_terms)
                item["score"] = int(item["score"]) + (70 if phrase_hit else 0) + term_hits * 10
                evidence = item["evidence"]
                if "content_match" not in evidence:
                    evidence.append("content_match")
                if sha:
                    if "sha_resolved_to_current_path" not in evidence:
                        evidence.append("sha_resolved_to_current_path")
                if not item["content_excerpt"] or len(text) > len(str(item["content_excerpt"])):
                    item["content_excerpt"] = excerpt(text, query_terms)
                item["content_sources"].add(str(content_path))

    ranked = sorted(results.values(), key=lambda item: (-int(item["score"]), norm(item["row"].get("full_path", ""))))[: max(args.limit, 0)]
    output_results = []
    for item in ranked:
        row = item["row"]
        path = Path(row.get("full_path", ""))
        output_results.append({
            "score": item["score"],
            "full_path": row.get("full_path", ""),
            "exists": path.exists(),
            "file_name": row.get("file_name", ""),
            "extension": row.get("extension", ""),
            "department": row.get("possible_department", ""),
            "academic_year": row.get("possible_year", ""),
            "semester": row.get("possible_semester", ""),
            "work_type": row.get("possible_work_type", ""),
            "sha256": row.get("sha256", ""),
            "evidence": item["evidence"],
            "content_excerpt": item["content_excerpt"],
            "content_sources": sorted(item["content_sources"]),
        })

    op_mtime = datetime.fromtimestamp(inventory.stat().st_mtime).astimezone()
    newest_content_mtime = max((p.stat().st_mtime for p in content_indexes), default=0)
    content_mtime = datetime.fromtimestamp(newest_content_mtime).astimezone() if newest_content_mtime else None
    payload = {
        "query": args.query,
        "match": args.match,
        "result_count": len(output_results),
        "operational_index": str(inventory),
        "operational_index_updated_at": op_mtime.isoformat(timespec="seconds"),
        "content_index_count": len(content_indexes),
        "content_index_updated_at": content_mtime.isoformat(timespec="seconds") if content_mtime else None,
        "content_index_stale": bool(content_mtime and content_mtime.date() < op_mtime.date()),
        "backend": "operational_csv",
        "results": output_results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"results={len(output_results)} operational={payload['operational_index_updated_at']} content={payload['content_index_updated_at']}")
        for result in output_results:
            print(f"[{result['score']}] {result['full_path']} ({', '.join(result['evidence'])})")


if __name__ == "__main__":
    main()
