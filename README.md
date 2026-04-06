# Plumtree Agents

Internal agents for Plumtree Services. Two agents that support the team's weekly operations and client engagement workflow.

## Agents

### 1. Research and Insight Generation Agent

Produces a weekly "Future of Work" research brief every Friday. The agent:

- Searches public research, articles, and papers from the past 7 days across five categories: Teams and Teaming, Organization Systems, Culture, Leadership, and AI and the Future of Work
- Filters for substantive sources (academic papers, serious journalism, practitioner research) and rejects content farms, listicles, and hype
- Synthesizes findings using Claude — writes in Plumtree's voice (direct, plain-language, grounded)
- Creates a formatted Word document matching Plumtree's brief template
- Saves the document to Google Drive
- Notifies `#ops-knowledge-share` on Slack with a link
- Tracks all previously included articles in a Google Sheet to prevent repeats

**Run modes:**
```bash
# Start the Friday scheduler (runs every Friday at 8:00 AM)
plumtree research

# Run immediately (for testing or manual trigger)
plumtree research --now
```

### 2. Proposal-to-SOW Automation Agent

Supports proposal creation and SOW generation with explicit approval gates. Human-in-the-loop — nothing advances without Jen's sign-off.

**Workflow states:**
```
intake_received → proposal_draft_in_progress → proposal_under_review
    → proposal_approved → sow_draft_in_progress → sow_under_review → sow_finalized
```

**Hard gate:** SOW creation is blocked until Jen writes exactly: `"approved, create the SOW"`

**Run:**
```bash
# Start interactive session
plumtree proposal
```

**Commands in the interactive session:**
| Command | What it does |
|---------|-------------|
| `new <client>` | Start a new engagement with discovery notes |
| `draft <client>` | Generate the initial proposal draft |
| `revise-proposal <client>` | Revise proposal based on feedback |
| `approve <client>` | Submit approval (must include the exact phrase) |
| `sow <client>` | Generate SOW from approved proposal |
| `revise-sow <client>` | Revise SOW based on feedback |
| `finalize <client>` | Mark SOW as finalized |
| `status <client>` | Show current engagement state |
| `list` | Show all engagements |

## Setup

### Prerequisites

- Python 3.11+
- Google Cloud project with OAuth credentials
- Slack bot token
- Anthropic API key
- Tavily API key (for web search)

### Installation

```bash
# Clone and install
git clone <repo-url>
cd Plumtree-Agents
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your actual credentials
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required for | Notes |
|----------|-------------|-------|
| `ANTHROPIC_API_KEY` | Both agents | Claude API key |
| `GOOGLE_CLIENT_ID` | Both agents | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Both agents | OAuth client secret |
| `SLACK_BOT_TOKEN` | Both agents | Slack bot token (xoxb-...) |
| `TAVILY_API_KEY` | Research agent | Web search API key |
| `ARTICLE_HISTORY_SHEET_ID` | Research agent | Google Sheet ID for article dedup |

The remaining variables in `.env.example` have sensible defaults (folder IDs, template IDs, channel IDs) but can be overridden.

### Google OAuth Setup

1. The Google client ID is already configured: `374574530219-sehpo3pn4i1spa1tfppnv7hrlcqglp66.apps.googleusercontent.com`
2. You also need the **client secret** from the Google Cloud Console for this OAuth client
3. On first run, a browser window opens for OAuth consent
4. The token is cached at `~/.plumtree/token.json` for subsequent runs

### Article History Google Sheet

Create a new Google Sheet and copy its ID from the URL:
```
https://docs.google.com/spreadsheets/d/<THIS_IS_THE_ID>/edit
```

Set this as `ARTICLE_HISTORY_SHEET_ID` in your `.env`. The agent will create the header row automatically on first run.

### Slack Setup

The Slack bot needs permissions to post to:
- `#ops-knowledge-share` (research briefs)
- `#agent-proposal-sow` (proposal/SOW status)

Required Slack bot scopes: `chat:write`, `channels:read`

## Project Structure

```
Plumtree-Agents/
├── main.py                          # CLI entry point
├── config/
│   └── settings.py                  # Environment config loader
├── agents/
│   ├── research/
│   │   ├── agent.py                 # Research agent orchestrator + scheduler
│   │   ├── prompts.py               # Research synthesis prompts
│   │   └── formatter.py             # Word document formatting
│   └── proposal_sow/
│       ├── agent.py                 # Proposal/SOW agent + interactive CLI
│       ├── workflow.py              # State machine with approval gates
│       └── prompts.py               # Proposal and SOW drafting prompts
├── integrations/
│   ├── google_auth.py               # Shared OAuth2 authentication
│   ├── google_drive.py              # Drive upload and template copying
│   ├── google_sheets.py             # Article dedup tracking
│   ├── google_slides.py             # Proposal template operations
│   ├── google_docs.py               # SOW template operations
│   ├── slack_client.py              # Slack notifications
│   └── web_search.py                # Tavily web search
├── shared/
│   ├── llm.py                       # Claude API client
│   └── guardrails.py                # Banned phrase and fabrication checks
├── .env.example                     # Template for environment variables
├── pyproject.toml                   # Python package config
└── README.md
```

## Guardrails

Both agents enforce:

- **No banned phrases:** game-changing, leverage, unlock, empower, synergy, etc.
- **No fabrication:** citations, source links, client examples, and past work must be real
- **No client data leakage:** confidential material never crosses engagements
- **Template safety:** master templates are copied, never overwritten
- **File safety:** outputs saved only to designated folders; no deletions
- **Slack safety:** posts only to internal channels; never messages clients
- **Approval gates:** the proposal/SOW agent enforces explicit state transitions

## Unresolved Setup Dependencies

1. **Google OAuth client secret** — The client ID is known, but the client secret must be added to `.env` manually
2. **Article history Google Sheet** — A new Sheet needs to be created and its ID added to `.env`
3. **Tavily API key** — Required for web search; sign up at https://tavily.com
4. **Slack bot token** — The Slack workspace is connected, but the bot token must be added to `.env`

## Engagement State Persistence

The proposal/SOW agent stores engagement state at `~/.plumtree/engagements.json`. This tracks:
- Current workflow state
- Google Drive file IDs and links
- Review history
- Open questions

This file persists across sessions so you can pick up where you left off.
