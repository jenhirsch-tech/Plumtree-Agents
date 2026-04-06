"""State machine for the Proposal-to-SOW workflow.

Enforces explicit approval gates:
- Proposal drafting can begin once discovery is loaded
- SOW creation can only begin after explicit approval ("approved, create the SOW")
"""

import json
import logging
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    """Explicit states for the proposal/SOW workflow."""
    INTAKE_RECEIVED = "intake_received"
    PROPOSAL_DRAFT_IN_PROGRESS = "proposal_draft_in_progress"
    PROPOSAL_UNDER_REVIEW = "proposal_under_review"
    PROPOSAL_APPROVED = "proposal_approved"
    SOW_DRAFT_IN_PROGRESS = "sow_draft_in_progress"
    SOW_UNDER_REVIEW = "sow_under_review"
    SOW_FINALIZED = "sow_finalized"


# Valid state transitions
VALID_TRANSITIONS = {
    WorkflowState.INTAKE_RECEIVED: [WorkflowState.PROPOSAL_DRAFT_IN_PROGRESS],
    WorkflowState.PROPOSAL_DRAFT_IN_PROGRESS: [WorkflowState.PROPOSAL_UNDER_REVIEW],
    WorkflowState.PROPOSAL_UNDER_REVIEW: [
        WorkflowState.PROPOSAL_DRAFT_IN_PROGRESS,  # revision requested
        WorkflowState.PROPOSAL_APPROVED,
    ],
    WorkflowState.PROPOSAL_APPROVED: [WorkflowState.SOW_DRAFT_IN_PROGRESS],
    WorkflowState.SOW_DRAFT_IN_PROGRESS: [WorkflowState.SOW_UNDER_REVIEW],
    WorkflowState.SOW_UNDER_REVIEW: [
        WorkflowState.SOW_DRAFT_IN_PROGRESS,  # revision requested
        WorkflowState.SOW_FINALIZED,
    ],
    WorkflowState.SOW_FINALIZED: [],
}

# The exact phrase required to advance from proposal to SOW
APPROVAL_PHRASE = "approved, create the sow"


@dataclass
class Engagement:
    """Tracks the state of a single client engagement through the workflow."""
    client_name: str
    state: WorkflowState = WorkflowState.INTAKE_RECEIVED
    discovery_notes: str = ""
    proposal_id: str = ""  # Google Slides file ID
    proposal_link: str = ""
    sow_id: str = ""  # Google Docs file ID
    sow_link: str = ""
    review_history: list[dict] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def transition_to(self, new_state: WorkflowState) -> None:
        """Attempt to transition to a new state. Raises if invalid."""
        valid_next = VALID_TRANSITIONS.get(self.state, [])
        if new_state not in valid_next:
            raise WorkflowError(
                f"Cannot transition from {self.state.value} to {new_state.value}. "
                f"Valid next states: {[s.value for s in valid_next]}"
            )
        logger.info(f"[{self.client_name}] {self.state.value} -> {new_state.value}")
        self.state = new_state
        self.updated_at = datetime.now().isoformat()

    def add_review_note(self, note: str, reviewer: str = "Jen") -> None:
        """Record a review comment."""
        self.review_history.append({
            "reviewer": reviewer,
            "note": note,
            "timestamp": datetime.now().isoformat(),
            "state": self.state.value,
        })

    def check_sow_approval(self, message: str) -> bool:
        """Check if the message contains the exact SOW approval phrase."""
        return APPROVAL_PHRASE in message.lower().strip()

    @property
    def can_start_sow(self) -> bool:
        """Whether the workflow is in a state that allows SOW creation."""
        return self.state == WorkflowState.PROPOSAL_APPROVED

    @property
    def is_complete(self) -> bool:
        return self.state == WorkflowState.SOW_FINALIZED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Engagement":
        data["state"] = WorkflowState(data["state"])
        return cls(**data)


class WorkflowError(Exception):
    """Raised when a workflow transition is invalid."""
    pass


class WorkflowStore:
    """Persist engagement state to a local JSON file.

    Each engagement is stored by client name.
    """

    def __init__(self, store_path: str | None = None):
        self.path = Path(store_path or Path.home() / ".plumtree" / "engagements.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")

    def save(self, engagement: Engagement) -> None:
        data = self._load_all()
        data[engagement.client_name] = engagement.to_dict()
        self.path.write_text(json.dumps(data, indent=2))

    def load(self, client_name: str) -> Engagement | None:
        data = self._load_all()
        if client_name in data:
            return Engagement.from_dict(data[client_name])
        return None

    def list_engagements(self) -> list[str]:
        return list(self._load_all().keys())

    def _load_all(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
