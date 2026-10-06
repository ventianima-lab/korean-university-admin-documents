# 명시적으로 허용된 유사제품 비교

동일 제품 비교가 기본이다. 사용자가 유사제품을 허용한 품목만 예외로 처리하며, 본견적의 구매 제품을 바꾸지 않는다. 차류는 종류·수확 조건·총중량을, 실습용품은 용도·필수 규격·총수량을 실제 근거로 대조한다. 브랜드·모델·포장·등급·산지의 차이 또는 미확인 조건을 숨기지 않는다. 포장 수가 다르면 실제 주문 단위와 동등한 총중량·총수량을 각각 적는다.

`--equivalence-manifest`의 JSON 형식은 다음과 같다. 숫자는 예시이며 기관 기준으로 일반화하지 않는다.

```json
{
  "authorization": "The user explicitly allowed a similar product when the same model was unavailable.",
  "items": [
    {
      "item": "실습용품",
      "main": {"product": "브랜드A 모델A", "quantity": "2개", "total": 24000, "source": "판매처A"},
      "comparisons": [
        {
          "product": "브랜드B 모델B",
          "quantity": "2개",
          "total": 22000,
          "source": "판매처B",
          "kind": "similar",
          "basis": "같은 용도와 필수 규격, 총 2개",
          "differences": "브랜드와 모델이 다름.",
          "allow_lower_price": true
        }
      ]
    }
  ]
}
```

- `items`는 문서의 전체 본견적 수와 순서가 같아야 한다. `product`, `quantity`, `total`, `source`는 설명문의 실제 값과 일치해야 한다.
- 동일제품 항목은 `kind: "identical"`로 적는다. 본견적과 제품·수량이 같아야 한다. 유사제품은 `kind: "similar"`, 비교 기준 `basis`, 문서에 그대로 표시할 차이 `differences`가 필요하다.
- 유사제품 가격이 더 낮거나 같으면 실제 가격을 유지하고 `allow_lower_price: true`로 그 예외를 기록한다. 가격을 부풀려 검사를 통과시키지 않는다.
- 문서에는 해당 품목의 `유사제품` 표시와 `differences` 문구를 편집 가능한 글자로 넣는다. 명세만 작성하고 실제 문서의 구분을 생략하면 안 된다.
- 명세는 실제 설명문의 일치·누락을 검사하는 장치다. 스크린샷의 진위, 수량 선택 상태, 비교 규격의 적절성과 기관의 승인 여부를 대신 증명하지 않는다. 원본 화면과 최종 PDF를 직접 확인한다.
