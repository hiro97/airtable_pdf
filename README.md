# Airtable Multi-Document PDF Generator (Coolify Ready)

에어테이블(Airtable)에서 체크박스를 체크하면 해당 데이터(1:N 부모-자식 관계)를 조회하여 **ZOO DIGITAL KOREA 발주서(Purchase Order)** 및 **향후 추가될 다양한 PDF 문서들(인보이스, 계약서, 정산서 등)** 을 자동 생성하고, 에어테이블의 지정된 첨부파일 필드에 자동으로 저장하는 확장형 FastAPI 백엔드 마이크로서비스입니다.

---

## 📌 주요 특징
- **다중 문서 지원 (Registry / Strategy Pattern)**: 향후 인보이스, 계약서 등 새로운 PDF를 추가할 때 기존 코드 수정 없이 **새 템플릿과 생성 클래스만 추가**하면 즉시 확장 가능
- **100% 픽셀 퍼펙트 디자인**: 첨부해주신 ZOO Purchase Order 원본 디자인(로고, CONTRACTOR/ORDER DETAILS 카드, 에피소드 테이블, 3.3% 원천징수세 자동 계산, 이중선, 푸터)을 HTML/CSS와 Playwright(Headless Chrome)로 완벽하게 렌더링
- **1:N 관계 지원**: 부모 테이블(`Purchase Orders`)에 링크된 여러 개의 자식 테이블(`Episodes`) 레코드를 자동으로 묶어서 하나의 정산서로 생성
- **Airtable Attachment 자동 동기화**: 생성된 PDF를 임시 다운로드 URL로 노출하여 에어테이블 API를 통해 `PO Created` 첨부파일 필드에 원클릭 자동 업로드 & 체크박스 자동 해제
- **Coolify 원클릭 배포**: 리눅스 환경에서도 한글(`Noto Sans KR`, `Nanum`) 깨짐이 발생하지 않도록 사전 빌드된 Dockerfile 제공

---

## 🚀 1. 쿨리파이(Coolify) 배포 가이드

### 1) Coolify에서 애플리케이션 생성
1. Coolify 대시보드에서 **+ New Resource** → **Application** 선택
2. 코드가 포함된 Git 저장소를 연결하거나, **Dockerfile** 배포 방식을 선택합니다.
3. 기본 빌드 팩: `Dockerfile`
4. Ports Exposes: `8000`

### 2) 환경 변수(Environment Variables) 설정
Coolify 애플리케이션의 **Environment Variables** 탭에 다음 값들을 등록합니다:

| 환경변수명 | 필수 여부 | 설명 및 예시 |
| :--- | :---: | :--- |
| `BASE_URL` | **필수** | Coolify에서 설정한 이 서버의 공용 도메인 (예: `https://po.yourdomain.com`) |
| `AIRTABLE_API_KEY` | **필수** | Airtable Personal Access Token (`patXXXXXXXX...`) |
| `AIRTABLE_BASE_ID` | **필수** | 에어테이블 Base ID (`appXXXXXXXX...`) |
| `PO_TABLE_NAME` | 선택 | 부모 발주서 테이블 이름 (기본값: `Purchase Orders`) |
| `ITEMS_TABLE_NAME` | 선택 | 자식 에피소드 테이블 이름 (기본값: `Episodes`) |
| `FIELD_CHECKBOX` | 선택 | 발주서 생성 체크박스 필드명 (기본값: `Generate PO`) |
| `FIELD_ATTACHMENT` | 선택 | PDF를 저장할 첨부파일 필드명 (기본값: `PO Created`) |
| `FIELD_ITEMS_LINK` | 선택 | 부모 레코드에서 자식 레코드를 링크하는 필드명 (기본값: `Episodes`) |
| `WEBHOOK_SECRET` | 선택 | 보안 강화를 위한 웹훅 비밀 토큰 (Airtable 헤더에서 사용) |

> 💡 **주의**: `BASE_URL`은 Airtable 서버가 생성된 PDF를 가져가서 자체 저장할 때 사용하는 주소이므로, 반드시 외부에서 접근 가능한 도메인이어야 합니다.

---

## ⚡ 2. 에어테이블(Airtable) 자동화(Automation) 설정

### 발주서(PO) 생성 자동화
1. 에어테이블 상단의 **Automations** 탭 클릭 → **Create automation**
2. **Trigger**: `When a record matches conditions` 선택
   - **Table**: `Purchase Orders` (부모 발주서 테이블)
   - **Conditions**: `[Generate PO]` is `checked`
3. **Action**: **Run script** 선택 후 아래 코드 입력 (Input Variable `recordId` = Trigger의 `Airtable record ID` 매핑):

```javascript
let inputConfig = input.config();
let recordId = inputConfig.recordId;

// Coolify에 배포된 서버 도메인 주소
// 발주서(PO): /webhook/po 또는 /webhook/generate-po
let serverUrl = "https://po.yourdomain.com/webhook/po";

await fetch(serverUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ record_id: recordId })
});
```

### 💡 [추천] 에어테이블 버튼(Button) 필드로 원클릭 PDF 생성 (자동화 횟수 소모 X)
복잡한 Automation 스크립트 설정 없이, 에어테이블의 **Button** 필드로 즉시 연동할 수 있습니다.
1. 새 필드 추가 → 타입: **Button**
2. Action: **Open URL** 선택
3. URL Formula 입력:
   - **급여명세서**: `"https://your-domain.com/generate/payslip?record_id=" & RECORD_ID()`
   - **발주서**: `"https://your-domain.com/generate/po?record_id=" & RECORD_ID()`
4. 버튼을 클릭하면 브라우저 창에서 진행 상태가 표시된 후 3초 뒤 자동 닫히며, 지정된 첨부파일 필드(예: `Paystub`, `PO Created`)에 PDF가 자동 업로드됩니다.

---

## 🧩 3. 나중에 새로운 PDF 문서 추가하는 방법 (Extending New PDFs)

새로운 문서(예: 인보이스 `invoice`, 프리랜서 계약서 `contract` 등)를 추가하려면 **단 2개의 파일만 작성**하면 자동으로 시스템에 등록됩니다!

### 단계 1: 템플릿 폴더 생성 (`app/templates/{문서이름}/`)
`app/templates/invoice/` 폴더를 만들고 HTML과 CSS를 넣습니다:
- `app/templates/invoice/template.html`
- `app/templates/invoice/style.css`

### 단계 2: 문서 생성 클래스 작성 (`app/documents/invoice.py`)
`BaseDocumentGenerator`를 상속받고 `@register_document("invoice")` 데코레이터를 붙입니다:

```python
# app/documents/invoice.py
from app.documents.base import BaseDocumentGenerator
from app.documents.registry import register_document

@register_document("invoice")
class InvoiceGenerator(BaseDocumentGenerator):
    def __init__(self):
        self.doc_type = "invoice"
        self.template_subpath = "invoice"
        self.template_name = "template.html"
        self.css_name = "style.css"
        # Airtable 테이블 초기화...

    def fetch_data(self, record_id: str) -> dict:
        # 에어테이블에서 인보이스 데이터 조회 및 가공
        return { ... }

    def get_output_filename(self, data: dict, record_id: str) -> str:
        return f"Invoice_{record_id}.pdf"

    def update_airtable_attachment(self, record_id: str, file_url: str, filename: str):
        # 에어테이블 인보이스 레코드의 첨부파일 필드에 URL 업데이트
        ...
```

### 단계 3: `app/documents/__init__.py`에 한 줄 추가
```python
from app.documents import po, invoice
```

**끝입니다!** 이제 에어테이블에서 `POST https://po.yourdomain.com/webhook/invoice` 로 웹훅만 쏘면 새로운 인보이스 PDF가 바로 생성됩니다.

---

## 🛠️ 4. 로컬 개발 및 테스트

```bash
# 가상환경 활성화
source .venv/bin/activate

# 발주서 렌더링 테스트 (storage/ZOO_Korea_김애정_2026-07.pdf 생성)
python3 test_render.py

# API 엔드포인트 테스트
python3 test_api.py

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```
