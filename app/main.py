import os
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from app.config import settings
from app.pdf_engine import PDFEngine
from app.documents import DocumentRegistry

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("po-generator")

app = FastAPI(
    title="Airtable Multi-Document PDF Generator",
    description="Multi-template PDF generator service triggered by Airtable automations and deployed on Coolify",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_path = Path(settings.STORAGE_DIR)
storage_path.mkdir(parents=True, exist_ok=True)

pdf_engine = PDFEngine(storage_dir=settings.STORAGE_DIR)

def sanitize_filename(name: str) -> str:
    clean = re.sub(r'[/\\?%*:|"<>]', '_', name)
    return clean.strip().replace(" ", "_")

async def process_document_workflow(doc_type: str, record_id: str):
    """Universal background worker that handles data fetch, PDF render, and Airtable attachment sync"""
    try:
        logger.info(f"Starting [{doc_type}] document workflow for Airtable record: {record_id}")
        generator = DocumentRegistry.get(doc_type)

        # 1. Fetch data from Airtable
        doc_data = generator.fetch_data(record_id)
        filename = sanitize_filename(generator.get_output_filename(doc_data, record_id))

        # 2. Generate PDF via Playwright engine
        await pdf_engine.generate_pdf(
            template_subpath=generator.template_subpath,
            template_filename=generator.template_name,
            css_filename=generator.css_name,
            data=doc_data,
            output_filename=filename
        )

        # 3. Construct public download URL
        import urllib.parse
        import time
        file_url = f"{settings.BASE_URL.rstrip('/')}/files/download/{urllib.parse.quote(filename)}?t={int(time.time())}"
        logger.info(f"PDF generated successfully: {file_url}")

        # 4. Sync back to Airtable
        generator.update_airtable_attachment(record_id, file_url, filename)
        logger.info(f"[{doc_type}] workflow finished successfully for record: {record_id}")

    except Exception as e:
        logger.error(f"Error processing [{doc_type}] for record {record_id}: {e}", exc_info=True)

@app.get("/health")
def health_check():
    """Health check endpoint for Coolify monitoring"""
    return {
        "status": "healthy",
        "supported_documents": DocumentRegistry.list_types(),
        "storage_ready": storage_path.exists(),
        "base_url": settings.BASE_URL
    }

@app.post("/webhook/generate-po")
async def generate_po_legacy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(None, alias="x-webhook-secret"),
    secret: Optional[str] = Query(None)
):
    """Legacy endpoint for Purchase Order generation (doc_type='po')"""
    return await generate_document_webhook("po", request, background_tasks, x_webhook_secret, secret)

@app.post("/webhook/{doc_type}")
async def generate_document_webhook(
    doc_type: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(None, alias="x-webhook-secret"),
    secret: Optional[str] = Query(None)
):
    """
    Universal webhook endpoint supporting multiple document types (e.g. /webhook/po, /webhook/invoice).
    Airtable automation sends POST with {"record_id": "rec..."}.
    """
    # 1. Validate doc_type existence
    try:
        DocumentRegistry.get(doc_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 2. Validate secret token if configured
    if settings.WEBHOOK_SECRET:
        token = x_webhook_secret or secret
        if token != settings.WEBHOOK_SECRET:
            logger.warning(f"Unauthorized webhook call for doc_type '{doc_type}'")
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # 3. Extract record_id
    try:
        body = await request.json()
    except Exception:
        body = {}

    record_id = (
        body.get("record_id")
        or body.get("recordId")
        or (body.get("record", {}).get("id") if isinstance(body.get("record"), dict) else None)
    )

    if not record_id:
        raise HTTPException(status_code=400, detail="Missing record_id in request payload")

    # 4. Schedule background generation task
    background_tasks.add_task(process_document_workflow, doc_type, record_id)

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "doc_type": doc_type,
            "record_id": record_id,
            "message": f"{doc_type.upper()} generation task scheduled successfully"
        }
    )

@app.get("/generate/{doc_type}")
@app.get("/webhook/{doc_type}")
async def generate_document_get(
    doc_type: str,
    background_tasks: BackgroundTasks,
    record_id: Optional[str] = Query(None),
    recordId: Optional[str] = Query(None),
    secret: Optional[str] = Query(None),
    format: Optional[str] = Query(None)
):
    """
    GET endpoint for Airtable Button field ('Open URL').
    When clicked, it triggers PDF generation in the background and displays a friendly success window.
    """
    # 1. Validate doc_type
    try:
        DocumentRegistry.get(doc_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 2. Validate secret token if configured
    if settings.WEBHOOK_SECRET and secret != settings.WEBHOOK_SECRET:
        logger.warning(f"Unauthorized GET call for doc_type '{doc_type}'")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    rec_id = record_id or recordId
    if not rec_id:
        return HTMLResponse(
            status_code=400,
            content="""
            <!DOCTYPE html>
            <html lang="ko">
            <head><meta charset="UTF-8"><title>오류</title></head>
            <body style="font-family:sans-serif;text-align:center;padding:50px;">
                <h2 style="color:#ef4444;">❌ Record ID 누락</h2>
                <p>URL 파라미터에 <code>record_id</code>가 제공되지 않았습니다.</p>
            </body>
            </html>
            """
        )

    # 3. Schedule background generation
    background_tasks.add_task(process_document_workflow, doc_type, rec_id)

    if format == "json":
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "doc_type": doc_type,
                "record_id": rec_id,
                "message": f"{doc_type.upper()} generation task scheduled successfully"
            }
        )

    doc_name_map = {
        "payslip": "급여명세서",
        "po": "발주서 (PO)",
    }
    doc_display = doc_name_map.get(doc_type, doc_type.upper())

    # Return friendly HTML page that closes itself
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{doc_display} 생성 중</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                color: #1e293b;
            }}
            .card {{
                background: #ffffff;
                padding: 2.5rem 2rem;
                border-radius: 1.25rem;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                text-align: center;
                max-width: 440px;
                width: 90%;
                border: 1px solid #e2e8f0;
            }}
            .icon {{
                font-size: 3.2rem;
                margin-bottom: 0.8rem;
                animation: bounce 1.5s infinite;
            }}
            @keyframes bounce {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-8px); }}
            }}
            h2 {{
                margin: 0 0 0.5rem;
                font-size: 1.35rem;
                color: #0f172a;
                font-weight: 700;
            }}
            .badge {{
                display: inline-block;
                background: #eff6ff;
                color: #2563eb;
                padding: 0.35rem 0.85rem;
                border-radius: 9999px;
                font-size: 0.85rem;
                font-weight: 600;
                margin: 0.5rem 0 1rem;
                border: 1px solid #bfdbfe;
            }}
            p {{
                margin: 0.5rem 0;
                color: #64748b;
                font-size: 0.95rem;
                line-height: 1.6;
            }}
            .record-id {{
                background: #f1f5f9;
                padding: 0.2rem 0.5rem;
                border-radius: 0.35rem;
                font-family: monospace;
                color: #334155;
            }}
            .close-btn {{
                margin-top: 1.5rem;
                display: inline-block;
                padding: 0.65rem 1.8rem;
                background: #2563eb;
                color: white;
                border-radius: 0.6rem;
                text-decoration: none;
                font-weight: 600;
                font-size: 0.9rem;
                cursor: pointer;
                border: none;
                transition: background 0.2s;
            }}
            .close-btn:hover {{
                background: #1d4ed8;
            }}
            .countdown {{
                font-size: 0.8rem;
                color: #94a3b8;
                margin-top: 0.8rem;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⚡📄</div>
            <h2>{doc_display} PDF 생성 중</h2>
            <div class="badge">Airtable 작업 시작됨</div>
            <p>
                에어테이블 레코드 <span class="record-id">{rec_id}</span>의<br>
                데이터를 읽어 PDF를 제작하고 있습니다.
            </p>
            <p style="font-size:0.9rem; color:#475569;">
                잠시 후 <strong>Paystub</strong> 필드에 파일이 자동 첨부됩니다.
            </p>
            <button class="close-btn" onclick="window.close()">창 닫기</button>
            <div class="countdown" id="cd">3초 후 자동으로 창이 닫힙니다...</div>
        </div>
        <script>
            let count = 3;
            const cdEl = document.getElementById('cd');
            const timer = setInterval(() => {{
                count--;
                if (count > 0) {{
                    cdEl.textContent = count + "초 후 자동으로 창이 닫힙니다...";
                }} else {{
                    clearInterval(timer);
                    window.close();
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/files/download/{file_name}")
async def download_file(file_name: str):
    """Public file serving endpoint for Airtable attachment crawler"""
    clean_name = sanitize_filename(file_name)
    file_path = storage_path / clean_name

    if not file_path.exists():
        fallback_path = storage_path / file_name
        if fallback_path.exists():
            file_path = fallback_path
        else:
            raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=clean_name
    )
