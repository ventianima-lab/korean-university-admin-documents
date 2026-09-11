# Korean University Administrative Documents

한국 대학·학과 조교 업무에서 사용하는 공문, 계획서, 결과보고서, 예산·구매 서류, 안내문과 각종 HWP/HWPX·DOCX·XLSX·PDF 양식을 근거 기반으로 작성·수정·검증하는 Agent Skills 모음입니다.

## 핵심 원칙

- 제공된 최신 공식 양식이 있으면 그 양식을 설계 원본으로 사용합니다.
- 원본은 보존하고 별도 결과물에서 지정된 필드만 최소한으로 수정합니다.
- 이름, 날짜, 금액, 수량, 결재선, 업체, 연락처 등 근거 없는 값은 만들지 않습니다.
- 글꼴, 표, 셀 음영, 여백, 머리글·바닥글, 페이지 설정과 개체 배치를 보존합니다.
- 결과는 내용뿐 아니라 구조와 실제 렌더링을 함께 검증합니다.
- 이 스킬 묶음의 사용자는 현재 요청 범위에 필요한 한컴 자동화를 상시 허가합니다. 작업별·파일별·동작별 승인을 반복해서 요청하지 않습니다.

## 포함된 스킬

| 스킬 | 역할 |
|---|---|
| `korean-university-admin-documents` | 전체 문서 작업의 통합 진입점 |
| `hancom-hwpx-documents` | HWPX 양식 보존 편집, 한컴 자동화와 최종 재열기 검증 |
| `hwp-to-hwpx-converter` | 실제 파일 시그니처 기반 HWP→HWPX 변환 |
| `hwpx-internet-comparison-quotes` | 동일 제품·옵션·수량의 인터넷 견적 캡처, 편집 가능한 출처 설명문과 검증 |
| `docx-template-editor` | Word 양식, 변경 내용 추적, 댓글, 렌더 검증 |
| `spreadsheet-form-preservation` | Excel 양식의 셀·수식·숨김 시트·인쇄 설정 보존 |
| `document-scan-cleaner` | 사진 문서를 원문 픽셀을 보존한 스캔 이미지/PDF로 정리 |
| `finalize-department-files` | 완료된 학과자료를 본문·학년도·업무철 기준으로 분류하고 파일명·이동·해시·색인을 검증 |
| `korean-admin-writing` | 한국어 작성·스타일·윤문·문법 검수 라우터 |
| `fluent-korean` | 명확하고 자연스러운 한국어 작성 |
| `style-guide` | 공식 문서의 용어·어조·형식 일관성 |
| `grammar-checker` | 맞춤법·띄어쓰기·문법·구두점 검사 |
| `humanize-korean` | 비보호 서술부의 조건부 AI 문체 완화 |

## 설치

Agent Skills 호환 도구에서는 저장소 전체 또는 필요한 `skills/<name>` 폴더를 설치합니다. Codex에서는 각 스킬 폴더를 사용자 스킬 디렉터리에 복사할 수 있습니다.

```powershell
Copy-Item -Recurse -LiteralPath .\skills\* -Destination "$env:USERPROFILE\.codex\skills"
```

외부 실행 도구는 저장소에 포함하지 않습니다. 필요할 때 각 스킬의 안내에 따라 Kordoc, python-hwpx, pyhwpxlib, LibreOffice, Poppler 또는 관련 Python 패키지를 설치합니다.

## 한컴 자동화 상시 허가

이 저장소의 통합 스킬과 HWPX 스킬을 설치·사용하는 사용자는 현재 요청한 HWP/HWPX 작업을 완료하고 검증하는 데 합리적으로 필요한 한컴오피스, `Hwp.exe`, `HWPFrame.HwpObject`, COM 및 GUI 자동화를 상시 허가합니다. 별도의 작업별·파일별·동작별 승인이나 반복 승인을 요구하지 않습니다. 자동화는 현재 요청에 필요한 파일과 동작으로 제한하며, 기존 사용자 한글 창과 관련 없는 문서는 건드리지 않습니다.

## 공개 자료 원칙

예시는 모두 가상 자료입니다. 실제 학생·교직원 개인정보, 대학 내부 경로, 인증정보, 견적·계좌·연락처, 실제 제출 문서는 저장소에 포함하지 않습니다.

## 라이선스

저장소의 독자 작성 부분은 MIT License입니다. 포함하거나 변형한 제3자 MIT 자료와 설치형 의존성은 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 확인하세요.
