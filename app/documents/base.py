from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseDocumentGenerator(ABC):
    """
    Abstract base class for document generators.
    To add a new PDF type (e.g. invoice, contract, settlement statement),
    inherit from this class and implement the required methods.
    """
    doc_type: str = "base"
    template_name: str = "template.html"
    css_name: str = "style.css"

    @abstractmethod
    def fetch_data(self, record_id: str) -> Dict[str, Any]:
        """
        Fetch record and related records from Airtable,
        perform calculations, and format data for HTML template rendering.
        """
        pass

    @abstractmethod
    def get_output_filename(self, data: Dict[str, Any], record_id: str) -> str:
        """
        Generate a sanitized filename for the generated PDF (e.g. ZOO_Korea_김애정_2026-07.pdf).
        """
        pass

    @abstractmethod
    def update_airtable_attachment(self, record_id: str, file_url: str, filename: str) -> Dict[str, Any]:
        """
        Update the corresponding attachment field in Airtable with the generated PDF URL,
        and optionally reset triggers/update statuses.
        """
        pass
