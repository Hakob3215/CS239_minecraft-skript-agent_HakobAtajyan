from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class FileMutation(BaseModel):
    """
    Represents a single file update in server/plugins/Skript/scripts/
    """
    path: str = Field(
        ...,
        description="Relative POSIX path from scripts root (e.g. 'combat/double_jump.sk' or 'spells/fireball.sk'). Must never contain '..'."
    )
    action: Literal["CREATE", "WRITE", "DELETE"] = Field(
        ...,
        description="Mutation type: must be 'CREATE', 'WRITE', or 'DELETE'."
    )
    content: Optional[str] = Field(
        default="",
        description="UTF-8 Skript code buffer to write. Required if action is 'WRITE' or 'CREATE', empty or None if 'DELETE'."
    )


class AgentState(BaseModel):
    """
    The shared state that each agent (Secretary, SWE, Reviewer) accesses and mutates in LangGraph.
    """

    # INPUT FROM CHAT LOGGER
    raw_prompt: str = Field(
        ...,
        description="The in-game chat trigger, e.g. '!create double jump boots'"
    )

    # OUTPUT OF SECRETARY AGENT
    action_type: Literal["CREATE", "UPDATE", "FIX"] = Field(
        default="CREATE",
        description="Action Decision: 'CREATE', 'UPDATE', or 'FIX'"
    )
    target_scope: str = Field(
        default="",
        description="The target directory or file, e.g. 'double_jump.sk' or 'items/spellbook/'"
    )
    candidate_events: List[str] = Field(
        default_factory=list,
        description="Matched Skript event IDs from data/event_manifest.json (e.g. ['flight_toggle'])"
    )
    workspace_context: Dict[str, str] = Field(
        default_factory=dict,
        description="Relevant existing scripts to content: {'path/to/script.sk': 'code...'}"
    )

    # OUTPUT OF SWE AGENT
    mutations: List[FileMutation] = Field(
        default_factory=list,
        description="List of file operations provided by the SWE Agent"
    )
    swe_rationale: Optional[str] = Field(
        default=None,
        description="Explanation from the SWE Agent justifying code patterns"
    )

    # OUTPUT OF REVIEWER AGENT
    compiler_error: Optional[str] = Field(
        default=None,
        description="Console syntax errors caught by RCON during /skript reload or semantic critique"
    )
    reviewer_feedback: Optional[str] = Field(
        default=None,
        description="Summary of code review findings or overview of applied changes"
    )
    usage_instructions: List[str] = Field(
        default_factory=list,
        description="In-game usage instructions broadcast to players (e.g., commands, items, mechanics)"
    )
    retry_count: int = Field(
        default=0,
        description="Number of compile-fix attempts made so far (max of 3)"
    )

    # TRACE LOGGING
    traces: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Auditing steps to trace model thoughts and node actions"
    )