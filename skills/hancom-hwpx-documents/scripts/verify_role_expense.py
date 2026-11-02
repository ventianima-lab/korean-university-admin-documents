"""Check independently evidenced personnel roles, costs and saved letter labels.

This narrow HWPX packet check does not determine institutional applicability,
authenticate cited evidence, or discover omitted people, policies or labels.
"""
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
SECTION = re.compile(r"Contents/section[0-9]+\.xml")
FEE_KINDS = {"instructor_fee", "consulting_fee"}
ROLE_KINDS = {"support", "instructor", "assistant_instructor", "consultant", "participant"}
DOC_KINDS = {"resume", "background_check", "privacy_consent"}
EVIDENCE_KINDS = {"user_instruction", "office_confirmation", "prior_record"}
PAYMENT_EVIDENCE_KINDS = EVIDENCE_KINDS | {"approved_plan", "settlement_record"}
ROLE_TERMS = {
    "support": re.compile(r"측정|지원|보조|협력|도움|돕|support|assist|help", re.I),
    "instructor": re.compile(r"강\s*사(?!\s*료)|특\s*강|강\s*의(?!\s*료)|instructor|lectur", re.I),
    "assistant_instructor": re.compile(r"보조\s*강사|assistant\s+instructor", re.I),
    "consultant": re.compile(r"자\s*문(?!\s*료)|consult", re.I),
    "participant": re.compile(r"참석|참여|외부\s*인사|participant|attendee", re.I),
    "special_lecture": re.compile(r"특\s*강|강\s*의(?!\s*료)|special\s+lecture", re.I),
}


def _proof(value, kinds=None):
    return (isinstance(value, dict)
            and all(isinstance(value.get(k), str) and value[k].strip()
                    for k in ("reference", "location", "quote"))
            and (kinds is None or value.get("kind") in kinds))


def _role_label(label):
    # Check specific roles first. A fee name is not an instructor role.
    for kind in ("assistant_instructor", "instructor", "consultant", "support", "participant"):
        if (ROLE_TERMS[kind].search(label)
                and (kind in {"support", "participant"} or not _negative_role_claim(kind, label))):
            return kind
    return None


def _negative_role_claim(kind, quote):
    """Require a negation tied to the role, not to an unrelated fee clause."""
    term = ROLE_TERMS[kind].pattern
    korean = (rf"(?:{term})\s*(?:은|는|이|가|을|를)?\s*"
              rf"(?:(?:진행|실시|운영|수행|계획)(?:이|을|은|는)?\s*)?"
              rf"(?:하지\s*않|없|아니|아닙|아님|않|무관|제외|없이|안\s*하|미실시)")
    english = rf"(?:\bno\b|\bnot\b|\bwithout\b)\s+(?:(?:a|an|any)\s+)?(?:{term})"
    return bool(re.search(korean, quote, re.I) or re.search(english, quote, re.I))


def _read_label(item):
    path, section = item.get("path"), item.get("section")
    if not isinstance(path, str) or not path.strip() or not isinstance(section, str) or not SECTION.fullmatch(section):
        raise ValueError("saved role label needs an HWPX path and section")
    with ZipFile(path) as package:
        root = ET.fromstring(package.read(section))
    if "paragraph" in item:
        index = item["paragraph"]
        if type(index) is not int or index < 0 or any(k in item for k in ("table", "row", "cell")):
            raise ValueError("invalid saved role paragraph")
        paragraph = root.findall("./" + HP + "p")[index]
        return "".join("".join(t.itertext()) for run in paragraph.findall(HP + "run")
                       for t in run.findall(HP + "t"))
    indexes = [item.get(k) for k in ("table", "row", "cell")]
    if any(type(i) is not int or i < 0 for i in indexes):
        raise ValueError("invalid saved role table location")
    tables = list(root.iter(HP + "tbl"))
    rows = tables[indexes[0]].findall(HP + "tr")
    cell = rows[indexes[1]].findall(HP + "tc")[indexes[2]]
    return "".join("".join(t.itertext()) for t in cell.iter(HP + "t"))


def check_role_expense_review(review, expense_reviews, requirements, artifacts):
    """Return issues for an independently prepared, role-specific private inventory."""
    issues = []

    def issue(problem, group=None, document=None):
        entry = {"problem": problem}
        if group is not None:
            entry["group"] = group
        if document is not None:
            entry["document"] = document
        issues.append(entry)

    if not isinstance(review, dict):
        return [{"problem": "role_expense_review_missing"}]
    if review.get("stage") not in {"planned", "actual"}:
        issue("payment_stage_missing")
    groups, payments = review.get("groups"), review.get("payments")
    if not isinstance(groups, list) or not groups:
        return issues + [{"problem": "role_groups_missing"}]
    if not isinstance(payments, list) or not payments:
        return issues + [{"problem": "payment_inventory_missing"}]

    review_categories = {x.get("category") for x in (expense_reviews or []) if isinstance(x, dict)}
    group_ids = [g.get("id") for g in groups if isinstance(g, dict)]
    valid_ids = [x for x in group_ids if isinstance(x, str) and x.strip()]
    if len(valid_ids) != len(groups) or len(set(valid_ids)) != len(groups):
        return issues + [{"problem": "role_group_ids_invalid"}]

    fees = {}
    for payment in payments:
        if not isinstance(payment, dict):
            issue("payment_invalid")
            continue
        kind, group, amount, category = (payment.get(k) for k in ("kind", "group", "amount", "category"))
        if (kind not in FEE_KINDS | {"other"} or type(amount) is not int or amount < 0
                or not isinstance(category, str) or not category.strip()
                or not _proof(payment.get("evidence"), PAYMENT_EVIDENCE_KINDS)):
            issue("payment_evidence_invalid", group)
            continue
        if kind in FEE_KINDS:
            key = (group, kind)
            if group not in valid_ids or key in fees:
                issue("payment_group_or_kind_invalid", group)
                continue
            fees[key] = amount
        elif group is not None and group not in valid_ids:
            issue("payment_group_or_kind_invalid", group)
        if amount > 0 and category not in review_categories:
            issue("paid_category_not_reviewed", group)

    for group in groups:
        group_id = group["id"]
        for kind in FEE_KINDS:
            if (group_id, kind) not in fees:
                issue("fee_amount_unverified", group_id)
        role = group.get("actual_role")
        actual = role.get("kind") if isinstance(role, dict) else None
        basis = role.get("evidence") if isinstance(role, dict) else None
        if actual not in ROLE_KINDS or not _proof(basis, EVIDENCE_KINDS):
            issue("actual_role_unverified", group_id)
        elif not ROLE_TERMS[actual].search(basis["quote"]):
            issue("actual_role_evidence_inconclusive", group_id)
        elif ((observed := _role_label(basis["quote"])) in {"instructor", "assistant_instructor", "consultant"}
              and observed != actual
              and not (actual == "assistant_instructor" and observed == "instructor")):
            issue("actual_role_evidence_conflicts", group_id)

        labels = group.get("letter_labels")
        if not isinstance(labels, list) or not labels:
            issue("letter_role_label_missing", group_id)
        else:
            for label in labels:
                if not isinstance(label, dict) or not isinstance(label.get("label"), str) or not label["label"].strip():
                    issue("letter_role_label_invalid", group_id)
                    continue
                try:
                    text = _read_label(label)
                except (OSError, ValueError, IndexError, KeyError, TypeError, BadZipFile, ET.ParseError):
                    issue("letter_role_label_unverifiable", group_id)
                    continue
                if label["label"] != text.strip():
                    issue("letter_role_label_changed", group_id)
                    continue
                label_kind = _role_label(label["label"])
                if label_kind is None:
                    issue("letter_role_label_unclassified", group_id)
                elif (actual in ROLE_KINDS and label_kind != "participant" and label_kind != actual
                      and not (actual == "assistant_instructor" and label_kind == "instructor")):
                    issue("letter_role_conflicts_with_evidence", group_id)
                if (_proof(basis, EVIDENCE_KINDS)
                        and basis["kind"] == "prior_record"
                        and basis["reference"] == label["path"]):
                    issue("letter_used_as_its_own_role_evidence", group_id)

        documents = group.get("documents")
        if not isinstance(documents, list) or not documents:
            issue("personnel_documents_not_reviewed", group_id)
            continue
        kinds = [d.get("kind") for d in documents if isinstance(d, dict)]
        if (not {"resume", "background_check"}.issubset(set(kinds))
                or any(k not in DOC_KINDS for k in kinds) or len(set(kinds)) != len(documents)):
            issue("personnel_document_inventory_invalid", group_id)
        for document in documents:
            if not isinstance(document, dict) or document.get("kind") not in DOC_KINDS:
                continue
            doc = document["kind"]
            status = document.get("status")
            if status not in {"required", "not_applicable", "pending"}:
                issue("personnel_status_invalid", group_id, doc)
            elif status == "pending":
                issue("personnel_applicability_pending", group_id, doc)
            fee_checks, role_checks = document.get("fee_conditions"), document.get("role_conditions")
            if not isinstance(fee_checks, list) or not fee_checks:
                issue("personnel_fee_conditions_missing", group_id, doc)
                fee_checks = []
            if not isinstance(role_checks, list) or not role_checks:
                issue("personnel_role_conditions_missing", group_id, doc)
                role_checks = []
            fee_active, role_active = False, False
            seen_fees = set()
            for check in fee_checks:
                if (not isinstance(check, dict) or check.get("kind") not in FEE_KINDS
                        or check.get("effect") not in {"required_if_paid", "no_requirement"}
                        or not _proof(check.get("policy")) or check["kind"] in seen_fees):
                    issue("personnel_fee_condition_invalid", group_id, doc)
                    continue
                seen_fees.add(check["kind"])
                if check["effect"] == "required_if_paid" and fees.get((group_id, check["kind"]), 0) > 0:
                    fee_active = True
            if seen_fees != FEE_KINDS:
                issue("personnel_fee_condition_coverage_incomplete", group_id, doc)
            for check in role_checks:
                if (not isinstance(check, dict) or check.get("kind") not in
                        {"special_lecture", "instructor", "assistant_instructor", "consultant"}
                        or not _proof(check.get("policy")) or check.get("matched") not in {"yes", "no", "unknown"}):
                    issue("personnel_role_condition_invalid", group_id, doc)
                    continue
                match = check["matched"]
                if match == "unknown":
                    issue("personnel_role_condition_pending", group_id, doc)
                    continue
                evidence = check.get("evidence")
                if not _proof(evidence, EVIDENCE_KINDS):
                    issue("personnel_role_condition_evidence_missing", group_id, doc)
                    continue
                quote = evidence["quote"]
                negative = _negative_role_claim(check["kind"], quote)
                if (not ROLE_TERMS[check["kind"]].search(quote)
                        or (match == "no" and not negative)):
                    issue("personnel_role_condition_evidence_inconclusive", group_id, doc)
                    continue
                if match == "yes" and negative:
                    issue("personnel_role_condition_evidence_conflicts", group_id, doc)
                    continue
                if match == "yes":
                    role_active = True
            if status == "required" and not (fee_active or role_active):
                issue("personnel_requirement_unsupported", group_id, doc)
            if status == "not_applicable" and (fee_active or role_active):
                issue("personnel_exclusion_conflicts_with_trigger", group_id, doc)
            req_id = document.get("requirement_id")
            if status == "required" and req_id not in requirements:
                issue("personnel_requirement_unmapped", group_id, doc)
            if (status == "not_applicable" and req_id in requirements
                    and artifacts.get(req_id, {}).get("status") != "not_applicable"):
                request = document.get("user_request")
                if not _proof(request, {"user_instruction"}):
                    issue("personnel_document_in_packet_without_basis", group_id, doc)
    return issues
