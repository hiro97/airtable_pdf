from datetime import date

from app.documents.employment import EmploymentCertificateGenerator
from app.pdf_engine import PDFEngine


FIELDS = {
    "Name": "김민수",
    "English Name": "Minsu Kim",
    "Position": "MP PM",
    "Department": "Media Processing",
    "Social No.": "800101-1234567",
    "Address": "서울특별시 강남구 테헤란로 1",
    "Joined On": "2023-03-02",
}


def test_transform_fields_for_current_employee():
    generator = EmploymentCertificateGenerator()
    data = generator.transform_fields(FIELDS, "recEmp", today=date(2026, 10, 14))
    html = PDFEngine("storage").render_html("employment", "template.html", "style.css", data)

    assert data["employment_period"] == "2023년 03월 02일 ~ 현재"
    assert data["issue_date"] == "2026년 10월 14일"
    assert "800101-1234567" in html
    assert "재직하고 있음" in html
    assert generator.get_output_filename(data, "recEmp") == "재직증명서_김민수_2026-10-14.pdf"


def test_transform_fields_for_resigned_employee():
    generator = EmploymentCertificateGenerator()
    data = generator.transform_fields({**FIELDS, "Resignation Date": "2025-12-31"}, "recEmp")

    assert data["employment_period"] == "2023년 03월 02일 ~ 2025년 12월 31일"
    assert data["is_resigned"] is True


def test_attachment_is_appended_keeping_existing_files():
    generator = EmploymentCertificateGenerator()

    class Table:
        updated = None

        def get(self, record_id):
            return {"fields": {"Signed Agreement": [{"id": "attOld1", "url": "x"}, {"id": "attOld2", "url": "y"}]}}

        def update(self, record_id, payload):
            self.updated = payload

    generator.table = Table()
    generator.update_airtable_attachment("recEmp", "https://srv/files/download/a.pdf", "a.pdf")

    assert generator.table.updated == {
        "Signed Agreement": [
            {"id": "attOld1"},
            {"id": "attOld2"},
            {"url": "https://srv/files/download/a.pdf", "filename": "a.pdf"},
        ]
    }


def test_attachment_when_field_is_empty():
    generator = EmploymentCertificateGenerator()

    class Table:
        updated = None

        def get(self, record_id):
            return {"fields": {}}

        def update(self, record_id, payload):
            self.updated = payload

    generator.table = Table()
    generator.update_airtable_attachment("recEmp", "https://srv/a.pdf", "a.pdf")

    assert generator.table.updated == {"Signed Agreement": [{"url": "https://srv/a.pdf", "filename": "a.pdf"}]}
