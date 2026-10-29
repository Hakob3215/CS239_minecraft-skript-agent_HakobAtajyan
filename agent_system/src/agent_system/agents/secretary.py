import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agent_system.paths import DATA_DIR, SCRIPTS_ROOT
from agent_system.state import AgentState

load_dotenv()

MANIFEST_PATH = DATA_DIR / "event_manifest.json"


class SecretaryDecision(BaseModel):
    target_scope: str = Field(
        ...,
        description=(
            "The resolved script path or directory (relative to scripts root). "
            "If updating or fixing, match the best existing file from active_scripts. "
            "If creating, synthesize a clean, logical path like 'combat/double_jump.sk' or 'items/grapple.sk'."
        ),
    )
    is_new_file: bool = Field(
        ...,
        description="True if this task requires creating a new file, False if modifying existing scripts.",
    )
    candidate_events: List[str] = Field(
        default_factory=list,
        description=(
            "Advisory Skript event IDs (e.g. ['flight_toggle', 'damage']) deduced from the user's intent. "
            "Leave empty if the request only involves custom commands (command /...) or helper functions."
        ),
    )
    intent_summary: str = Field(
        ...,
        description="Concise 1-sentence summary of the core mechanical change requested.",
    )


SECRETARY_SYSTEM_PROMPT = """You are the triage Secretary Agent for an autonomous Minecraft Skript development system.
Your goal is to inspect player chat commands (!create, !update, !fix), analyze the active workspace scripts, and resolve the target scope and candidate events.

WORKSPACE CONTEXT:
- Active Scripts currently on disk:
{active_scripts}

COMMON EVENT IDS AVAILABLE IN SKRIPT:
{sample_events}

RESOLUTION RULES:
1. FUZZY & SEMANTIC SCOPE MATCHING:
   - If action is UPDATE or FIX, analyze the prompt and match it to the most relevant existing file in `active_scripts` even if the user did not type the exact path.
     For example: "update double jump to use iron boots" -> "combat/double_jump.sk".
     "fix the ping cooldown" -> "demo/ping.sk".
   - If action is CREATE, check if the mechanic fits an existing script or requires a new file. If new, choose a clean, grouped path (e.g., 'combat/fireball.sk', 'items/spellbook.sk', 'utils/spawn.sk').
2. ADVISORY EVENT CANDIDATES:
   - Infer the relevant underlying Skript event triggers from intent (e.g., 'jumping in air' -> 'flight_toggle', 'when hit' -> 'damage', 'right click item' -> 'click').
   - If the request is purely for a command (e.g., /ping, /getboots), do not invent unnecessary event listeners.
"""

SECRETARY_USER_PROMPT = """PLAYER CHAT TRIGGER:
- Action Type: {action_type}
- Raw Prompt: "{raw_prompt}"

Analyze the request and output your structured routing decision."""


def get_active_scripts() -> List[str]:
    """Recursively scans scripts directory for non-disabled .sk files."""
    if not SCRIPTS_ROOT.exists():
        return []

    active_files = []
    for p in SCRIPTS_ROOT.rglob("*.sk"):
        parts = p.relative_to(SCRIPTS_ROOT).parts
        if any(part.startswith("-") for part in parts):
            continue
        rel_posix = str(p.relative_to(SCRIPTS_ROOT)).replace("\\", "/")
        active_files.append(rel_posix)

    return sorted(active_files)


def load_workspace_context(target_scope: str) -> Dict[str, str]:
    """Reads file buffers in target scope for downstream agents."""
    clean_scope = target_scope.replace("\\", "/").strip("/")
    target_path = (SCRIPTS_ROOT / clean_scope).resolve()

    context: Dict[str, str] = {}

    if not target_path.is_relative_to(SCRIPTS_ROOT):
        raise PermissionError(f"Scope escapes scripts directory: {target_scope}")

    if not target_path.exists():
        return context

    if target_path.is_dir():
        for p in target_path.rglob("*.sk"):
            parts = p.relative_to(SCRIPTS_ROOT).parts
            if any(part.startswith("-") for part in parts):
                continue
            rel = str(p.relative_to(SCRIPTS_ROOT)).replace("\\", "/")
            context[rel] = p.read_text(encoding="utf-8", errors="replace")
    elif target_path.is_file() and not target_path.name.startswith("-"):
        rel = str(target_path.relative_to(SCRIPTS_ROOT)).replace("\\", "/")
        context[rel] = target_path.read_text(encoding="utf-8", errors="replace")

    return context


def _get_event_samples() -> str:
    """Loads a representative summary of event IDs for the prompt."""
    if not MANIFEST_PATH.exists():
        return "None available"
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            events = json.load(f)
        # Select common core events
        sample_ids = [e["id"] for e in events[:40]]
        return ", ".join(sample_ids)
    except Exception:
        return "None available"


def secretary_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: Semantically triages the request, maps it to the
    workspace filesystem, and gathers context for the SWE agent.
    """
    active_scripts = get_active_scripts()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SECRETARY_SYSTEM_PROMPT),
        ("user", SECRETARY_USER_PROMPT),
    ])

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=0.0,
    )
    structured_llm = llm.with_structured_output(SecretaryDecision)
    chain = prompt | structured_llm

    decision: SecretaryDecision = chain.invoke({
        "active_scripts": active_scripts if active_scripts else ["(No scripts currently active)"],
        "sample_events": _get_event_samples(),
        "action_type": state.action_type,
        "raw_prompt": state.raw_prompt,
    })

    # Read relevant existing files based on LLM's target scope
    workspace_context = load_workspace_context(decision.target_scope)

    trace_entry = {
        "node": "secretary",
        "action_type": state.action_type,
        "target_scope": decision.target_scope,
        "is_new_file": decision.is_new_file,
        "files_loaded": list(workspace_context.keys()),
        "candidate_events": decision.candidate_events,
        "intent_summary": decision.intent_summary,
    }

    return {
        "target_scope": decision.target_scope,
        "workspace_context": workspace_context,
        "candidate_events": decision.candidate_events,
        "traces": state.traces + [trace_entry],
    }