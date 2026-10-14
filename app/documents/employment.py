import base64
import logging
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from pyairtable import Api
from app.config import settings
from app.documents.base import BaseDocumentGenerator
from app.documents.registry import register_document

logger = logging.getLogger(__name__)

EMPLOYMENT_BASE_ID = "appBrtwfDBFnsOgxS"
EMPLOYEE_TABLE_ID = "tbleAbyCtSkXgX5wu"
ATTACHMENT_FIELD = "Signed Agreement"

# Company information printed on the certificate
COMPANY_NAME = "주식회사 주코리아"
COMPANY_CEO = "오종현"
COMPANY_BIZ_NO = "395-86-00988"
COMPANY_ADDRESS = "서울특별시 강서구 양천로 424, 309호"

SEAL_IMAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "images" / "company_seal.png"
KST = timezone(timedelta(hours=9))


@register_document("employment")
class EmploymentCertificateGenerator(BaseDocumentGenerator):
    """Document generator for ZOO Digital Korea Certificate of Employment (재직증명서)"""

    def __init__(self):
        self.doc_type = "employment"
        self.template_subpath = "employment"
        self.template_name = "template.html"
        self.css_name = "style.css"

        if settings.AIRTABLE_API_KEY:
            self.api = Api(settings.AIRTABLE_API_KEY)
            self.table = self.api.table(EMPLOYMENT_BASE_ID, EMPLOYEE_TABLE_ID)
        else:
            self.api = None
            self.table = None

    def _extract_text(self, val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, list):
            return str(val[0]).strip() if len(val) > 0 else ""
        return str(val).strip()

    def _parse_date(self, val: Any) -> Optional[date]:
        text = self._extract_text(val)
        match = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', text)
        if not match:
            return None
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    def _format_date(self, d: Optional[date]) -> str:
        return f"{d.year}년 {d.month:02d}월 {d.day:02d}일" if d else ""

    def _seal_data_uri(self) -> str:
        # Playwright renders via set_content (no base URL), so the seal must be inlined
        if not SEAL_IMAGE_PATH.exists():
            return ""
        encoded = base64.b64encode(SEAL_IMAGE_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def fetch_data(self, record_id: str) -> Dict[str, Any]:
        if not self.table:
            raise ValueError("Airtable client is not configured. Check AIRTABLE_API_KEY.")
        record = self.table.get(record_id)
        return self.transform_fields(record.get("fields", {}), record_id)

    def transform_fields(self, fields: dict, record_id: str = "", today: Optional[date] = None) -> Dict[str, Any]:
        today = today or datetime.now(KST).date()
        joined_on = self._parse_date(fields.get("Joined On"))
        resigned_on = self._parse_date(fields.get("Resignation Date"))

        period_end = self._format_date(resigned_on) if resigned_on else "현재"
        period = f"{self._format_date(joined_on)} ~ {period_end}" if joined_on else ""

        return {
            "name": self._extract_text(fields.get("Name")),
            "english_name": self._extract_text(fields.get("English Name")),
            "resident_id": self._extract_text(fields.get("Social No.")),
            "address": self._extract_text(fields.get("Address")),
            "department": self._extract_text(fields.get("Department")),
            "position": self._extract_text(fields.get("Position")),
            "employment_period": period,
            "is_resigned": resigned_on is not None,
            "issue_date": self._format_date(today),
            "issue_date_iso": today.isoformat(),
            "doc_no": f"ZDK-EC-{today:%Y%m%d}-{record_id[-4:].upper()}" if record_id else f"ZDK-EC-{today:%Y%m%d}",
            "company_name": COMPANY_NAME,
            "company_ceo": COMPANY_CEO,
            "company_biz_no": COMPANY_BIZ_NO,
            "company_address": COMPANY_ADDRESS,
            "seal_image": self._seal_data_uri(),
            "record_id": record_id,
        }

    def get_output_filename(self, data: dict, record_id: str) -> str:
        name = data.get("name", "").replace(" ", "_")
        issued = data.get("issue_date_iso", "")
        if name:
            return f"재직증명서_{name}_{issued}.pdf"
        return f"Employment_Certificate_{record_id}.pdf"

    def update_airtable_attachment(self, record_id: str, file_url: str, filename: str):
        """Append the certificate to 'Signed Agreement' while keeping existing files"""
        if not self.table:
            logger.warning("Airtable client not configured. Skipping attachment update.")
            return

        record = self.table.get(record_id)
        existing = record.get("fields", {}).get(ATTACHMENT_FIELD) or []
        # Airtable replaces the whole attachment array on update; existing files are kept by passing their ids
        attachments = [{"id": att["id"]} for att in existing if att.get("id")]
        attachments.append({"url": file_url, "filename": filename})

        self.table.update(record_id, {ATTACHMENT_FIELD: attachments})
        logger.info(f"Appended {filename} to '{ATTACHMENT_FIELD}' of record {record_id} ({len(existing)} existing kept)")
