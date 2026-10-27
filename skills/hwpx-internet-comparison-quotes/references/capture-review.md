# 캡처 검수 기록

편집 가능한 설명문과 그림 수가 맞아도 검색 목록, 잘린 판매처, 빠진 제품 사진, 미선택 수량을 잡아내지 못한다. 다음 기록은 사람이 실제 원본과 최종 쪽을 확인한 결과를 파일 해시에 묶는 보완 검사이며 OCR 또는 화면 진위 판정기가 아니다. 완료를 위해 값을 일괄 `true`로 채우지 않는다.

비공개 기술 작업 폴더에 JSON을 둔다. `document_sha256`은 최종 HWPX SHA-256, `captures`는 본문 그림 순서와 같은 배열이다. 각 항목은 다음 필드를 가진다.

- `picture_id`: HWPX `hp:pic`의 실제 `id`.
- `source_kind`: `product_detail`, `cart`, `vendor_quote` 중 실제 유형. `search`, `store_list`, `unknown`은 불충분한 증빙으로 실패한다.
- `seller`: 화면·근거에서 읽은 판매처 표시명. 쇼핑몰 이름만으로 실제 입점 판매자가 다르다고 추정하지 않는다.
- `original_file`, `original_sha256`: 원본 캡처 경로와 해시. 경로는 JSON 위치 기준 상대 경로 또는 절대 경로.
- `render_file`, `render_sha256`: 정확한 최종 HWPX의 해당 쪽 이미지 경로와 해시.
- 불리언 확인값: `seller_readable`, `product_photo_visible`, `product_name_readable`, `options_visible`, `quantity_visible`, `total_visible`, `shipping_verified`, `discount_verified`, `pointer_free`, `final_render_readable`.

옵션이 없는 상품, 무료배송, 할인 미적용처럼 조건 자체가 없거나 해당 없는 경우도 실제 화면에서 그 상태를 확인한 후 해당 검증값을 `true`로 기록한다. 단가에 수량을 곱한 작성자 계산은 화면에서 선택 수량의 최종 총액을 확인한 것을 대신하지 않는다. 모호하거나 미확인인 값은 `false`로 두어 실패시킨다. 화면 접근 제한과 원본 누락은 가독성 수정으로 해소되었다고 기록하지 않는다.

그림의 배치·문서 내용·원본·쪽 이미지가 바뀌면 해시와 연결을 다시 확인하고 영향을 받는 시각 검수를 반복한다. 검수 기록을 실제 제출 문서에 추가하거나 별도 납품 PDF로 만들지 않는다.
