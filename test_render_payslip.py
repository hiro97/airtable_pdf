import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from app.pdf_engine import PDFEngine
from app.documents import DocumentRegistry

# Mock data strictly matching the user-uploaded real payslip
MOCK_PAYSLIP_FIELDS = {
    "성명": "이성은 (Seongeun Lee)",
    "주민등록번호": "800202-2011213",
    "부서": "Language",
    "직급": "LPM",
    "지급은행": "KEB하나(구외환포함)",
    "계좌번호": "556-910463-32307",
    "귀속월": "2026-08",
    "지급일자": "2026-08-25",
    "기본급": 2716670,
    "식대": 200000,
    "차량유지비": None,
    "수당": 62799,
    "수당 비고": "연장근로 3.0시간",
    "상여금": None,
    "검진지원비": None,
    "지급합계": 2979469,
    "국민연금": 129040,
    "건강보험": 97660,
    "장기요양보험료": 12830,
    "고용보험": 24450,
    "소득세": 49100,
    "지방소득세": 4910,
    "연말정산(소득세)": None,
    "연말정산(지방소득세)": None,
    "주차비": 20000,
    "공제합계": 337990,
    "실수령액": 2641479
}

async def main():
    print("Available document generators:", DocumentRegistry.list_types())
    payslip_gen = DocumentRegistry.get("payslip")
    
    data = payslip_gen.transform_fields(MOCK_PAYSLIP_FIELDS, "mock_payslip_rec_123")
    output_filename = payslip_gen.get_output_filename(data, "mock_payslip_rec_123")
    
    print(f"Generating PDF for doc_type='payslip' -> {output_filename}...")
    engine = PDFEngine(storage_dir=str(BASE_DIR / "storage"))
    
    pdf_path = await engine.generate_pdf(
        template_subpath=payslip_gen.template_subpath,
        template_filename=payslip_gen.template_name,
        css_filename=payslip_gen.css_name,
        data=data,
        output_filename=output_filename,
        screenshot_filename="preview_payslip.png"
    )
    print(f"Success! Generated Payslip PDF at: {pdf_path}")

if __name__ == "__main__":
    asyncio.run(main())
