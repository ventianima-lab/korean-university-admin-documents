from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
PRICE_RE = re.compile(r"총액\s*([0-9][0-9,]*)\s*원")
QUANTITY_RE = re.compile(r"수량\s*(\d+)\s*([^|\s]+)")
SOURCE_RE = re.compile(r"(?:출처|판매처)\s+(.+)")


def paragraph_text(paragraph: ET.Element) -> str:
    fragments: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{{{HP}}}t" and node.text:
            fragments.append(node.text)
    return " ".join("".join(fragments).split())


def parse_caption(text: str, comparison: bool) -> tuple[str, str, str, int]:
    parts = [part.strip() for part in text.split("|")]
    required = 6 if comparison else 5
    if len(parts) < required:
        raise ValueError(f"설명 항목이 {required}개보다 적음: {text}")
    offset = 1 if comparison else 0
    if comparison and not re.fullmatch(r"비교견적\s*\d+", parts[0]):
        raise ValueError(f"비교견적 번호 형식 오류: {text}")
    item = parts[offset]
    product = parts[offset + 1]
    quantity_match = QUANTITY_RE.fullmatch(parts[offset + 2])
    price_match = PRICE_RE.fullmatch(parts[offset + 3])
    source_match = SOURCE_RE.fullmatch(parts[offset + 4])
    if not quantity_match:
        raise ValueError(f"수량 형식 오류: {text}")
    if not price_match:
        raise ValueError(f"총액 형식 오류: {text}")
    if not source_match:
        raise ValueError(f"출처 형식 오류: {text}")
    quantity = quantity_match.group(1) + quantity_match.group(2)
    total = int(price_match.group(1).replace(",", ""))
    return item, product, quantity, total


def main() -> int:
    parser = argparse.ArgumentParser(description="HWPX 인터넷 비교견적 문서의 핵심 구조를 검사합니다.")
    parser.add_argument("document", type=Path)
    parser.add_argument("--expected-main", type=int, required=True)
    parser.add_argument("--comparisons-per-main", type=int, default=2)
    args = parser.parse_args()

    issues: list[str] = []
    if not args.document.is_file():
        print(f"FAIL: 파일 없음: {args.document}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(args.document, "r") as archive:
        names = archive.namelist()
        if not names or names[0] != "mimetype":
            issues.append("mimetype가 첫 ZIP 항목이 아님")
        elif archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
            issues.append("mimetype가 무압축이 아님")
        try:
            root = ET.fromstring(archive.read("Contents/section0.xml"))
        except (KeyError, ET.ParseError) as error:
            print(f"FAIL: section0.xml 읽기 실패: {error}", file=sys.stderr)
            return 2

    paragraphs = root.findall(f".//{{{HP}}}p")
    captions: list[tuple[bool, str]] = []
    for paragraph in paragraphs:
        text = paragraph_text(paragraph)
        if "|" in text and "총액" in text and "원" in text:
            captions.append((text.startswith("비교견적"), text))

    expected_comparisons = args.expected_main * args.comparisons_per_main
    main_count = sum(not comparison for comparison, _ in captions)
    comparison_count = sum(comparison for comparison, _ in captions)
    if main_count != args.expected_main:
        issues.append(f"본견적 설명문 수 {main_count}, 예상 {args.expected_main}")
    if comparison_count != expected_comparisons:
        issues.append(f"비교견적 설명문 수 {comparison_count}, 예상 {expected_comparisons}")

    groups: list[tuple[tuple[str, str, str, int], list[tuple[str, str, str, int]]]] = []
    current_main: tuple[str, str, str, int] | None = None
    current_comparisons: list[tuple[str, str, str, int]] = []
    for comparison, text in captions:
        try:
            parsed = parse_caption(text, comparison)
        except ValueError as error:
            issues.append(str(error))
            continue
        if not comparison:
            if current_main is not None:
                groups.append((current_main, current_comparisons))
            current_main = parsed
            current_comparisons = []
        elif current_main is None:
            issues.append(f"본견적보다 먼저 나온 비교견적: {text}")
        else:
            current_comparisons.append(parsed)
    if current_main is not None:
        groups.append((current_main, current_comparisons))

    for group_index, (main_quote, comparisons) in enumerate(groups, start=1):
        if len(comparisons) != args.comparisons_per_main:
            issues.append(f"품목 {group_index}의 비교견적 수 {len(comparisons)}, 예상 {args.comparisons_per_main}")
        main_item, main_product, main_quantity, main_total = main_quote
        for comparison_index, comparison in enumerate(comparisons, start=1):
            item, product, quantity, total = comparison
            if (item, product, quantity) != (main_item, main_product, main_quantity):
                issues.append(f"품목 {group_index} 비교견적 {comparison_index}의 품목·제품·수량이 본견적과 다름")
            if total <= main_total:
                issues.append(
                    f"품목 {group_index} 비교견적 {comparison_index} 총액 {total:,}원이 본견적 {main_total:,}원보다 높지 않음"
                )

    pictures = root.findall(f".//{{{HP}}}pic")
    expected_pictures = args.expected_main * (1 + args.comparisons_per_main)
    if len(pictures) != expected_pictures:
        issues.append(f"그림 수 {len(pictures)}, 예상 {expected_pictures}")
    for index, picture in enumerate(pictures, start=1):
        position = picture.find(f"{{{HP}}}pos")
        if position is None or position.get("treatAsChar") != "1" or position.get("flowWithText") != "1":
            issues.append(f"그림 {index}에 글자처럼 취급 또는 본문 흐름 속성이 적용되지 않음")

    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("PASS")
    print(f"- 본견적: {main_count}건")
    print(f"- 비교견적: {comparison_count}건")
    print(f"- 그림: {len(pictures)}개, 모두 글자처럼 취급")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
