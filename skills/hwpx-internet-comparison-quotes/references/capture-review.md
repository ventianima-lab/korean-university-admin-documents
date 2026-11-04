# 캡처 검수 기록

편집 가능한 설명문과 그림 수가 맞아도 검색 목록, 잘린 판매처, 빠진 제품 사진, 미선택 수량을 잡아내지 못한다. 다음 기록은 사람이 실제 원본과 최종 쪽을 확인한 결과를 파일 해시에 묶는 보완 검사이며 OCR 또는 화면 진위 판정기가 아니다. 완료를 위해 값을 일괄 `true`로 채우지 않는다.

비공개 기술 작업 폴더에 JSON을 둔다. `document_sha256`은 최종 HWPX SHA-256, `captures`는 본문 그림 순서와 같은 배열이다. 각 항목은 다음 필드를 가진다.

- `picture_id`: HWPX `hp:pic`의 실제 `id`.
- `source_kind`: `product_detail`, `cart`, `vendor_quote` 중 실제 유형. `search`, `store_list`, `unknown`은 불충분한 증빙으로 실패한다.
- `seller`: 화면·근거에서 읽은 판매처 표시명. `seller_identity`는 별도로 확인한 실제 거래업체 상호이다. 쇼핑몰 이름만으로 실제 입점 판매자가 다르다고 추정하지 않는다.
- `original_file`, `original_sha256`: 원본 캡처 경로와 해시. 경로는 JSON 위치 기준 상대 경로 또는 절대 경로.
- `render_file`, `render_sha256`: 정확한 최종 HWPX의 해당 쪽 이미지 경로와 해시.
- 불리언 확인값: `seller_and_total_same_capture`, `only_quoted_product_visible`, `seller_readable`, `seller_identity_verified`, `product_photo_visible`, `product_name_readable`, `options_visible`, `quantity_visible`, `total_visible`, `shipping_verified`, `discount_verified`, `pointer_free`, `unrelated_page_chrome_excluded`, `final_render_readable`.

옵션이 없는 상품, 무료배송, 할인 미적용처럼 조건 자체가 없거나 해당 없는 경우도 실제 화면에서 그 상태를 확인한 후 해당 검증값을 `true`로 기록한다. 단가에 수량을 곱한 작성자 계산은 화면에서 선택 수량의 최종 총액을 확인한 것을 대신하지 않는다. 모호하거나 미확인인 값은 `false`로 두어 실패시킨다. 화면 접근 제한과 원본 누락은 가독성 수정으로 해소되었다고 기록하지 않는다.

그림의 배치·문서 내용·원본·쪽 이미지가 바뀌면 해시와 연결을 다시 확인하고 영향을 받는 시각 검수를 반복한다. 검수 기록을 실제 제출 문서에 추가하거나 별도 납품 PDF로 만들지 않는다.

`seller_and_total_same_capture`는 업체명과 해당 상품의 실제 최종 금액이 하나의 원본 캡처 안에서 함께 읽힐 때만 참이다. 문서의 판매처 제목이나 다른 화면 조각으로 대신하지 않는다. `only_quoted_product_visible`는 관련 없는 상품·추천 상품이 없고, 합계가 그 견적 상품에만 대응할 때 참이다. 장바구니 한 상품과 판매처별 소계의 연속 영역을 자를 수 있으나 혼합 주문 전체 합계를 가져오면 실패한다.

`pointer_free`는 각 저장 원본과 정확한 최종 파일의 해당 삽입 그림 및 현재 쪽 렌더링을 각각 직접 확대 확인하여 포인터, 클릭 후광, 툴팁, 호버 강조가 모두 없을 때만 참이다. 포인터가 이미지에 이미 기록될 수 있으므로 캡처 도구 설정이나 자동 검사의 통과만으로 참으로 두지 않는다. 오염이 있으면 화면을 안정시킨 뒤 원본을 재촬영하고 교체하며, 재확인할 수 없으면 거짓으로 남긴다. 증빙 픽셀을 덧칠하거나 AI로 지우지 않는다.

## 장바구니 필수 검사

장바구니 캡처가 요구된 경우 독립적으로 열거한 모든 비교견적 그림의 `source_kind`가 `cart`여야 한다. 문서의 모든 그림에 장바구니가 요구되면 `python scripts/verify_quote_capture_review.py <최종.hwpx> <검수.json> --require-cart`를 실행한다. 업체 발행 본견적처럼 제외할 근거가 있는 다른 그림이 함께 있으면 `--cart-picture-id <그림ID>`를 비교견적 그림마다 반복하고, 별도 그림 목록과 실제 문서 순서를 대조하여 누락이 없음을 확인한다. 지정 ID 누락이나 해당 그림의 비장바구니 원본은 실패다. 도우미는 지정한 ID의 적절성·전체 비교견적 포함 여부 또는 화면 진위를 판단하지 못한다.

`unrelated_page_chrome_excluded`는 판매처·제품·수량·총액·배송 및 할인 정보를 유지하면서 내비게이션, 검색창, 광고, 추천 상품, 안내문과 큰 빈 여백을 삽입용 단일 자르기에서 제외했는지 원본 및 최종 쪽을 직접 대조한 경우에만 참이다. 장바구니 화면이 분리되어 한 번의 자르기로 필수 내용을 담을 수 없으면 서로 다른 화면을 합성하지 말고 다시 캡처하거나 미완료로 둔다. 사용자가 지정한 견적서가 있으면 해당 쪽의 제목·표·사진 배치도 시각적으로 비교한다.
