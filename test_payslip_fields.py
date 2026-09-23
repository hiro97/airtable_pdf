from app.documents.payslip import PayslipGenerator
from app.pdf_engine import PDFEngine


def test_current_airtable_fields_render_employee_dates_and_overtime():
    generator = PayslipGenerator()
    fields = {
        "Name_Month": "김민수 2026-09",
        "Employee": ["recEmployee"],
        "English Name": ["Minsu Kim"],
        "월급월": "2026-09",
        "월급지급날짜": "2026-09-23",
        "주민번호": ["800101-1234567"],
        "Position": ["MP PM"],
        "Bank Code": ["081"],
        "Bank Account No": ["123456789"],
        "기본급": [8092000],
        "수당": 975157.89,
        "Overtime": 16,
        "상여": 500000,
        "지급합계": 9567157.89,
        "공제합계": 1000000,
        "차인지급액": 8567157.89,
    }
    employee = {"Name": "김민수", "Department": "Media Processing", "은행명": "KEB하나은행", "계좌번호": "123456789"}

    data = generator.transform_fields(fields, "recPayslip", employee)
    html = PDFEngine("storage").render_html("payslip", "template.html", "style.css", data)

    assert "김민수" in data["name"]
    assert "Minsu Kim" in data["name"]
    assert data["department"] == "Media Processing"
    assert data["bank"] == "KEB하나은행"
    assert data["account_no"] == "123456789"
    assert data["period"] == "2026-09"
    assert data["payment_date"] == "2026-09-23"
    assert data["earnings"][3]["note"] == "초과근무 16시간"
    assert "초과근무 16시간" in html
    assert "2026-09-23" in html


def test_fetch_data_uses_linked_employee_record():
    generator = PayslipGenerator()

    class Table:
        def __init__(self, data):
            self.data = data
            self.ids = []

        def get(self, record_id):
            self.ids.append(record_id)
            return {"fields": self.data}

    generator.table = Table({"Employee": ["recEmployee"], "Overtime": 1.5, "수당": 10000})
    generator.employee_table = Table({"Name": "김민수", "은행명": "KEB하나은행"})

    data = generator.fetch_data("recPayslip")

    assert generator.employee_table.ids == ["recEmployee"]
    assert data["name"] == "김민수"
    assert data["earnings"][3]["note"] == "초과근무 1.5시간"


def test_no_overtime_does_not_show_hours():
    data = PayslipGenerator().transform_fields({"수당": 10000, "Overtime": 0})
    assert data["earnings"][3]["note"] == ""
