"""One-off weekly report generator using Claude API + pre-gathered search results.

Bypasses Tavily/Google/Slack dependencies — writes the .docx locally.
"""

import os
import sys
import logging
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from shared.llm import ClaudeClient
from shared.guardrails import check_banned_phrases, validate_no_fabrication_markers
from agents.research.prompts import SYSTEM_PROMPT, SYNTHESIS_PROMPT_TEMPLATE, SO_WHAT_PROMPT
from agents.research.formatter import create_brief_document, CATEGORIES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------- Pre-gathered search results (week ending April 6, 2026) ----------

SEARCH_RESULTS = {
    "Teams and Teaming": [
        {
            "title": "Deloitte Report: Human Skills Drive High-Performing Teams in the AI Era",
            "url": "https://www.deloitte.com/us/en/about/press-room/high-performing-teams.html",
            "source": "Deloitte",
            "content": (
                "A January 2026 Deloitte study of 1,394 employees found that human capabilities — "
                "curiosity, resilience, divergent thinking, informed agility, connected teaming, and "
                "emotional and social intelligence — are critical in determining whether teams thrive. "
                "High-performing teams use AI more often than other teams and use it to bring out the "
                "best in their people, reporting higher-quality experiences that boost efficiency (93% vs. 77%), "
                "problem-solving (88% vs. 71%), and collaboration (79% vs. 57%). Members of high-performing "
                "teams are 2.3x as likely to feel trusted by their team leader, 2.3x as likely to feel "
                "respected and appreciated by peers, and nearly 1.5x more likely to report feeling included, "
                "with emotional and social intelligence cited as the top success factor."
            ),
        },
        {
            "title": "Human capabilities are at the heart of high-performing teams",
            "url": "https://www.deloitte.com/us/en/insights/topics/talent/building-high-performing-teams.html",
            "source": "Deloitte Insights",
            "content": (
                "Deep dive into the Deloitte high-performing teams study. Teams that consistently meet or "
                "exceed expectations share specific traits: they invest in trust, practice connected teaming, "
                "and use AI as a complement to human judgment rather than a replacement. The report argues "
                "that the most important team capability in the AI era is emotional and social intelligence."
            ),
        },
        {
            "title": "Flubber teams: The emergence of dynamic platform-enabled teams in business organizations",
            "url": "https://www.sciencedirect.com/science/article/pii/S0148296325006186",
            "source": "Journal of Business Research (ScienceDirect)",
            "content": (
                "Introduces 'flubber teaming' — teams that dynamically change shape, form, hierarchy, "
                "and properties in response to shifting demands. Platform-enabled team structures allow "
                "large organizations to reconfigure talent rapidly, moving beyond static org charts toward "
                "fluid, project-based configurations. The research examines how digital platforms mediate "
                "team formation and dissolution cycles."
            ),
        },
        {
            "title": "AI-teaming: Redefining collaboration in the digital era",
            "url": "https://www.sciencedirect.com/science/article/pii/S2352250X24000502",
            "source": "Current Opinion in Psychology (ScienceDirect)",
            "content": (
                "Human-AI teams frequently underperform due to poor team cognition and mutual understanding. "
                "The paper argues that effective AI-teaming requires rethinking how we design roles, "
                "communication protocols, and shared mental models when one team member is a machine. "
                "Standard team science frameworks need updating for hybrid human-AI contexts."
            ),
        },
    ],
    "Organization Systems": [
        {
            "title": "How One Company Achieved a Bold Transformation Despite Major Unknowns",
            "url": "https://hbr.org/2026/01/how-one-company-achieved-a-bold-transformation-despite-major-unknowns",
            "source": "Harvard Business Review",
            "content": (
                "HBR case study of a company navigating large-scale organizational transformation with "
                "significant uncertainty. The piece argues that successful transformation requires leaders "
                "to embrace ambiguity, build adaptive capacity, and resist the temptation to over-plan. "
                "Instead of trying to eliminate unknowns before acting, effective transformers learn by doing."
            ),
        },
        {
            "title": "2026 Life sciences outlook",
            "url": "https://www.deloitte.com/us/en/insights/industry/health-care/life-sciences-and-health-care-industry-outlooks/2026-life-sciences-executive-outlook.html",
            "source": "Deloitte Insights",
            "content": (
                "Nearly half of surveyed life sciences leaders (48%) identified accelerated digital "
                "transformation as having substantial impact in 2026 — up significantly from 2025. "
                "30% cited agentic AI as a key trend. Only 22% have successfully scaled AI, and just "
                "9% reported achieving significant returns. More than 75% of biopharma and medtech "
                "executives are confident in their organizations' 2026 financial outlook, though only "
                "41% feel optimistic about the global economy."
            ),
        },
        {
            "title": "Against the odds: How life sciences companies excel in large transformations",
            "url": "https://www.mckinsey.com/industries/life-sciences/our-insights/against-the-odds-how-life-sciences-companies-excel-in-large-transformations",
            "source": "McKinsey & Company",
            "content": (
                "In the past five years, 26 of the 30 largest global pharmaceutical companies have "
                "announced major transformations — restructuring organizations, overhauling operations, "
                "and streamlining business units. The article examines what differentiates successful "
                "transformations from failures in life sciences."
            ),
        },
        {
            "title": "Simplification for success: Rewiring the biopharma operating model",
            "url": "https://www.mckinsey.com/industries/life-sciences/our-insights/simplification-for-success-rewiring-the-biopharma-operating-model",
            "source": "McKinsey & Company",
            "content": (
                "Some biopharma organizations have simplified their structures by eliminating duplication "
                "between global, regional, and local layers. One company consolidated into just two regions "
                "— international and US — transitioning to an above-market vs. in-market structure, which "
                "brought decisions closer to customers, reduced bureaucracy, and gave employees clearer roles."
            ),
        },
        {
            "title": "Towards enterprise-wide pharma 4.0 adoption",
            "url": "https://www.sciencedirect.com/science/article/pii/S2468227625002406",
            "source": "ScienceDirect",
            "content": (
                "The adoption of Industry 4.0 in pharma (Pharma 4.0) brings significant benefits — "
                "operational efficiency, regulatory compliance, and quality improvements. The paper examines "
                "enterprise-wide adoption challenges and the organizational changes required."
            ),
        },
    ],
    "Culture": [
        {
            "title": "To Change Company Culture, Start with One High-Impact Behavior",
            "url": "https://hbr.org/2026/01/to-change-company-culture-start-with-one-high-impact-behavior",
            "source": "Harvard Business Review",
            "content": (
                "Behavior is at the heart of nearly every challenge in the workplace, from leadership and "
                "fair decisions to high performance and AI adoption. Instead of trying to change everything "
                "at once, the most effective culture change begins with identifying and shifting one "
                "high-impact behavior that cascades through the organization."
            ),
        },
        {
            "title": "How Leaders Can Build a High-Agency Culture",
            "url": "https://hbr.org/2026/03/how-leaders-can-build-a-high-agency-culture",
            "source": "Harvard Business Review",
            "content": (
                "The most effective leaders deliberately cultivate 'high agency' — the capacity to act "
                "despite ambiguity by choosing beliefs that expand what people notice, expect, and attempt. "
                "This replaces cultures of blame and helplessness with cultures oriented toward experimentation, "
                "problem solving, and progress. The article provides a practical framework for building agency."
            ),
        },
        {
            "title": "2026 Global Human Capital Trends",
            "url": "https://www.deloitte.com/us/en/insights/topics/talent/human-capital-trends.html",
            "source": "Deloitte Insights",
            "content": (
                "Organizations need to redesign work to harness human-machine synergy — moving beyond having "
                "humans and machines work side by side. This includes rethinking culture, decision rights, "
                "and trust in data itself. The report emphasizes that the human edge becomes the key "
                "differentiator as AI accelerates change."
            ),
        },
        {
            "title": "Agentic organizations: Turning AI into business value",
            "url": "https://www.mckinsey.com/capabilities/people-and-organizational-performance/our-insights/ai-is-everywhere-the-agentic-organization-isnt-yet",
            "source": "McKinsey & Company",
            "content": (
                "Life sciences and pharma companies are envisioning squads of AI agents in R&D, though "
                "researchers and scientists won't be replaced in the org chart — they'll be able to "
                "supercharge the speed at which they innovate. The piece examines how organizations are "
                "building cultures that integrate AI agents alongside human workers."
            ),
        },
    ],
    "Leadership": [
        {
            "title": "9 Trends Shaping Work in 2026 and Beyond",
            "url": "https://hbr.org/2026/02/9-trends-shaping-work-in-2026-and-beyond",
            "source": "Harvard Business Review",
            "content": (
                "CEO expectations for AI-driven growth remain high in 2026, but workforces grapple with "
                "the more sober reality of current AI performance. Only 1 in 50 AI investments deliver "
                "transformational value, and only 1 in 5 delivers any measurable ROI. The article examines "
                "nine key trends shaping how work and leadership are evolving."
            ),
        },
        {
            "title": "The art of 21st-century leadership: From succession planning to building a leadership factory",
            "url": "https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/our-insights/the-art-of-21st-century-leadership-from-succession-planning-to-building-a-leadership-factory",
            "source": "McKinsey & Company",
            "content": (
                "CEOs and leadership teams cite talent and the leadership team as the biggest hurdles, "
                "specifically citing an urgent need to build leadership capabilities — not only to manage "
                "through today's disruptions but also to fortify against tomorrow's inevitable shifts. "
                "The article argues for moving from succession planning to building a leadership factory."
            ),
        },
        {
            "title": "How Leaders Face the Future of Work",
            "url": "https://sloanreview.mit.edu/article/how-leaders-face-the-future-of-work/",
            "source": "MIT Sloan Management Review",
            "content": (
                "Lynda Gratton examines how leaders are navigating the future of work, emphasizing the need "
                "for treating decision-making as a strategic discipline and intentionally designing how "
                "humans and AI share judgment and accountability to maintain trust and protect human agency."
            ),
        },
        {
            "title": "Why Digital Dexterity Is Key to Transformation",
            "url": "https://sloanreview.mit.edu/article/why-digital-dexterity-is-key-to-transformation/",
            "source": "MIT Sloan Management Review",
            "content": (
                "Leaders are building a digitally dexterous workforce — one that is both willing and able "
                "to take advantage of new technologies such as generative AI to deliver innovative solutions. "
                "Learning should be integrated into how work gets done day to day, which will define the "
                "learning organizations of the future."
            ),
        },
    ],
    "AI and the Future of Work": [
        {
            "title": "The future of pharmaceuticals: Artificial intelligence in drug discovery and development",
            "url": "https://www.sciencedirect.com/science/article/pii/S2095177925000656",
            "source": "ScienceDirect",
            "content": (
                "AI is revolutionizing traditional drug discovery and development models by enhancing "
                "efficiency, accuracy, and success rates while shortening timelines and reducing costs. "
                "AI combined with ML and deep learning has demonstrated significant advancements in drug "
                "characterization, target discovery, small molecule design, and clinical trial acceleration."
            ),
        },
        {
            "title": "Generative AI in the pharmaceutical industry: Moving from hype to reality",
            "url": "https://www.mckinsey.com/industries/life-sciences/our-insights/generative-ai-in-the-pharmaceutical-industry-moving-from-hype-to-reality",
            "source": "McKinsey & Company",
            "content": (
                "The life sciences industry stands on the brink of a revolution, potentially unlocking "
                "$5-7 billion in value through strategic application of AI, particularly Generative AI. "
                "Pharma R&D alone could account for 30-40% of the potential value. The industry is entering "
                "a period of purposeful transformation where discipline and innovation must coexist."
            ),
        },
        {
            "title": "Generative AI to Reshape the Future of Life Sciences",
            "url": "https://www.deloitte.com/us/en/Industries/life-sciences-health-care/articles/value-of-genai-in-pharma.html",
            "source": "Deloitte",
            "content": (
                "Generative AI is reshaping life sciences, with 30% of leaders citing agentic AI as a key "
                "2026 trend. Despite enthusiasm, only 22% have scaled AI and just 9% report significant "
                "returns. The industry is moving beyond hype toward measurable productivity."
            ),
        },
        {
            "title": "Reimagined: Learning & development in the future of work",
            "url": "https://www.mckinsey.com/featured-insights/people-in-progress/reimagined-learning-and-development-in-the-future-of-work",
            "source": "McKinsey & Company",
            "content": (
                "Employees increasingly look for growth to be a natural part of their work experience "
                "rather than an added obligation. This creates an opportunity to weave development into "
                "everyday experiences. Specialized personnel in scientific data science are essential for "
                "transformation to smart manufacturing. Privacy, cybersecurity, and AI-dependent unemployment "
                "require proper regulation."
            ),
        },
    ],
}


def run():
    """Run the synthesis and generate the Word document."""
    # Build a minimal settings object
    class MinimalSettings:
        anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]

    settings = MinimalSettings()
    llm = ClaudeClient(settings)

    brief_date = "April 6, 2026"
    brief_date_short = "2026-04-06"

    category_content: dict[str, str] = {}

    for category in CATEGORIES:
        articles = SEARCH_RESULTS.get(category, [])
        search_text = _format_search_results(articles)

        prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
            category=category,
            previously_covered="(none yet)",
            search_results=search_text if search_text else "(No results found this week)",
        )

        logger.info(f"Synthesizing: {category}...")
        synthesis = llm.generate(prompt, system=SYSTEM_PROMPT)

        # Guardrail checks
        banned = check_banned_phrases(synthesis)
        if banned:
            logger.warning(f"Banned phrases in {category}: {banned}. Requesting revision.")
            synthesis = llm.generate(
                f"Revise the following text to remove these phrases: {banned}.\n\n{synthesis}",
                system=SYSTEM_PROMPT,
            )

        fabrication_warnings = validate_no_fabrication_markers(synthesis)
        if fabrication_warnings:
            logger.warning(f"Fabrication markers in {category}: {fabrication_warnings}")

        category_content[category] = synthesis

    # Generate "The So What This Week"
    logger.info("Generating 'The So What This Week'...")
    all_summaries = "\n\n".join(
        f"### {cat}\n{content}" for cat, content in category_content.items()
    )
    so_what = llm.generate(
        SO_WHAT_PROMPT.format(all_summaries=all_summaries),
        system=SYSTEM_PROMPT,
    )

    banned = check_banned_phrases(so_what)
    if banned:
        so_what = llm.generate(
            f"Revise to remove these phrases: {banned}.\n\n{so_what}",
            system=SYSTEM_PROMPT,
        )

    # Create Word document
    logger.info("Creating Word document...")
    doc_bytes = create_brief_document(brief_date, category_content, so_what)
    filename = f"Plumtree_FoW_Brief_{brief_date_short}.docx"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "wb") as f:
        f.write(doc_bytes)

    logger.info(f"Report saved to: {output_path}")
    print(f"\nWeekly research brief saved: {filename}")


def _format_search_results(articles: list[dict]) -> str:
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


if __name__ == "__main__":
    run()
