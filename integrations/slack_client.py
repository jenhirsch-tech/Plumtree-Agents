"""Slack integration for status notifications."""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config.settings import Settings


class SlackNotifier:
    """Post status messages to Plumtree Slack channels."""

    def __init__(self, settings: Settings):
        self.client = WebClient(token=settings.slack_bot_token)
        self.channel_research = settings.slack_channel_research
        self.channel_proposal_sow = settings.slack_channel_proposal_sow

    def post_research_brief_ready(self, drive_link: str, brief_date: str) -> None:
        """Notify #ops-knowledge-share that the weekly brief is ready."""
        text = (
            f"The weekly Future of Work research brief for the week ending "
            f"{brief_date} is ready.\n\n"
            f"<{drive_link}|View the brief in Google Drive>"
        )
        self._post(self.channel_research, text)

    def post_research_status(self, message: str) -> None:
        """Post a progress update to #ops-knowledge-share."""
        self._post(self.channel_research, message)

    def post_proposal_status(self, message: str) -> None:
        """Post a progress update to #agent-proposal-sow."""
        self._post(self.channel_proposal_sow, message)

    def post_proposal_ready(self, client_name: str, drive_link: str) -> None:
        """Notify that a proposal draft is ready for review."""
        text = (
            f"Proposal draft for *{client_name}* is ready for review.\n\n"
            f"<{drive_link}|View the proposal in Google Drive>"
        )
        self._post(self.channel_proposal_sow, text)

    def post_sow_ready(self, client_name: str, drive_link: str) -> None:
        """Notify that a SOW draft is ready for review."""
        text = (
            f"SOW draft for *{client_name}* is ready for review.\n\n"
            f"<{drive_link}|View the SOW in Google Drive>"
        )
        self._post(self.channel_proposal_sow, text)

    def _post(self, channel: str, text: str) -> None:
        """Post a message to a Slack channel."""
        try:
            self.client.chat_postMessage(channel=channel, text=text)
        except SlackApiError as e:
            print(f"[Slack error] {e.response['error']}: {text[:100]}...")
            raise
