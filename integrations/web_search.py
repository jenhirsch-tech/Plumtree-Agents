"""Web search integration using Tavily for research gathering."""

from datetime import datetime, timedelta

from tavily import TavilyClient

from config.settings import Settings

# Priority sources for research
PRIORITY_DOMAINS = [
    "hbr.org",
    "sloanreview.mit.edu",
    "mckinsey.com",
    "deloitte.com",
    "accenture.com",
    "sypartners.com",
    "bain.com",
    "ey.com",
    "kpmg.com",
    "inc.com",
    "fortune.com",
    "fastcompany.com",
    "nytimes.com",
    "wsj.com",
    "journals.aom.org",
    "psycnet.apa.org",
    "nature.com",
    "sciencedirect.com",
]


class WebSearchClient:
    """Search the web for recent articles on future of work topics."""

    def __init__(self, settings: Settings):
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    def search_category(self, category: str, query: str, max_results: int = 10) -> list[dict]:
        """Search for articles in a specific category from the past 7 days.

        Returns list of dicts with: title, url, content, published_date, source
        """
        results = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=PRIORITY_DOMAINS,
            days=7,
        )
        articles = []
        for result in results.get("results", []):
            articles.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "source": _extract_source(result.get("url", "")),
                "category": category,
            })
        return articles

    def search_all_categories(self) -> dict[str, list[dict]]:
        """Run searches across all five research categories."""
        queries = {
            "Teams and Teaming": (
                "teams teaming cross-functional collaboration team effectiveness "
                "distributed teams high-performing teams organizational psychology"
            ),
            "Organization Systems": (
                "organization design organizational structure systems design "
                "decision making work design organizational effectiveness"
            ),
            "Culture": (
                "organizational culture psychological safety workplace culture "
                "belonging trust high-performing culture"
            ),
            "Leadership": (
                "leadership practices evidence-based leadership leadership research "
                "leadership development executive leadership"
            ),
            "AI and the Future of Work": (
                "AI workplace productivity AI teams AI organizational efficiency "
                "artificial intelligence work transformation practical AI"
            ),
        }
        results = {}
        for category, query in queries.items():
            results[category] = self.search_category(category, query)
        return results


def _extract_source(url: str) -> str:
    """Extract a readable source name from a URL."""
    domain_map = {
        "hbr.org": "Harvard Business Review",
        "sloanreview.mit.edu": "MIT Sloan Management Review",
        "mckinsey.com": "McKinsey & Company",
        "deloitte.com": "Deloitte",
        "accenture.com": "Accenture",
        "sypartners.com": "SY Partners",
        "bain.com": "Bain & Company",
        "ey.com": "Ernst & Young",
        "kpmg.com": "KPMG",
        "inc.com": "INC",
        "fortune.com": "Fortune",
        "fastcompany.com": "Fast Company",
        "nytimes.com": "New York Times",
        "wsj.com": "Wall Street Journal",
        "journals.aom.org": "Academy of Management",
    }
    for domain, name in domain_map.items():
        if domain in url:
            return name
    # Fallback: extract domain
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return url
