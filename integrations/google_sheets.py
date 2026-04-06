"""Google Sheets integration for article deduplication tracking."""

from datetime import datetime

from googleapiclient.discovery import build

from config.settings import Settings
from integrations.google_auth import get_credentials

SHEET_RANGE = "Sheet1"
HEADER_ROW = ["Title", "URL", "Source", "Category", "Date Added", "Brief Date"]


class ArticleHistorySheet:
    """Track previously included articles in a Google Sheet to prevent repeats."""

    def __init__(self, settings: Settings):
        creds = get_credentials(settings)
        self.service = build("sheets", "v4", credentials=creds)
        self.sheet_id = settings.article_history_sheet_id
        self._ensure_headers()

    def _ensure_headers(self):
        """Create header row if the sheet is empty."""
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=f"{SHEET_RANGE}!A1:F1",
        ).execute()
        values = result.get("values", [])
        if not values:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_RANGE}!A1:F1",
                valueInputOption="RAW",
                body={"values": [HEADER_ROW]},
            ).execute()

    def get_all_urls(self) -> set[str]:
        """Return all URLs already recorded."""
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=f"{SHEET_RANGE}!B:B",
        ).execute()
        values = result.get("values", [])
        # Skip header row
        return {row[0] for row in values[1:] if row}

    def get_all_titles(self) -> set[str]:
        """Return all titles already recorded (for fuzzy dedup)."""
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=f"{SHEET_RANGE}!A:A",
        ).execute()
        values = result.get("values", [])
        return {row[0].lower().strip() for row in values[1:] if row}

    def add_articles(self, articles: list[dict], brief_date: str) -> None:
        """Record articles to the history sheet.

        Each article dict should have: title, url, source, category.
        """
        rows = []
        for article in articles:
            rows.append([
                article.get("title", ""),
                article.get("url", ""),
                article.get("source", ""),
                article.get("category", ""),
                datetime.now().strftime("%Y-%m-%d"),
                brief_date,
            ])
        if rows:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_RANGE}!A:F",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()
