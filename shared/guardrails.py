"""Shared guardrail checks enforced across both agents."""

BANNED_PHRASES = [
    "game-changing",
    "leverage",
    "unlock",
    "empower",
    "in today's rapidly evolving landscape",
    "synergy",
    "paradigm shift",
    "move the needle",
    "best-in-class",
    "thought leader",
    "disrupt",
    "circle back",
    "low-hanging fruit",
    "deep dive",
    "north star",
]


def check_banned_phrases(text: str) -> list[str]:
    """Return any banned phrases found in text."""
    lower = text.lower()
    return [phrase for phrase in BANNED_PHRASES if phrase in lower]


def strip_banned_phrases(text: str) -> str:
    """Remove banned phrases from text (simple replacement)."""
    for phrase in BANNED_PHRASES:
        # Case-insensitive removal
        idx = text.lower().find(phrase)
        while idx != -1:
            text = text[:idx] + text[idx + len(phrase):]
            idx = text.lower().find(phrase)
    return text


def validate_no_fabrication_markers(text: str) -> list[str]:
    """Flag common signs of fabricated citations."""
    warnings = []
    fabrication_signals = [
        "et al., forthcoming",
        "accessed on [",
        "URL not available",
        "[insert ",
        "[placeholder",
        "example.com",
    ]
    lower = text.lower()
    for signal in fabrication_signals:
        if signal.lower() in lower:
            warnings.append(f"Possible fabrication marker: '{signal}'")
    return warnings
