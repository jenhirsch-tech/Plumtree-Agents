"""Google Slides integration for proposal creation."""

from googleapiclient.discovery import build

from config.settings import Settings
from integrations.google_auth import get_credentials


class GoogleSlidesClient:
    """Read and update Google Slides presentations."""

    def __init__(self, settings: Settings):
        creds = get_credentials(settings)
        self.slides_service = build("slides", "v1", credentials=creds)

    def get_presentation(self, presentation_id: str) -> dict:
        """Read a presentation's full content."""
        return self.slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()

    def batch_update(self, presentation_id: str, requests: list[dict]) -> dict:
        """Apply a batch of update requests to a presentation."""
        body = {"requests": requests}
        return self.slides_service.presentations().batchUpdate(
            presentationId=presentation_id, body=body
        ).execute()

    def replace_text(self, presentation_id: str, replacements: dict[str, str]) -> dict:
        """Replace placeholder text across all slides.

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
        return self.batch_update(presentation_id, requests)
