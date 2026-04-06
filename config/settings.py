"""Central configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    """All configuration for Plumtree agents, loaded from .env file."""

    # Anthropic
    anthropic_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Slack
    slack_bot_token: str = ""
    slack_channel_research: str = "C06KLD36J9H"
    slack_channel_proposal_sow: str = "C0ARCMZRVUH"

    # Web search
    tavily_api_key: str = ""

    # Google Drive folder IDs
    research_brief_folder_id: str = "1XZzSlFw0zR9MLZBnHiudIYkje3vDhpWq"
    proposal_sow_folder_id: str = "1NBoC0_qEuBK_Rl53nZSCHqtIrCiZVk8w"

    # Google template IDs
    proposal_template_id: str = "18ClUVBfYgmR1vbs68RNVRhW0GEVsZUSkqx9YQDTp24Y"
    sow_template_id: str = "1QvUtHjfG8w-12-zeH45T3H595OuVxT9qr0aYvuAMqPg"

    # Article history Google Sheet ID
    article_history_sheet_id: str = ""

    # Paths
    token_path: str = field(default_factory=lambda: str(Path.home() / ".plumtree" / "token.json"))

    @classmethod
    def load(cls, env_path: str | None = None) -> "Settings":
        """Load settings from environment / .env file."""
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
            slack_channel_research=os.getenv("SLACK_CHANNEL_RESEARCH", "C06KLD36J9H"),
            slack_channel_proposal_sow=os.getenv("SLACK_CHANNEL_PROPOSAL_SOW", "C0ARCMZRVUH"),
            tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
            research_brief_folder_id=os.getenv("RESEARCH_BRIEF_FOLDER_ID", "1XZzSlFw0zR9MLZBnHiudIYkje3vDhpWq"),
            proposal_sow_folder_id=os.getenv("PROPOSAL_SOW_FOLDER_ID", "1NBoC0_qEuBK_Rl53nZSCHqtIrCiZVk8w"),
            proposal_template_id=os.getenv("PROPOSAL_TEMPLATE_ID", "18ClUVBfYgmR1vbs68RNVRhW0GEVsZUSkqx9YQDTp24Y"),
            sow_template_id=os.getenv("SOW_TEMPLATE_ID", "1QvUtHjfG8w-12-zeH45T3H595OuVxT9qr0aYvuAMqPg"),
            article_history_sheet_id=os.getenv("ARTICLE_HISTORY_SHEET_ID", ""),
            token_path=os.getenv("GOOGLE_TOKEN_PATH", str(Path.home() / ".plumtree" / "token.json")),
        )

    def validate(self, required_keys: list[str] | None = None) -> list[str]:
        """Return list of missing required config keys."""
        if required_keys is None:
            required_keys = ["anthropic_api_key"]
        return [k for k in required_keys if not getattr(self, k, "")]
