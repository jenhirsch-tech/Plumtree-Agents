"""Google Docs integration for SOW creation."""

from googleapiclient.discovery import build

from config.settings import Settings
from integrations.google_auth import get_credentials


class GoogleDocsClient:
    """Read and update Google Docs documents."""

    def __init__(self, settings: Settings):
        creds = get_credentials(settings)
        self.docs_service = build("docs", "v1", credentials=creds)

    def get_document(self, document_id: str) -> dict:
        """Read a document's full content."""
        return self.docs_service.documents().get(documentId=document_id).execute()

    def get_document_text(self, document_id: str) -> str:
        """Extract plain text from a Google Doc."""
        doc = self.get_document(document_id)
        text_parts = []
        for element in doc.get("body", {}).get("content", []):
            paragraph = element.get("paragraph")
            if paragraph:
                for elem in paragraph.get("elements", []):
                    text_run = elem.get("textRun")
                    if text_run:
                        text_parts.append(text_run.get("content", ""))
        return "".join(text_parts)

    def batch_update(self, document_id: str, requests: list[dict]) -> dict:
        """Apply a batch of update requests to a document."""
        body = {"requests": requests}
        return self.docs_service.documents().batchUpdate(
            documentId=document_id, body=body
        ).execute()

    def replace_text(self, document_id: str, replacements: dict[str, str]) -> dict:
        """Replace placeholder text throughout a document.

        replacements: mapping of {{PLACEHOLDER}} -> replacement text
        """
        requests = []
        for placeholder, replacement in replacements.items():
            requests.append({
                "replaceAllText": {
                    "containsText": {"text": placeholder, "matchCase": True},
                    "replaceText": replacement,
                }
            })
        return self.batch_update(document_id, requests)

    def insert_text(self, document_id: str, index: int, text: str) -> dict:
        """Insert text at a specific index in the document."""
        requests = [{"insertText": {"location": {"index": index}, "text": text}}]
        return self.batch_update(document_id, requests)
