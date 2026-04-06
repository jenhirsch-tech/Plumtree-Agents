"""Research and Insight Generation Agent.

Runs every Friday. Searches for future-of-work research from the past 7 days,
synthesizes findings using Claude, creates a Word document brief, saves it to
Google Drive, and notifies the team on Slack.
"""

import sys
import time
import logging
from datetime import datetime, timedelta

import schedule

from config.settings import Settings
from shared.llm import ClaudeClient
from shared.guardrails import check_banned_phrases, validate_no_fabrication_markers
from integrations.web_search import WebSearchClient
from integrations.google_drive import GoogleDriveClient
from integrations.google_sheets import ArticleHistorySheet
from integrations.slack_client import SlackNotifier
from agents.research.prompts import SYSTEM_PROMPT, SYNTHESIS_PROMPT_TEMPLATE, SO_WHAT_PROMPT
from agents.research.formatter import create_brief_document, CATEGORIES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_CONFIG = [
    "anthropic_api_key",
    "tavily_api_key",
    "slack_bot_token",
    "google_client_id",
    "google_client_secret",
    "article_history_sheet_id",
]


class ResearchAgent:
    """Semi-autonomous weekly research brief generator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = ClaudeClient(settings)
        self.search = WebSearchClient(settings)
        self.drive = GoogleDriveClient(settings)
        self.history = ArticleHistorySheet(settings)
        self.slack = SlackNotifier(settings)

    def run(self) -> None:
        """Execute the full weekly brief workflow."""
        brief_date = datetime.now().strftime("%B %d, %Y")
        brief_date_short = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Starting weekly research brief for week ending {brief_date}")

        self.slack.post_research_status(
            f"Starting weekly Future of Work research brief for week ending {brief_date}..."
        )

        # Step 1: Get previously covered articles
        logger.info("Loading article history for deduplication...")
        known_urls = self.history.get_all_urls()
        known_titles = self.history.get_all_titles()
        previously_covered = "\n".join(known_titles) if known_titles else "(none yet)"

        # Step 2: Search across all categories
        logger.info("Searching for articles across all five categories...")
        raw_results = self.search.search_all_categories()

        # Step 3: Filter out previously covered articles
        for category, articles in raw_results.items():
            raw_results[category] = [
                a for a in articles
                if a["url"] not in known_urls
                and a["title"].lower().strip() not in known_titles
            ]

        # Step 4: Synthesize each category with Claude
        logger.info("Synthesizing research findings with Claude...")
        category_content: dict[str, str] = {}
        all_new_articles: list[dict] = []

        for category in CATEGORIES:
            articles = raw_results.get(category, [])
            search_text = _format_search_results(articles)

            prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
                category=category,
                previously_covered=previously_covered,
                search_results=search_text if search_text else "(No results found this week)",
            )

            synthesis = self.llm.generate(prompt, system=SYSTEM_PROMPT)

            # Guardrail checks
            banned = check_banned_phrases(synthesis)
            if banned:
                logger.warning(f"Banned phrases found in {category}: {banned}. Requesting revision.")
                synthesis = self.llm.generate(
                    f"Revise the following text to remove these phrases: {banned}.\n\n{synthesis}",
                    system=SYSTEM_PROMPT,
                )

            fabrication_warnings = validate_no_fabrication_markers(synthesis)
            if fabrication_warnings:
                logger.warning(f"Fabrication markers in {category}: {fabrication_warnings}")

            category_content[category] = synthesis

            # Track new articles for dedup
            for article in articles:
                all_new_articles.append({
                    "title": article["title"],
                    "url": article["url"],
                    "source": article.get("source", ""),
                    "category": category,
                })

        # Step 5: Generate "The So What This Week"
        logger.info("Generating synthesis paragraph...")
        all_summaries = "\n\n".join(
            f"### {cat}\n{content}" for cat, content in category_content.items()
        )
        so_what = self.llm.generate(
            SO_WHAT_PROMPT.format(all_summaries=all_summaries),
            system=SYSTEM_PROMPT,
        )

        # Guardrail check on so_what
        banned = check_banned_phrases(so_what)
        if banned:
            so_what = self.llm.generate(
                f"Revise to remove these phrases: {banned}.\n\n{so_what}",
                system=SYSTEM_PROMPT,
            )

        # Step 6: Create Word document
        logger.info("Creating Word document...")
        doc_bytes = create_brief_document(brief_date, category_content, so_what)
        filename = f"Plumtree_FoW_Brief_{brief_date_short}.docx"

        # Step 7: Upload to Google Drive
        logger.info(f"Uploading {filename} to Google Drive...")
        file_meta = self.drive.upload_bytes(
            doc_bytes,
            filename,
            self.settings.research_brief_folder_id,
        )
        drive_link = file_meta.get("webViewLink", "")
        logger.info(f"Uploaded: {drive_link}")

        # Step 8: Record articles in history sheet
        logger.info(f"Recording {len(all_new_articles)} articles in history sheet...")
        self.history.add_articles(all_new_articles, brief_date_short)

        # Step 9: Notify Slack
        logger.info("Posting to Slack...")
        self.slack.post_research_brief_ready(drive_link, brief_date)

        logger.info("Weekly research brief complete.")


def _format_search_results(articles: list[dict]) -> str:
    """Format raw search results into text for the synthesis prompt."""
    if not articles:
        return ""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(
            f"[{i}] {a['title']}\n"
            f"    URL: {a['url']}\n"
            f"    Source: {a.get('source', 'Unknown')}\n"
            f"    Content: {a.get('content', '(no preview)')[:500]}\n"
        )
    return "\n".join(parts)


def run_scheduled():
    """Run the agent on a Friday schedule."""
    settings = Settings.load()
    missing = settings.validate(REQUIRED_CONFIG)
    if missing:
        logger.error(f"Missing required configuration: {missing}")
        logger.error("Please set these in your .env file. See .env.example.")
        sys.exit(1)

    agent = ResearchAgent(settings)

    # Schedule for every Friday at 8:00 AM
    schedule.every().friday.at("08:00").do(agent.run)
    logger.info("Research agent scheduled. Running every Friday at 08:00.")
    logger.info("Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(60)


def run_now():
    """Run the agent immediately (for testing or manual trigger)."""
    settings = Settings.load()
    missing = settings.validate(REQUIRED_CONFIG)
    if missing:
        logger.error(f"Missing required configuration: {missing}")
        logger.error("Please set these in your .env file. See .env.example.")
        sys.exit(1)

    agent = ResearchAgent(settings)
    agent.run()


def main():
    """Entry point — pass --now to run immediately, otherwise starts scheduler."""
    if "--now" in sys.argv:
        run_now()
    else:
        run_scheduled()


if __name__ == "__main__":
    main()
