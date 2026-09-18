import re
import logging
from typing import Dict, Any, List
from pyairtable import Api
from app.config import settings
from app.documents.base import BaseDocumentGenerator
from app.documents.registry import register_document

logger = logging.getLogger(__name__)

@register_document("po")
class PurchaseOrderGenerator(BaseDocumentGenerator):
    """Document generator for ZOO Digital Korea Purchase Order"""

    def __init__(self):
        self.doc_type = "po"
        self.template_subpath = "po"
        self.template_name = "template.html"
        self.css_name = "style.css"

        if settings.AIRTABLE_API_KEY and settings.AIRTABLE_BASE_ID:
            self.api = Api(settings.AIRTABLE_API_KEY)
            self.po_table = self.api.table(settings.AIRTABLE_BASE_ID, settings.PO_TABLE_NAME)
            self.items_table = self.api.table(settings.AIRTABLE_BASE_ID, settings.ITEMS_TABLE_NAME)
        else:
            self.api = None
            self.po_table = None
            self.items_table = None

    def _format_krw(self, amount: int | float) -> str:
        val = int(round(amount))
        return f"₩{val:,}"

    def _extract_text(self, val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, list):
            return str(val[0]) if len(val) > 0 else ""
        return str(val).strip()

    def fetch_data(self, record_id: str) -> Dict[str, Any]:
        """Fetch 1:N PO and Episodes data from Airtable"""
        if not self.po_table or not self.items_table:
            raise ValueError("Airtable client is not configured. Check AIRTABLE_API_KEY and AIRTABLE_BASE_ID.")

        parent_record = self.po_table.get(record_id)
        fields = parent_record.get("fields", {})

        # Primary PO title/name (e.g. ZOO Korea_김애정_2026-07)
        po_name = self._extract_text(fields.get("Name", ""))
        linguist = self._extract_text(fields.get(settings.FIELD_LINGUIST_NAME, ""))
        
        # Position fallback
        position = (
            self._extract_text(fields.get(settings.FIELD_LINGUIST_POSITION))
            or self._extract_text(fields.get("Position", "SDH"))
        )
        email = self._extract_text(fields.get(settings.FIELD_LINGUIST_EMAIL, ""))
        date_issued = self._extract_text(fields.get(settings.FIELD_DATE_ISSUED, ""))
        deadline_month = self._extract_text(fields.get(settings.FIELD_DEADLINE_MONTH, ""))
        payment_status = self._extract_text(fields.get(settings.FIELD_PAYMENT_STATUS, ""))

        # If po_name exists in Name column, use it directly
        if po_name:
            po_code = po_name
            # Try parsing deadline month from Name if not directly provided (e.g. ZOO Korea_김애정_2026-07 -> 2026-07)
            if not deadline_month:
                match = re.search(r'\d{4}-\d{2}', po_name)
                if match:
                    deadline_month = match.group(0)
            if not linguist:
                parts = po_name.split("_")
                if len(parts) >= 2:
                    linguist = parts[1]
        else:
            po_code = f"ZOO Korea_{linguist}_{deadline_month}" if linguist and deadline_month else f"PO_{record_id}"

        # Find linked items (support '작업내역', 'Episodes', 'Line Items')
        item_ids = (
            fields.get(settings.FIELD_ITEMS_LINK)
            or fields.get("작업내역")
            or fields.get("Episodes")
            or fields.get("Line Items")
            or []
        )
        if not isinstance(item_ids, list):
            item_ids = [item_ids] if item_ids else []

        items: List[Dict[str, Any]] = []
        subtotal = 0

        for idx, item_id in enumerate(item_ids, start=1):
            try:
                child_rec = self.items_table.get(item_id)
                child_fields = child_rec.get("fields", {})

                project = (
                    self._extract_text(child_fields.get(settings.ITEM_FIELD_PROJECT))
                    or self._extract_text(child_fields.get("Series"))
                    or self._extract_text(child_fields.get("프로젝트"))
                    or self._extract_text(child_fields.get("작품명"))
                    or self._extract_text(child_fields.get("Name"))
                )
                episode = (
                    self._extract_text(child_fields.get(settings.ITEM_FIELD_EPISODE))
                    or self._extract_text(child_fields.get("에피소드"))
                )
                deadline = (
                    self._extract_text(child_fields.get(settings.ITEM_FIELD_DEADLINE))
                    or self._extract_text(child_fields.get("마감일"))
                )
                role = (
                    self._extract_text(child_fields.get(settings.ITEM_FIELD_ROLE))
                    or self._extract_text(child_fields.get("역할"))
                    or "TRS"
                )

                rate = float(child_fields.get(settings.ITEM_FIELD_RATE, 0) or child_fields.get("단가", 0) or 0)
                runtime = float(child_fields.get(settings.ITEM_FIELD_RUNTIME, 0) or child_fields.get("러닝타임", 0) or 0)

                raw_amount = child_fields.get(settings.ITEM_FIELD_AMOUNT) or child_fields.get("금액")
                if raw_amount is not None and raw_amount != "":
                    amount = float(str(raw_amount).replace("₩", "").replace(",", "").strip())
                else:
                    amount = rate * runtime

                subtotal += amount

                items.append({
                    "no": idx,
                    "project_name": project,
                    "episode": episode if episode.startswith("Ep:") else f"Ep: {episode}" if episode else "",
                    "deadline": deadline,
                    "role": role,
                    "rate_formatted": self._format_krw(rate),
                    "runtime": int(runtime) if runtime.is_integer() else runtime,
                    "amount_formatted": self._format_krw(amount),
                    "amount": amount
                })
            except Exception as e:
                logger.error(f"Error fetching child record {item_id}: {e}")

        # If subtotal from child items is 0, check parent "Total For Month"
        parent_total = fields.get("Total For Month")
        if subtotal == 0 and parent_total:
            try:
                subtotal = float(str(parent_total).replace("₩", "").replace(",", "").strip())
            except Exception:
                pass

        # Freelancer 3.3% Tax calculation
        parent_tax = fields.get("Real Tax")
        if parent_tax:
            try:
                tax = int(round(float(str(parent_tax).replace("₩", "").replace(",", "").strip())))
            except Exception:
                tax = int(round(subtotal * 0.033))
        else:
            tax = int(round(subtotal * 0.033))

        real_total = int(subtotal - tax)

        return {
            "record_id": record_id,
            "po_code": po_code,
            "contractor": {
                "linguist": linguist,
                "position": position,
                "email": email
            },
            "order": {
                "date_issued": date_issued,
                "deadline_month": deadline_month,
                "payment_status": payment_status
            },
            "items": items,
            "summary": {
                "subtotal_formatted": self._format_krw(subtotal),
                "tax_formatted": f"- {self._format_krw(tax)}",
                "real_total_formatted": self._format_krw(real_total),
                "grand_total_formatted": self._format_krw(real_total),
                "subtotal": subtotal,
                "tax": tax,
                "real_total": real_total
            }
        }

    def get_output_filename(self, data: Dict[str, Any], record_id: str) -> str:
        po_code = data.get("po_code", f"PO_{record_id}")
        clean = re.sub(r'[/\\?%*:|"<>]', '_', po_code).strip().replace(" ", "_")
        return f"{clean}.pdf"

    def update_airtable_attachment(self, record_id: str, file_url: str, filename: str) -> Dict[str, Any]:
        """Update PO Created attachment field and reset trigger checkbox (Create PO)"""
        if not self.po_table:
            raise ValueError("Airtable client is not configured.")

        update_payload = {
            settings.FIELD_ATTACHMENT: [
                {
                    "url": file_url,
                    "filename": filename
                }
            ],
            # Reset checkbox 'Create PO'
            settings.FIELD_CHECKBOX: False
        }
        if settings.FIELD_STATUS and settings.FIELD_STATUS.strip():
            try:
                payload_with_status = dict(update_payload)
                payload_with_status[settings.FIELD_STATUS.strip()] = "Issued"
                return self.po_table.update(record_id, payload_with_status)
            except Exception as e:
                logger.warning(f"Failed to update optional status field '{settings.FIELD_STATUS}': {e}. Retrying without status field.")

        return self.po_table.update(record_id, update_payload)
