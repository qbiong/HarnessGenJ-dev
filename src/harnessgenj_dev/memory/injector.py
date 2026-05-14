"""Memory Injector — extracts knowledge from conversations and feeds it into the memory system.

Bridges Session conversation history with the JVM memory architecture:
- Extracts key decisions and saves to SharedMemory
- Extracts role-specific learnings and saves to RoleMemory
- Extracts project facts and saves to SharedMemory
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that indicate knowledge-worthy content
_DECISION_PATTERNS = [
    r"decided to\s+(.+)",
    r"we should\s+(.+)",
    r"we'll use\s+(.+)",
    r"using\s+(\w+)\s+(?:for|to|as)\s+(.+)",
    r"(?:the )?(?:approach|method|strategy|pattern) (?:is|will be|was)\s+(.+)",
    r"(?:architecture|design) (?:is|uses|follows)\s+(.+)",
]

# Patterns for project facts
_FACT_PATTERNS = [
    r"(?:the )?(?:project|codebase|app|application) (?:uses|has|contains|is built with)\s+(.+)",
    r"(?:file|module|component)\s+(\S+)\s+(?:handles|manages|provides|implements)\s+(.+)",
    r"(?:endpoint|route|api)\s+(\S+)\s+(?:returns|accepts|handles)\s+(.+)",
]


def extract_knowledge_from_conversation(
    messages: list[dict[str, str]],
    role: str = "developer",
) -> dict[str, list[dict[str, str]]]:
    """Extract knowledge entries from conversation history.

    Analyzes assistant messages for decisions, facts, and learnings.

    Args:
        messages: Conversation history (list of {role, content}).
        role: Current role context.

    Returns:
        Dict with keys: "decisions", "facts", "learnings"
        Each value is a list of {key, content} dicts.
    """
    decisions = []
    facts = []
    learnings = []

    for msg in messages:
        if msg.get("role") != "assistant":
            continue

        content = msg.get("content", "")
        if len(content) < 30:
            continue

        # Extract decisions
        for pattern in _DECISION_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                text = match.group(0).strip()
                key = _make_key(text)
                if key and len(text) < 200:
                    decisions.append({"key": key, "content": text})

        # Extract project facts
        for pattern in _FACT_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                text = match.group(0).strip()
                key = _make_key(text)
                if key and len(text) < 200:
                    facts.append({"key": key, "content": text})

    # Deduplicate by key
    seen = set()
    unique_decisions = []
    for d in decisions:
        if d["key"] not in seen:
            seen.add(d["key"])
            unique_decisions.append(d)

    seen = set()
    unique_facts = []
    for f in facts:
        if f["key"] not in seen:
            seen.add(f["key"])
            unique_facts.append(f)

    return {
        "decisions": unique_decisions,
        "facts": unique_facts,
        "learnings": learnings,
    }


def _make_key(text: str) -> str:
    """Generate a memory key from text."""
    # Take first 3 words, lowercase, underscores
    words = text.split()[:3]
    if not words:
        return ""
    key = "_".join(w.lower() for w in words if w.isalpha())
    # Clean up
    key = re.sub(r"[^a-z0-9_]", "", key)
    if len(key) < 3:
        return ""
    return f"auto_{key}"


def inject_into_memory(
    knowledge: dict[str, list[dict[str, str]]],
    role: str,
    project: str = "default",
) -> dict[str, int]:
    """Inject extracted knowledge into the memory system.

    Args:
        knowledge: Output from extract_knowledge_from_conversation().
        role: Role context for role-specific memory.
        project: Project name for session context.

    Returns:
        Dict with counts: {decisions_saved, facts_saved, learnings_saved}
    """
    from harnessgenj_dev.memory import MemoryManager

    mgr = MemoryManager()
    shared = mgr.shared
    role_mem = mgr.get_role_memory(role)

    counts = {"decisions_saved": 0, "facts_saved": 0, "learnings_saved": 0}

    # Save decisions to shared memory
    for d in knowledge.get("decisions", []):
        shared.add_decision(d["key"], d["content"], reason=f"Extracted from {role} conversation")
        counts["decisions_saved"] += 1

    # Save facts to shared memory
    for f in knowledge.get("facts", []):
        shared.add_shared_knowledge(f"fact_{f['key']}", f["content"], tags=["knowledge", "auto-extracted"])
        counts["facts_saved"] += 1

    # Save learnings to role memory
    for l in knowledge.get("learnings", []):
        role_mem.add_knowledge(l["key"], l["content"])
        counts["learnings_saved"] += 1

    # Save summary to shared memory
    if knowledge["decisions"] or knowledge["facts"]:
        summary_parts = []
        if knowledge["decisions"]:
            summary_parts.append(f"{len(knowledge['decisions'])} decision(s)")
        if knowledge["facts"]:
            summary_parts.append(f"{len(knowledge['facts'])} fact(s)")
        shared.add_shared_knowledge(
            f"session_summary_{role}",
            f"Auto-extracted from {role}: {', '.join(summary_parts)}",
            tags=["knowledge", "session-summary"],
        )

    # Persist all
    mgr.save_all()

    return counts
