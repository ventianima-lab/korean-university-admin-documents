"""Verify an explicitly required same-page pair against physical PDF pages and a human review.

The PDF must be exported from the exact final HWPX. This tool cannot prove export
provenance or human visual observations; both are explicit attestations.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot(path):
    with zipfile.ZipFile(path) as z:
        names = sorted((n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)), key=lambda n:int(re.search(r"section(\d+)",n).group(1)))
        if not names: raise ValueError("missing section XML")
        roots = [ET.fromstring(z.read(n)) for n in names]
        ids, texts, protected, cells = [], [], [], []
        for root in roots:
            parents = {child: parent for parent in root.iter() for child in parent}
            for node in root.iter(f"{{{HP}}}t"):
                if not (node.text or "").strip(): continue
                parent = parents.get(node); in_table = False
                while parent is not None:
                    if parent.tag == f"{{{HP}}}tbl": in_table = True; break
                    parent = parents.get(parent)
                texts.append(node.text); protected.append(in_table)
            for cell in root.iter(f"{{{HP}}}tc"):
                cells.append(tuple((t.text or "") for t in cell.iter(f"{{{HP}}}t")))
        mapping = {}
        content = ET.fromstring(z.read("Contents/content.hpf"))
        for el in content.iter():
            if el.tag.endswith("}item") and el.get("id") and el.get("href", "").startswith("BinData/"):
                mapping[el.get("id")] = el.get("href")
        pictures=[]
        for root in roots:
            for pic in root.iter(f"{{{HP}}}pic"):
                pid=pic.get("id"); ids.append(pid)
                refs=[x.get("binaryItemIDRef") for x in pic.iter() if x.get("binaryItemIDRef")]
                if len(refs)!=1 or refs[0] not in mapping: raise ValueError("picture binary reference missing or ambiguous")
                pictures.append((pid, hashlib.sha256(z.read(mapping[refs[0]])).hexdigest()))
        media = Counter(hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith("BinData/") and not n.endswith("/"))
    return ids, texts, protected, cells, pictures, media

def authorized_texts(texts, protected, edits):
    if not isinstance(edits, list): raise ValueError("authorized_text_edits must be an array")
    changes={}
    for edit in edits:
        if not isinstance(edit, dict): raise ValueError("invalid authorized text edit")
        index=edit.get("baseline_index"); before=edit.get("before"); after=edit.get("after"); kind=edit.get("kind")
        if type(index) is not int or index < 0 or index >= len(texts) or index in changes: raise ValueError("invalid or duplicate edit index")
        if edit.get("independently_reviewed") is not True or not isinstance(edit.get("instruction_reference"),str) or not edit["instruction_reference"].strip(): raise ValueError("edit lacks independent review or instruction reference")
        if protected[index] or texts[index] != before: raise ValueError("edit targets protected table text or before mismatch")
        if kind == "remove_duplicate_title":
            if after != "" or not (re.fullmatch(r".+ 비교견적",before) or re.fullmatch(r"비\s*교\s*견\s*적\s*서\s*[12]",before)): raise ValueError("unauthorized title removal")
        elif kind == "prefix_quote_number":
            if not re.fullmatch(r"비교견적 [12] \| "+re.escape(before), after or "") or not before.startswith("판매처:"): raise ValueError("unauthorized seller label change")
        else: raise ValueError("unsupported edit kind")
        changes[index]=after
    return [changes.get(i,text) for i,text in enumerate(texts) if changes.get(i,text) != ""]

def normalized(s): return re.sub(r"\s+", "", s).casefold()

def verify(document, baseline, pdf, manifest, expected_pairs, pdftotext="pdftotext"):
    errors = []
    if expected_pairs < 1: raise ValueError("expected pair count must be positive")
    ids, texts, protected, cells, pictures, media = snapshot(document); oldids, oldtexts, oldprotected, oldcells, oldpictures, oldmedia = snapshot(baseline)
    if len(ids) != expected_pairs*2 or len(oldids) != expected_pairs*2: errors.append("capture count differs from expected")
    if None in ids or len(set(ids)) != len(ids): errors.append("missing or duplicate picture ids")
    if media != oldmedia: errors.append("embedded capture/media content changed")
    if ids != oldids or pictures != oldpictures: errors.append("picture IDs, binary contents or order changed")
    if cells != oldcells: errors.append("protected table cells or their order changed")
    expected_texts = authorized_texts(oldtexts, oldprotected, manifest.get("authorized_text_edits", []))
    if texts != expected_texts: errors.append("saved text differs from baseline and authorized edits")
    for key,path in (("document_sha256",document),("baseline_sha256",baseline),("pdf_sha256",pdf)):
        if manifest.get(key) != sha(path): errors.append(key + " mismatch")
    if manifest.get("pdf_export_from_document_sha256") != sha(document): errors.append("exact-file export provenance not attested")
    if manifest.get("pdf_export_verified") is not True: errors.append("PDF export not visually verified")
    proc=subprocess.run([pdftotext,"-layout",str(pdf),"-"],capture_output=True,check=False)
    if proc.returncode: raise ValueError("pdftotext failed")
    pages=proc.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip(): pages.pop()
    pairs=manifest.get("pairs")
    if not isinstance(pairs,list) or len(pairs)!=expected_pairs: return errors+["expected pair inventory missing"]
    seen=[]; markers=[]; doc_text=normalized(" ".join(texts))
    for index,pair in enumerate(pairs,1):
        if not isinstance(pair,dict): errors.append(f"pair {index}: invalid"); continue
        picids=pair.get("picture_ids"); page=pair.get("page"); m=pair.get("markers")
        if not isinstance(picids,list) or len(picids)!=2 or any(not isinstance(x,str) for x in picids): errors.append(f"pair {index}: two picture IDs required"); continue
        seen.extend(picids)
        if not isinstance(page,int) or isinstance(page,bool) or not 1<=page<=len(pages): errors.append(f"pair {index}: invalid physical page"); continue
        if not isinstance(m,list) or len(m)!=2 or any(not isinstance(x,str) or not normalized(x) for x in m): errors.append(f"pair {index}: two unique markers required"); continue
        for marker in m:
            marker=normalized(marker); markers.append(marker)
            if marker not in doc_text: errors.append(f"pair {index}: marker absent from saved HWPX")
            hits=[i+1 for i,text in enumerate(pages) if marker in normalized(text)]
            if hits != [page]: errors.append(f"pair {index}: marker not unique on declared physical page")
        for check in ("both_pictures_on_page", "labels_match_pictures", "all_details_readable", "no_clipping_or_overlap", "same_item_quotes_1_and_2"):
            if pair.get(check) is not True: errors.append(f"pair {index}: {check} not verified")
    if len(markers)!=len(set(markers)): errors.append("markers are not unique")
    if seen != ids: errors.append("pair picture IDs do not cover saved captures in order")
    return errors

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("document",type=Path); p.add_argument("baseline",type=Path); p.add_argument("pdf",type=Path); p.add_argument("review",type=Path); p.add_argument("--expected-pairs",type=int,required=True); p.add_argument("--pdftotext",default="pdftotext")
    a=p.parse_args()
    try: issues=verify(a.document,a.baseline,a.pdf,json.loads(a.review.read_text(encoding="utf-8-sig")),a.expected_pairs,a.pdftotext)
    except (OSError,ValueError,KeyError,ET.ParseError,zipfile.BadZipFile,UnicodeError) as e: print("FAIL:",e); return 2
    if issues: print("FAIL\n"+"\n".join("- "+x for x in issues)); return 1
    print("PASS: page markers and preservation checks; export provenance and image readability remain human-attested")
    return 0
if __name__ == "__main__": raise SystemExit(main())
