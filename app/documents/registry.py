import logging
from typing import Dict, Type, List
from app.documents.base import BaseDocumentGenerator

logger = logging.getLogger(__name__)

class DocumentRegistry:
    _generators: Dict[str, BaseDocumentGenerator] = {}

    @classmethod
    def register(cls, doc_type: str):
        """Decorator to register a document generator class"""
        def decorator(subclass: Type[BaseDocumentGenerator]):
            instance = subclass()
            instance.doc_type = doc_type
            cls._generators[doc_type.lower()] = instance
            logger.info(f"Registered document generator for doc_type: '{doc_type}' ({subclass.__name__})")
            return subclass
        return decorator

    @classmethod
    def get(cls, doc_type: str) -> BaseDocumentGenerator:
        """Get document generator instance by doc_type key"""
        normalized = doc_type.lower().strip()
        if normalized not in cls._generators:
            available = list(cls._generators.keys())
            raise ValueError(f"Unknown doc_type '{doc_type}'. Available document types: {available}")
        return cls._generators[normalized]

    @classmethod
    def list_types(cls) -> List[str]:
        """Return list of supported document type keys"""
        return list(cls._generators.keys())

register_document = DocumentRegistry.register
