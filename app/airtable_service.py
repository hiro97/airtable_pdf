import logging
from typing import Dict, Any, List
from pyairtable import Api
from app.config import settings

logger = logging.getLogger(__name__)

class AirtableService:
    def __init__(self):
        if not settings.AIRTABLE_API_KEY or not settings.AIRTABLE_BASE_ID:
            logger.warning("Airtable API Key or Base ID is not configured.")
        self.api = Api(settings.AIRTABLE_API_KEY) if settings.AIRTABLE_API_KEY else None
        self.base_id = settings.AIRTABLE_BASE_ID
        self.po_table = self.api.table(self.base_id, settings.PO_TABLE_NAME) if self.api else None
        self.items_table = self.api.table(self.base_id, settings.ITEMS_TABLE_NAME) if self.api else None

    def _format_krw(self, amount: int | float) -> str:
        """Format number as KRW currency string: ₩15,000"""
        val = int(round(amount))
        return f"₩{val:,}"

    def _extract_text(self, val: Any) -> str:
        """Safely extract string value even if field is array/lookup"""
        if val is None:
            return ""
        if isinstance(val, list):
            return str(val[0]) if len(val) > 0 else ""
        return str(val).strip()

    def fetch_po_data(self, record_id: str) -> Dict[str, Any]:
        """Fetch parent PO record and all 1:N linked item records from Airtable"""
        if not self.po_table or not self.items_table:
            raise ValueError("Airtable client is not properly initialized. Check API key and Base ID.")

        # 1. Fetch parent record
        parent_record = self.po_table.get(record_id)
        fields = parent_record.get("fields", {})

        linguist = self._extract_text(fields.get(settings.FIELD_LINGUIST_NAME, ""))
        position = self._extract_text(fields.get(settings.FIELD_LINGUIST_POSITION, "SDH"))
        email = self._extract_text(fields.get(settings.FIELD_LINGUIST_EMAIL, ""))
        date_issued = self._extract_text(fields.get(settings.FIELD_DATE_ISSUED, ""))
        deadline_month = self._extract_text(fields.get(settings.FIELD_DEADLINE_MONTH, ""))
        payment_status = self._extract_text(fields.get(settings.FIELD_PAYMENT_STATUS, ""))

        # 2. Extract linked child item record IDs
        item_ids = fields.get(settings.FIELD_ITEMS_LINK, [])
        if not isinstance(item_ids, list):
            item_ids = [item_ids] if item_ids else []

        items: List[Dict[str, Any]] = []
        subtotal = 0

        # 3. Fetch each child item
        for idx, item_id in enumerate(item_ids, start=1):
            try:
                child_rec = self.items_table.get(item_id)
                child_fields = child_rec.get("fields", {})

                project = self._extract_text(child_fields.get(settings.ITEM_FIELD_PROJECT, ""))
                episode = self._extract_text(child_fields.get(settings.ITEM_FIELD_EPISODE, ""))
                deadline = self._extract_text(child_fields.get(settings.ITEM_FIELD_DEADLINE, ""))
                role = self._extract_text(child_fields.get(settings.ITEM_FIELD_ROLE, "TRS"))

                rate = float(child_fields.get(settings.ITEM_FIELD_RATE, 0) or 0)
                runtime = float(child_fields.get(settings.ITEM_FIELD_RUNTIME, 0) or 0)
                
                # If amount field exists and is populated, use it; otherwise rate * runtime
                raw_amount = child_fields.get(settings.ITEM_FIELD_AMOUNT)
                if raw_amount is not None and raw_amount != "":
                    amount = float(raw_amount)
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

        # 4. Tax and total calculations (Korean 3.3% Freelancer Tax)
        tax = int(round(subtotal * 0.033))
        real_total = int(subtotal - tax)

        po_code = f"ZOO Korea_{linguist}_{deadline_month}" if linguist and deadline_month else f"PO_{record_id}"

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

    def update_po_attachment(self, record_id: str, file_url: str, filename: str) -> Dict[str, Any]:
        """Update Airtable record with generated PDF attachment URL and uncheck trigger"""
        if not self.po_table:
            raise ValueError("Airtable client is not properly initialized.")

        # Airtable attachment field expects list of dicts with 'url' and optionally 'filename'
        update_payload = {
            settings.FIELD_ATTACHMENT: [
                {
                    "url": file_url,
                    "filename": filename
                }
            ],
            # Reset checkbox so it doesn't re-trigger continuously
            settings.FIELD_CHECKBOX: False
        }

        # Optionally update status if configured
        if settings.FIELD_STATUS:
            update_payload[settings.FIELD_STATUS] = "Issued"

        try:
            res = self.po_table.update(record_id, update_payload)
            logger.info(f"Updated record {record_id} successfully in Airtable.")
            return res
        except Exception as e:
            logger.error(f"Failed to update Airtable attachment for record {record_id}: {e}")
            raise
