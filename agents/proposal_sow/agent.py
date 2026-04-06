"""Proposal-to-SOW Automation Agent.

Human-in-the-loop workflow with explicit approval gates.
Jen provides discovery notes, the agent drafts proposals and SOWs,
and nothing advances without explicit approval.
"""

import sys
import logging

from config.settings import Settings
from shared.llm import ClaudeClient
from shared.guardrails import check_banned_phrases, validate_no_fabrication_markers
from integrations.google_drive import GoogleDriveClient
from integrations.google_slides import GoogleSlidesClient
from integrations.google_docs import GoogleDocsClient
from integrations.slack_client import SlackNotifier
from agents.proposal_sow.workflow import (
    Engagement,
    WorkflowState,
    WorkflowStore,
    WorkflowError,
)
from agents.proposal_sow.prompts import (
    SYSTEM_PROMPT,
    PROPOSAL_DRAFT_PROMPT,
    PROPOSAL_REVISION_PROMPT,
    SOW_MAPPING_PROMPT,
    SOW_REVISION_PROMPT,
    OPEN_QUESTIONS_PROMPT,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_CONFIG = [
    "anthropic_api_key",
    "slack_bot_token",
    "google_client_id",
    "google_client_secret",
]


class ProposalSOWAgent:
    """Interactive agent for creating proposals and SOWs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = ClaudeClient(settings)
        self.drive = GoogleDriveClient(settings)
        self.slides = GoogleSlidesClient(settings)
        self.docs = GoogleDocsClient(settings)
        self.slack = SlackNotifier(settings)
        self.store = WorkflowStore()

    # ── Phase 1: Proposal ──────────────────────────────────────────────

    def start_engagement(self, client_name: str, discovery_notes: str) -> Engagement:
        """Begin a new engagement from discovery notes."""
        engagement = Engagement(
            client_name=client_name,
            discovery_notes=discovery_notes,
        )
        self.store.save(engagement)
        logger.info(f"New engagement created: {client_name}")

        self.slack.post_proposal_status(
            f"New engagement intake received for *{client_name}*. Starting proposal draft."
        )
        return engagement

    def draft_proposal(self, client_name: str) -> str:
        """Create the initial proposal draft."""
        engagement = self._load_engagement(client_name)
        engagement.transition_to(WorkflowState.PROPOSAL_DRAFT_IN_PROGRESS)
        self.store.save(engagement)

        # Copy the proposal template
        logger.info("Copying proposal template...")
        copy = self.drive.copy_file(
            source_file_id=self.settings.proposal_template_id,
            new_name=f"Proposal — {client_name}",
            folder_id=self.settings.proposal_sow_folder_id,
        )
        engagement.proposal_id = copy["id"]
        engagement.proposal_link = copy.get("webViewLink", "")

        # Generate proposal content with Claude
        logger.info("Generating proposal draft...")
        prompt = PROPOSAL_DRAFT_PROMPT.format(
            client_name=client_name,
            discovery_notes=engagement.discovery_notes,
        )
        draft = self.llm.generate(prompt, system=SYSTEM_PROMPT)

        # Guardrail checks
        banned = check_banned_phrases(draft)
        if banned:
            logger.warning(f"Removing banned phrases: {banned}")
            draft = self.llm.generate(
                f"Revise to remove these phrases: {banned}.\n\n{draft}",
                system=SYSTEM_PROMPT,
            )

        fabrication_warnings = validate_no_fabrication_markers(draft)
        if fabrication_warnings:
            logger.warning(f"Fabrication warnings: {fabrication_warnings}")

        # Identify open questions
        questions_prompt = OPEN_QUESTIONS_PROMPT.format(
            discovery_notes=engagement.discovery_notes,
            current_draft=draft,
        )
        questions = self.llm.generate(questions_prompt, system=SYSTEM_PROMPT)
        engagement.open_questions = [q.strip() for q in questions.split("\n") if q.strip()]

        # Move to review
        engagement.transition_to(WorkflowState.PROPOSAL_UNDER_REVIEW)
        self.store.save(engagement)

        self.slack.post_proposal_ready(client_name, engagement.proposal_link)

        return draft

    def revise_proposal(self, client_name: str, feedback: str, current_draft: str) -> str:
        """Revise the proposal based on Jen's feedback."""
        engagement = self._load_engagement(client_name)

        if engagement.state != WorkflowState.PROPOSAL_UNDER_REVIEW:
            raise WorkflowError(
                f"Proposal must be under review to revise. Current state: {engagement.state.value}"
            )

        engagement.add_review_note(feedback)
        engagement.transition_to(WorkflowState.PROPOSAL_DRAFT_IN_PROGRESS)

        prompt = PROPOSAL_REVISION_PROMPT.format(
            client_name=client_name,
            current_draft=current_draft,
            feedback=feedback,
        )
        revised = self.llm.generate(prompt, system=SYSTEM_PROMPT)

        # Guardrail check
        banned = check_banned_phrases(revised)
        if banned:
            revised = self.llm.generate(
                f"Revise to remove these phrases: {banned}.\n\n{revised}",
                system=SYSTEM_PROMPT,
            )

        engagement.transition_to(WorkflowState.PROPOSAL_UNDER_REVIEW)
        self.store.save(engagement)

        self.slack.post_proposal_status(
            f"Revised proposal for *{client_name}* is ready for another review."
        )

        return revised

    def approve_proposal(self, client_name: str, message: str) -> bool:
        """Check if the message contains explicit SOW approval."""
        engagement = self._load_engagement(client_name)

        if engagement.state != WorkflowState.PROPOSAL_UNDER_REVIEW:
            logger.warning(f"Cannot approve — state is {engagement.state.value}")
            return False

        if not engagement.check_sow_approval(message):
            logger.info("Approval phrase not detected. Proposal remains under review.")
            return False

        engagement.transition_to(WorkflowState.PROPOSAL_APPROVED)
        self.store.save(engagement)

        self.slack.post_proposal_status(
            f"Proposal for *{client_name}* has been approved. Ready to create SOW."
        )
        logger.info(f"Proposal approved for {client_name}. SOW creation unlocked.")
        return True

    # ── Phase 2: SOW ───────────────────────────────────────────────────

    def draft_sow(self, client_name: str, proposal_content: str) -> str:
        """Create the SOW from the approved proposal. Gate 2 enforced here."""
        engagement = self._load_engagement(client_name)

        if not engagement.can_start_sow:
            raise WorkflowError(
                f"Cannot create SOW. Current state: {engagement.state.value}. "
                f"Proposal must be approved first. "
                f'Jen must write: "approved, create the SOW"'
            )

        engagement.transition_to(WorkflowState.SOW_DRAFT_IN_PROGRESS)
        self.store.save(engagement)

        # Copy the SOW template
        logger.info("Copying SOW template...")
        copy = self.drive.copy_file(
            source_file_id=self.settings.sow_template_id,
            new_name=f"SOW — {client_name}",
            folder_id=self.settings.proposal_sow_folder_id,
        )
        engagement.sow_id = copy["id"]
        engagement.sow_link = copy.get("webViewLink", "")

        # Generate SOW content with Claude
        logger.info("Mapping proposal content to SOW structure...")
        prompt = SOW_MAPPING_PROMPT.format(
            client_name=client_name,
            proposal_content=proposal_content,
        )
        sow_draft = self.llm.generate(prompt, system=SYSTEM_PROMPT, max_tokens=12000)

        # Guardrail checks
        banned = check_banned_phrases(sow_draft)
        if banned:
            sow_draft = self.llm.generate(
                f"Revise to remove these phrases: {banned}.\n\n{sow_draft}",
                system=SYSTEM_PROMPT,
            )

        fabrication_warnings = validate_no_fabrication_markers(sow_draft)
        if fabrication_warnings:
            logger.warning(f"Fabrication warnings in SOW: {fabrication_warnings}")

        engagement.transition_to(WorkflowState.SOW_UNDER_REVIEW)
        self.store.save(engagement)

        self.slack.post_sow_ready(client_name, engagement.sow_link)

        return sow_draft

    def revise_sow(self, client_name: str, feedback: str, current_sow: str) -> str:
        """Revise the SOW based on Jen's feedback."""
        engagement = self._load_engagement(client_name)

        if engagement.state != WorkflowState.SOW_UNDER_REVIEW:
            raise WorkflowError(
                f"SOW must be under review to revise. Current state: {engagement.state.value}"
            )

        engagement.add_review_note(feedback)
        engagement.transition_to(WorkflowState.SOW_DRAFT_IN_PROGRESS)

        prompt = SOW_REVISION_PROMPT.format(
            client_name=client_name,
            current_sow=current_sow,
            feedback=feedback,
        )
        revised = self.llm.generate(prompt, system=SYSTEM_PROMPT)

        # Guardrail check
        banned = check_banned_phrases(revised)
        if banned:
            revised = self.llm.generate(
                f"Revise to remove these phrases: {banned}.\n\n{revised}",
                system=SYSTEM_PROMPT,
            )

        engagement.transition_to(WorkflowState.SOW_UNDER_REVIEW)
        self.store.save(engagement)

        self.slack.post_proposal_status(
            f"Revised SOW for *{client_name}* is ready for another review."
        )

        return revised

    def finalize_sow(self, client_name: str) -> dict:
        """Mark the SOW as finalized. Returns links to both documents."""
        engagement = self._load_engagement(client_name)

        if engagement.state != WorkflowState.SOW_UNDER_REVIEW:
            raise WorkflowError(
                f"SOW must be under review to finalize. Current state: {engagement.state.value}"
            )

        engagement.transition_to(WorkflowState.SOW_FINALIZED)
        self.store.save(engagement)

        self.slack.post_proposal_status(
            f"SOW for *{client_name}* has been finalized.\n"
            f"Proposal: {engagement.proposal_link}\n"
            f"SOW: {engagement.sow_link}"
        )

        return {
            "client_name": client_name,
            "state": engagement.state.value,
            "proposal_link": engagement.proposal_link,
            "sow_link": engagement.sow_link,
        }

    def get_status(self, client_name: str) -> dict:
        """Return the current state of an engagement."""
        engagement = self._load_engagement(client_name)
        return engagement.to_dict()

    # ── Internal ───────────────────────────────────────────────────────

    def _load_engagement(self, client_name: str) -> Engagement:
        engagement = self.store.load(client_name)
        if not engagement:
            raise WorkflowError(f"No engagement found for '{client_name}'")
        return engagement


def interactive_session():
    """Run an interactive CLI session for the proposal/SOW workflow."""
    settings = Settings.load()
    missing = settings.validate(REQUIRED_CONFIG)
    if missing:
        logger.error(f"Missing required configuration: {missing}")
        sys.exit(1)

    agent = ProposalSOWAgent(settings)

    print("\n" + "=" * 60)
    print("  Plumtree Proposal & SOW Agent")
    print("  Type 'help' for available commands")
    print("=" * 60 + "\n")

    while True:
        try:
            command = input("\nplumtree> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not command:
            continue

        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            _print_help()
        elif cmd == "new":
            _handle_new(agent, args)
        elif cmd == "draft":
            _handle_draft(agent, args)
        elif cmd == "revise-proposal":
            _handle_revise_proposal(agent, args)
        elif cmd == "approve":
            _handle_approve(agent, args)
        elif cmd == "sow":
            _handle_sow(agent, args)
        elif cmd == "revise-sow":
            _handle_revise_sow(agent, args)
        elif cmd == "finalize":
            _handle_finalize(agent, args)
        elif cmd == "status":
            _handle_status(agent, args)
        elif cmd == "list":
            _handle_list(agent)
        elif cmd in ("quit", "exit"):
            print("Exiting.")
            break
        else:
            print(f"Unknown command: {cmd}. Type 'help' for options.")


def _print_help():
    print("""
Available commands:

  new <client_name>         Start a new engagement (will prompt for discovery notes)
  draft <client_name>       Generate the initial proposal draft
  revise-proposal <client>  Revise the proposal with feedback
  approve <client_name>     Submit approval message (must include "approved, create the SOW")
  sow <client_name>         Generate the SOW from the approved proposal
  revise-sow <client>       Revise the SOW with feedback
  finalize <client_name>    Mark the SOW as finalized
  status <client_name>      Show current engagement status
  list                      Show all engagements
  help                      Show this message
  quit                      Exit
""")


def _handle_new(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    print("Paste discovery notes (end with a line containing only 'END'):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    discovery = "\n".join(lines)
    engagement = agent.start_engagement(client_name, discovery)
    print(f"\nEngagement created. State: {engagement.state.value}")


def _handle_draft(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    try:
        draft = agent.draft_proposal(client_name)
        print(f"\n{'=' * 60}")
        print("PROPOSAL DRAFT")
        print(f"{'=' * 60}")
        print(draft)
    except WorkflowError as e:
        print(f"Error: {e}")


def _handle_revise_proposal(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    print("Enter feedback (end with 'END'):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    feedback = "\n".join(lines)
    print("Paste current draft (end with 'END'):")
    draft_lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        draft_lines.append(line)
    current_draft = "\n".join(draft_lines)
    try:
        revised = agent.revise_proposal(client_name, feedback, current_draft)
        print(f"\n{'=' * 60}")
        print("REVISED PROPOSAL")
        print(f"{'=' * 60}")
        print(revised)
    except WorkflowError as e:
        print(f"Error: {e}")


def _handle_approve(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    message = input("Approval message: ").strip()
    approved = agent.approve_proposal(client_name, message)
    if approved:
        print("Proposal approved. You can now run 'sow' to create the SOW.")
    else:
        print('Proposal not approved. Message must contain: "approved, create the SOW"')


def _handle_sow(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    print("Paste the approved proposal content (end with 'END'):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    proposal_content = "\n".join(lines)
    try:
        sow = agent.draft_sow(client_name, proposal_content)
        print(f"\n{'=' * 60}")
        print("SOW DRAFT")
        print(f"{'=' * 60}")
        print(sow)
    except WorkflowError as e:
        print(f"Error: {e}")


def _handle_revise_sow(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    print("Enter feedback (end with 'END'):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    feedback = "\n".join(lines)
    print("Paste current SOW (end with 'END'):")
    sow_lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        sow_lines.append(line)
    current_sow = "\n".join(sow_lines)
    try:
        revised = agent.revise_sow(client_name, feedback, current_sow)
        print(f"\n{'=' * 60}")
        print("REVISED SOW")
        print(f"{'=' * 60}")
        print(revised)
    except WorkflowError as e:
        print(f"Error: {e}")


def _handle_finalize(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    try:
        result = agent.finalize_sow(client_name)
        print(f"\nSOW finalized for {result['client_name']}.")
        print(f"Proposal: {result['proposal_link']}")
        print(f"SOW: {result['sow_link']}")
    except WorkflowError as e:
        print(f"Error: {e}")


def _handle_status(agent: ProposalSOWAgent, client_name: str):
    if not client_name:
        client_name = input("Client name: ").strip()
    try:
        status = agent.get_status(client_name)
        print(f"\nClient: {status['client_name']}")
        print(f"State: {status['state']}")
        print(f"Proposal: {status.get('proposal_link', '(not created)')}")
        print(f"SOW: {status.get('sow_link', '(not created)')}")
        if status.get("open_questions"):
            print(f"Open questions: {len(status['open_questions'])}")
    except WorkflowError as e:
        print(f"Error: {e}")


def _handle_list(agent: ProposalSOWAgent):
    engagements = agent.store.list_engagements()
    if not engagements:
        print("No engagements found.")
    else:
        for name in engagements:
            status = agent.get_status(name)
            print(f"  {name}: {status['state']}")


def main():
    interactive_session()


if __name__ == "__main__":
    main()
