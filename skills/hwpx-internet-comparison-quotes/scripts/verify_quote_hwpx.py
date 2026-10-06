from __future__ import annotations

import argparse
import json
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


def caption_source(text: str) -> str:
    match = SOURCE_RE.fullmatch(text.split('|')[-1].strip())
    return match.group(1).strip() if match else ''


def check_manifest_group(main_quote, comparisons, main_caption, comparison_captions, spec, comparison_texts):
    """Check declared actual values; a manifest cannot prove screenshot authenticity."""
    issues = []
    if spec.get('item') != main_quote[0]:
        issues.append('명세의 품목명 또는 품목 순서 불일치')
    declared = [spec.get('main', {})] + spec.get('comparisons', [])
    actual = [main_quote] + comparisons
    sources = [caption_source(main_caption)] + [caption_source(s) for s in comparison_captions]
    if len(declared) != len(actual):
        return issues + ['명세의 비교견적 수 불일치']
    for n, (quote, source, expected) in enumerate(zip(actual, sources, declared)):
        expected_values = (spec.get('item'), expected.get('product'), expected.get('quantity'), expected.get('total'))
        if quote != expected_values or source != expected.get('source'):
            issues.append(f'명세와 실제 설명문의 제품·수량·총액·출처 불일치 ({n})')
        if n == 0:
            continue
        if source == sources[0]:
            issues.append(f'비교견적 {n}의 판매처가 본견적과 같음')
        kind = expected.get('kind')
        if kind == 'identical':
            if quote[:3] != main_quote[:3]:
                issues.append(f'동일제품 비교견적 {n}의 품목·제품·수량 불일치')
        elif kind == 'similar':
            differences = expected.get('differences')
            if not expected.get('basis') or not differences:
                issues.append(f'유사제품 비교견적 {n}의 비교 기준 또는 차이가 없음')
            body = comparison_texts[n - 1] if n <= len(comparison_texts) else ''
            if '유사제품' not in body or not differences or differences not in body:
                issues.append(f'유사제품 비교견적 {n}의 실제 차이가 문서에 표시되지 않음')
        else:
            issues.append(f'비교견적 {n}의 kind는 identical 또는 similar여야 함')
        if quote[3] <= main_quote[3] and not (kind == 'similar' and expected.get('allow_lower_price') is True):
            issues.append(f'비교견적 {n}의 낮거나 같은 가격에 대한 명시적 예외가 없음')
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="HWPX 인터넷 비교견적 문서의 핵심 구조를 검사합니다.")
    parser.add_argument("document", type=Path)
    parser.add_argument("--expected-main", type=int, required=True)
    parser.add_argument("--comparisons-per-main", type=int, default=2)
    parser.add_argument('--equivalence-manifest', type=Path, help='명시적으로 허용된 유사제품의 실제 값과 비교 기준 JSON')
    args = parser.parse_args()

    if args.expected_main <= 0 or args.comparisons_per_main < 0:
        print('FAIL: 요청 본견적 수는 양수, 품목당 비교견적 수는 0 이상이어야 함', file=sys.stderr)
        return 2

    issues: list[str] = []
    manifest = None
    if args.equivalence_manifest:
        try:
            manifest = json.loads(args.equivalence_manifest.read_text(encoding='utf-8'))
            if not isinstance(manifest, dict) or not isinstance(manifest.get('authorization'), str) or not manifest['authorization'].strip():
                raise ValueError('유사제품 비교를 허용한 사용자 지시가 없음')
            if not isinstance(manifest.get('items'), list) or len(manifest['items']) != args.expected_main:
                raise ValueError('명세 품목 수가 요청 전체 품목 수와 다름')
            for item in manifest['items']:
                if not isinstance(item, dict) or not isinstance(item.get('main'), dict) or not isinstance(item.get('comparisons'), list) or any(not isinstance(x, dict) for x in item['comparisons']):
                    raise ValueError('명세의 품목·본견적·비교견적 구조 오류')
        except (OSError, ValueError) as error:
            print(f'FAIL: 유사제품 명세 읽기 실패: {error}', file=sys.stderr)
            return 2
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
            section_names = sorted(
                (name for name in names if re.fullmatch(r'Contents/section\d+\.xml', name)),
                key=lambda name: int(re.search(r'section(\d+)\.xml', name).group(1)),
            )
            if 'Contents/section0.xml' not in section_names:
                raise KeyError('Contents/section0.xml')
            roots = [ET.fromstring(archive.read(name)) for name in section_names]
        except (KeyError, ET.ParseError) as error:
            print(f"FAIL: 본문 구역 읽기 실패: {error}", file=sys.stderr)
            return 2

    paragraphs = [paragraph for root in roots for paragraph in root.findall(f".//{{{HP}}}p")]
    captions: list[tuple[bool, str]] = []
    main_positions = []
    all_texts = [paragraph_text(p) for p in paragraphs]
    for index, text in enumerate(all_texts):
        if "|" in text and "총액" in text and "원" in text:
            captions.append((text.startswith("비교견적"), text))
            if not text.startswith('비교견적'):
                main_positions.append(index)

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
        if group_index > len(main_positions):
            issues.append(f'품목 {group_index}의 설명문 위치가 없음')
            continue
        start = main_positions[group_index - 1]
        end = main_positions[group_index] if group_index < len(main_positions) else len(all_texts)
        local_positions = [i for i in range(start, end) if '|' in all_texts[i] and '총액' in all_texts[i] and '원' in all_texts[i]]
        local_captions = [all_texts[i] for i in local_positions]
        numbers = []
        for text in local_captions[1:]:
            number = re.fullmatch(r'비교견적\s*(\d+)', text.split('|')[0].strip())
            numbers.append(int(number.group(1)) if number else None)
        if numbers != list(range(1, args.comparisons_per_main + 1)):
            issues.append(f'품목 {group_index}의 비교견적 번호가 1부터 요구 건수까지 연속되지 않음')
        sources = [caption_source(text) for text in local_captions]
        normalized_sources = [re.sub(r'\s+', '', source).casefold() for source in sources]
        if any(not source for source in sources) or len(set(normalized_sources)) != len(normalized_sources):
            issues.append(f'품목 {group_index}의 판매처가 누락되거나 본견적·비교견적 사이에 중복됨')
        comparison_texts = [
            '\n'.join(all_texts[position:local_positions[index + 1] if index + 1 < len(local_positions) else end])
            for index, position in enumerate(local_positions) if index > 0
        ]
        if manifest is not None:
            if group_index > len(manifest['items']):
                issues.append(f'품목 {group_index}에 대응하는 명세가 없음')
                continue
            group_issues = check_manifest_group(main_quote, comparisons, local_captions[0], local_captions[1:], manifest['items'][group_index - 1], comparison_texts)
            issues.extend(f'품목 {group_index}: {s}' for s in group_issues)
            continue
        for comparison_index, comparison in enumerate(comparisons, start=1):
            item, product, quantity, total = comparison
            if (item, product, quantity) != (main_item, main_product, main_quantity):
                issues.append(f"품목 {group_index} 비교견적 {comparison_index}의 품목·제품·수량이 본견적과 다름")
            if total <= main_total:
                issues.append(
                    f"품목 {group_index} 비교견적 {comparison_index} 총액 {total:,}원이 본견적 {main_total:,}원보다 높지 않음"
                )

    pictures = [picture for root in roots for picture in root.findall(f".//{{{HP}}}pic")]
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
    print(f'- 본문 구역: {len(roots)}개, 비교견적 번호·판매처 중복 검사 통과')
    if manifest is not None:
        print('- 명시적 유사제품 비교 범위와 실제 값 검사 통과 (동일제품 판정 아님)')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
