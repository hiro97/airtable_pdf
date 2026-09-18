import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from app.pdf_engine import PDFEngine
from app.documents import DocumentRegistry

MOCK_DATA = {
    "po_code": "ZOO Korea_김애정_2026-07",
    "contractor": {
        "linguist": "김애정",
        "position": "SDH",
        "email": "wlioop@naver.com"
    },
    "order": {
        "date_issued": "2026-08-20",
        "deadline_month": "2026-07",
        "payment_status": ""
    },
    "items": [
        {
            "no": 1,
            "project_name": "Atashin'chi Remaster 2",
            "episode": "Ep: 19",
            "deadline": "2026-07-06",
            "role": "TRS",
            "rate_formatted": "₩1,500",
            "runtime": 10,
            "amount_formatted": "₩15,000"
        },
        {
            "no": 2,
            "project_name": "Atashin'chi Remaster 2",
            "episode": "Ep: 20",
            "deadline": "2026-07-06",
            "role": "TRS",
            "rate_formatted": "₩1,500",
            "runtime": 10,
            "amount_formatted": "₩15,000"
        },
        {
            "no": 3,
            "project_name": "Atashin'chi Remaster 2",
            "episode": "Ep: 57",
            "deadline": "2026-07-09",
            "role": "TRS",
            "rate_formatted": "₩1,500",
            "runtime": 10,
            "amount_formatted": "₩15,000"
        },
        {
            "no": 4,
            "project_name": "Atashin'chi Remaster 2",
            "episode": "Ep: 58",
            "deadline": "2026-07-09",
            "role": "TRS",
            "rate_formatted": "₩1,500",
            "runtime": 10,
            "amount_formatted": "₩15,000"
        },
        {
            "no": 5,
            "project_name": "Atashin'chi Remaster 2",
            "episode": "Ep: 59",
            "deadline": "2026-07-10",
            "role": "TRS",
            "rate_formatted": "₩1,500",
            "runtime": 10,
            "amount_formatted": "₩15,000"
        },
        {
            "no": 6,
            "project_name": "Atashin'chi Remaster 2",
            "episode": "Ep: 60",
            "deadline": "2026-07-10",
            "role": "TRS",
            "rate_formatted": "₩1,500",
            "runtime": 10,
            "amount_formatted": "₩15,000"
        }
    ],
    "summary": {
        "subtotal_formatted": "₩90,000",
        "tax_formatted": "- ₩2,970",
        "real_total_formatted": "₩87,030",
        "grand_total_formatted": "₩87,030"
    },
    "remark": "The payment will be automatically remitted to your registered bank account on the pre-scheduled payment date.",
    "company_name": "ZOO DIGITAL KOREA",
    "footer_notice": "If you have any questions regarding this Purchase Order, please contact support at your designated coordinator email. Please check that your details and project records match before accepting payments."
}

async def main():
    print("Available document generators in registry:", DocumentRegistry.list_types())
    po_gen = DocumentRegistry.get("po")
    
    engine = PDFEngine(storage_dir=str(BASE_DIR / "storage"))
    output_filename = po_gen.get_output_filename(MOCK_DATA, "mock_rec_123")
    
    print(f"Generating PDF for doc_type='po' -> {output_filename}...")
    pdf_path = await engine.generate_pdf(
        template_subpath=po_gen.template_subpath,
        template_filename=po_gen.template_name,
        css_filename=po_gen.css_name,
        data=MOCK_DATA,
        output_filename=output_filename,
        screenshot_filename="preview_page-1.png"
    )
    print(f"Success! Generated PDF at: {pdf_path}")

if __name__ == "__main__":
    asyncio.run(main())
