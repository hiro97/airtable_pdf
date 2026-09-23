import re
import logging
from typing import Dict, Any, List, Optional
from pyairtable import Api
from app.config import settings
from app.documents.base import BaseDocumentGenerator
from app.documents.registry import register_document

logger = logging.getLogger(__name__)

PAYSLIP_BASE_ID = "appBrtwfDBFnsOgxS"
PAYSLIP_TABLE_ID = "tblWCYgcNpZKNSfXI"
EMPLOYEE_TABLE_ID = "tbleAbyCtSkXgX5wu"

@register_document("payslip")
class PayslipGenerator(BaseDocumentGenerator):
    """Document generator for ZOO Digital Korea Employee Payslip (급여명세서)"""

    def __init__(self):
        self.doc_type = "payslip"
        self.template_subpath = "payslip"
        self.template_name = "template.html"
        self.css_name = "style.css"

        if settings.AIRTABLE_API_KEY:
            self.api = Api(settings.AIRTABLE_API_KEY)
            self.table = self.api.table(PAYSLIP_BASE_ID, PAYSLIP_TABLE_ID)
            self.employee_table = self.api.table(PAYSLIP_BASE_ID, EMPLOYEE_TABLE_ID)
        else:
            self.api = None
            self.table = None
            self.employee_table = None

    def _format_krw(self, amount: int | float) -> str:
        if amount is None or amount == "" or amount == 0:
            return ""
        try:
            val = int(round(float(amount)))
            return f"₩{val:,}"
        except Exception:
            return str(amount)

    def _extract_number(self, val: Any) -> int:
        if val is None or val == "":
            return 0
        if isinstance(val, (int, float)):
            return int(round(val))
        clean_str = re.sub(r'[^0-9.-]', '', str(val))
        try:
            return int(round(float(clean_str)))
        except ValueError:
            return 0

    def _extract_text(self, val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, list):
            return str(val[0]) if len(val) > 0 else ""
        return str(val).strip()

    def _find_field_value(self, fields: dict, candidate_keys: list) -> Any:
        for k in candidate_keys:
            if k in fields and fields[k] is not None:
                return fields[k]
        return None

    def fetch_data(self, record_id: str) -> Dict[str, Any]:
        """Fetch payslip record from Airtable and process fields"""
        if not self.table:
            raise ValueError("Airtable client is not configured. Check AIRTABLE_API_KEY.")

        record = self.table.get(record_id)
        fields = record.get("fields", {})
        employee_fields = {}
        employee_ids = fields.get("Employee") or []
        if employee_ids and self.employee_table:
            employee_fields = self.employee_table.get(employee_ids[0]).get("fields", {})
        return self.transform_fields(fields, record_id, employee_fields)

    def transform_fields(self, fields: dict, record_id: str = "", employee_fields: Optional[dict] = None) -> Dict[str, Any]:
        """Transform Airtable raw record fields into payslip template context"""
        employee_fields = employee_fields or {}
        # Employee Information
        name = self._extract_text(self._find_field_value(fields, ["성명", "성 명", "이름", "Name", "직원명"]))
        if not name:
            name = self._extract_text(employee_fields.get("Name"))
        if not name:
            name = re.sub(r'\s+\d{4}[-_.]\d{2}$', '', self._extract_text(fields.get("Name_Month")))
        english_name = self._extract_text(self._find_field_value(fields, ["English Name"]))
        if english_name and english_name != name and english_name not in name:
            name = f"{name} ({english_name})" if name else english_name
        resident_id = self._extract_text(self._find_field_value(fields, ["주민등록번호", "주민번호", "주민 번호", "Resident ID", "ID Number"]))
        department = self._extract_text(self._find_field_value(fields, ["부서", "부 서", "소속", "Department", "Dept"]))
        if not department:
            department = self._extract_text(employee_fields.get("Department"))
        position = self._extract_text(self._find_field_value(fields, ["직급", "직 급", "직책", "Position", "Title", "Role"]))
        bank = self._extract_text(self._find_field_value(fields, ["지급은행", "지급 은행", "은행", "은행명", "Bank"]))
        if not bank:
            bank = self._extract_text(employee_fields.get("은행명"))
        account_no = self._extract_text(self._find_field_value(fields, ["계좌번호", "계좌 번호", "Bank Account No", "Account Number", "Account No", "Account"]))
        if not account_no:
            account_no = self._extract_text(employee_fields.get("계좌번호"))

        # Dates
        period = self._extract_text(self._find_field_value(fields, ["귀속월", "귀속 월", "급여월", "월급월", "Period", "Month"]))
        payment_date = self._extract_text(self._find_field_value(fields, ["지급일자", "지급일", "지급 일자", "월급지급날짜", "Payment Date", "Pay Date", "Date"]))

        # Fallbacks for Name / Period from primary field
        if not period:
            match = re.search(r'\d{4}[-_.]\d{2}', self._extract_text(fields.get("Name_Month") or fields.get("Name")))
            if match:
                period = match.group(0).replace(".", "-").replace("_", "-")

        # Earnings Items (지급 항목)
        base_salary = self._extract_number(self._find_field_value(fields, ["기본급", "기본급여", "Base Salary"]))
        meal_allowance = self._extract_number(self._find_field_value(fields, ["식대", "식대보조금", "Meal"]))
        car_allowance = self._extract_number(self._find_field_value(fields, ["차량유지비", "차량보조금", "Car Allowance"]))

        # Overtime / Allowances
        overtime_val = self._extract_number(self._find_field_value(fields, ["수당", "연장수당", "연장근로수당", "연장근로", "Overtime"]))
        overtime_note = self._extract_text(self._find_field_value(fields, ["수당 비고", "수당내역"]))
        hours_value = self._find_field_value(fields, ["Overtime", "초과근무시간", "연장근로시간"])
        if hours_value is not None and not overtime_note:
            try:
                hours = float(hours_value)
                if hours > 0:
                    overtime_note = f"초과근무 {hours:g}시간"
            except (TypeError, ValueError):
                pass

        bonus = self._extract_number(self._find_field_value(fields, ["상여금", "상여", "Bonus"]))
        health_checkup = self._extract_number(self._find_field_value(fields, ["검진지원비", "건강검진비", "검진비", "Medical Checkup"]))

        # Earnings List
        earnings = [
            {"name": "기본급", "note": "", "amount": base_salary, "amount_formatted": self._format_krw(base_salary)},
            {"name": "식대", "note": "", "amount": meal_allowance, "amount_formatted": self._format_krw(meal_allowance)},
            {"name": "차량유지비", "note": "", "amount": car_allowance, "amount_formatted": self._format_krw(car_allowance)},
            {"name": "수당", "note": overtime_note, "amount": overtime_val, "amount_formatted": self._format_krw(overtime_val)},
            {"name": "상여금", "note": "", "amount": bonus, "amount_formatted": self._format_krw(bonus)},
            {"name": "검진지원비", "note": "", "amount": health_checkup, "amount_formatted": self._format_krw(health_checkup)},
        ]

        # Total Earnings
        calc_total_earnings = sum(item["amount"] for item in earnings)
        given_total_earnings = self._extract_number(self._find_field_value(fields, ["지급합계", "총지급액", "Total Earnings"]))
        total_earnings = given_total_earnings if given_total_earnings > 0 else calc_total_earnings

        # Deductions Items (공제 항목)
        national_pension = self._extract_number(self._find_field_value(fields, ["국민연금", "National Pension"]))
        health_insurance = self._extract_number(self._find_field_value(fields, ["건강보험", "Health Insurance"]))
        long_term_care = self._extract_number(self._find_field_value(fields, ["장기요양보험료", "장기요양", "Long-term Care"]))
        employment_insurance = self._extract_number(self._find_field_value(fields, ["고용보험", "Employment Insurance"]))
        income_tax = self._extract_number(self._find_field_value(fields, ["소득세", "Income Tax"]))
        local_income_tax = self._extract_number(self._find_field_value(fields, ["지방소득세", "주민세", "Local Income Tax"]))
        year_end_tax = self._extract_number(self._find_field_value(fields, ["연말정산(소득세)", "연말정산(차감소득세)", "연말정산 소득세", "Year-end Tax"]))
        year_end_local_tax = self._extract_number(self._find_field_value(fields, ["연말정산(지방소득세)", "연말정산(차감지방소득세)", "연말정산 지방소득세", "Year-end Local Tax"]))
        parking_fee = self._extract_number(self._find_field_value(fields, ["주차비", "Parking Fee"]))

        # Deductions List
        deductions = [
            {"name": "국민연금", "note": "", "amount": national_pension, "amount_formatted": self._format_krw(national_pension)},
            {"name": "건강보험", "note": "", "amount": health_insurance, "amount_formatted": self._format_krw(health_insurance)},
            {"name": "장기요양보험료", "note": "", "amount": long_term_care, "amount_formatted": self._format_krw(long_term_care)},
            {"name": "고용보험", "note": "", "amount": employment_insurance, "amount_formatted": self._format_krw(employment_insurance)},
            {"name": "소득세", "note": "", "amount": income_tax, "amount_formatted": self._format_krw(income_tax)},
            {"name": "지방소득세", "note": "", "amount": local_income_tax, "amount_formatted": self._format_krw(local_income_tax)},
            {"name": "연말정산(소득세)", "note": "", "amount": year_end_tax, "amount_formatted": self._format_krw(year_end_tax)},
            {"name": "연말정산(지방소득세)", "note": "", "amount": year_end_local_tax, "amount_formatted": self._format_krw(year_end_local_tax)},
            {"name": "주차비", "note": "", "amount": parking_fee, "amount_formatted": self._format_krw(parking_fee)},
        ]

        # Balance rows between earnings and deductions for strict Swiss symmetry
        max_rows = max(len(earnings), len(deductions))
        while len(earnings) < max_rows:
            earnings.append({"name": "", "note": "", "amount": None, "amount_formatted": ""})
        while len(deductions) < max_rows:
            deductions.append({"name": "", "note": "", "amount": None, "amount_formatted": ""})

        # Total Deductions
        calc_total_deductions = sum(item["amount"] for item in deductions if item["amount"])
        given_total_deductions = self._extract_number(self._find_field_value(fields, ["공제합계", "총공제액", "Total Deductions"]))
        total_deductions = given_total_deductions if given_total_deductions > 0 else calc_total_deductions

        # Net Payable (실수령액)
        given_net_pay = self._extract_number(self._find_field_value(fields, ["실수령액", "차인지급액", "실지급액", "Net Pay"]))
        net_pay = given_net_pay if given_net_pay > 0 else (total_earnings - total_deductions)

        return {
            "name": name,
            "resident_id": resident_id,
            "department": department,
            "position": position,
            "bank": bank,
            "account_no": account_no,
            "period": period,
            "payment_date": payment_date,
            "earnings": earnings,
            "total_earnings_formatted": self._format_krw(total_earnings),
            "deductions": deductions,
            "total_deductions_formatted": self._format_krw(total_deductions),
            "net_pay_formatted": self._format_krw(net_pay),
            "company_name": "주식회사 주코리아",
            "record_id": record_id
        }

    def get_output_filename(self, data: dict, record_id: str) -> str:
        name = data.get("name", "").replace(" ", "_")
        period = data.get("period", "").replace(" ", "_")
        if name and period:
            return f"급여명세서_{name}_{period}.pdf"
        elif name:
            return f"급여명세서_{name}_{record_id}.pdf"
        return f"Payslip_{record_id}.pdf"

    def update_airtable_attachment(self, record_id: str, file_url: str, filename: str):
        """Update Airtable record with the generated PDF attachment and uncheck trigger"""
        if not self.table:
            logger.warning("Airtable client not configured. Skipping attachment update.")
            return

        # 1. Inspect record to identify trigger checkbox and attachment fields
        record = self.table.get(record_id)
        fields = record.get("fields", {})

        # Find attachment field candidates: 'Paystub', '급여명세서', '명세서', 'PDF', '첨부파일', 'Attachment'
        att_field_name = None
        for cand in ["Paystub", "paystub", "급여명세서", "명세서", "PDF", "첨부파일", "Attachment", "Files", "급여 명세서"]:
            if cand in fields or cand.lower() in [k.lower() for k in fields.keys()]:
                att_field_name = cand
                break

        # Fallback to first existing attachment or default
        if not att_field_name:
            att_field_name = "Paystub"

        # Find checkbox field candidates: 'PDF 생성', '생성', 'Generate PDF', 'Create PDF'
        checkbox_field_name = None
        for cand in ["PDF 생성", "PDF생성", "Generate PDF", "Create PDF", "발행", "생성"]:
            if cand in fields:
                checkbox_field_name = cand
                break

        update_payload = {
            att_field_name: [{"url": file_url, "filename": filename}]
        }
        if checkbox_field_name:
            update_payload[checkbox_field_name] = False

        try:
            self.table.update(record_id, update_payload)
            logger.info(f"Successfully updated payslip record {record_id} in table {PAYSLIP_TABLE_ID}")
        except Exception as e:
            logger.error(f"Failed to update Airtable payslip record {record_id}: {e}")
            # Try updating without checkbox if checkbox update failed
            if checkbox_field_name:
                try:
                    self.table.update(record_id, {att_field_name: [{"url": file_url, "filename": filename}]})
                    logger.info(f"Successfully updated attachment only for record {record_id}")
                except Exception as e2:
                    logger.error(f"Failed attachment-only update: {e2}")
