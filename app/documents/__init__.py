from app.documents.base import BaseDocumentGenerator
from app.documents.registry import DocumentRegistry, register_document

# Import all document generators so they self-register
from app.documents import po

__all__ = [
    "BaseDocumentGenerator",
    "DocumentRegistry",
    "register_document"
]
