import os
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
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
        file_url = f"{settings.BASE_URL.rstrip('/')}/files/download/{urllib.parse.quote(filename)}"
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
