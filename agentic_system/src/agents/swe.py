import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agentic_system.src.db.retriever import DocRetriever
from agentic_system.src.state import AgentState, FileMutation

load_dotenv()

# Container model for SWE output
class SweResult(BaseModel):
    mutations: List[FileMutation] = Field(
        ...,
        description="List of file operations to apply. Each WRITE must contain complete, fully indented Skript code."
    )
    rationale: str = Field(
        ...,
        description="Brief explanation of the chosen syntax patterns and architectural choices."
    )


SWE_SYSTEM_PROMPT = """You are an expert Minecraft Skript DSL systems developer.
You write production-grade, highly performant, and secure .sk scripts for 1.21.5 PaperMC servers.

ENVIRONMENT CONSTRAINTS:
1. PURE VANILLA SKRIPT ONLY: No third-party addons are installed on this server (NO SkBee, NO SkQuery, NO sk-nbtee).
2. ZERO NBT TAG USAGE: Vanilla Skript cannot parse NBT tags. NEVER use 'nbt', 'tag', 'custom nbt', or 'nbt compound'.
3. CUSTOM ITEM IDENTIFICATION: Always identify custom items by their item type, display name, and/or lore:
   - Check example: if victim's chestplate is iron chestplate named "&bBullet Proof Vest":
   - Check example: if name of player's tool is "&6Fire Staff":
   - Give example: give 1 of iron chestplate named "&bBullet Proof Vest" with lore "&7Absorbs projectile damage" to player

CRITICAL SYNTAX & FORMATTING RULES:
1. INDENTATION IS MANDATORY: Skript syntax is whitespace-sensitive. Every block following a colon (:) MUST be on a new line indented with exactly 4 spaces. NEVER combine statements on a single line.
2. MULTI-FILE ARCHITECTURE: If target_scope is a directory, emit clean, modular files with clear responsibilities. Ensure shared variables (e.g., {{spellbook::*}}) and function signatures match across sibling files.
3. PURE SKRIPT DSL: Use standard Skript syntax patterns. Never hallucinate Java Bukkit API methods or curly-brace code.
4. TARGETED FIXING & SELF-HEALING: If a compiler error is provided, prioritize fixing the exact file and line number flagged by the compiler trace. If the compiler reports an unrecognizable condition/effect, eliminate any complex or addon syntax and revert to canonical vanilla Skript.

Relevant Skript Syntax Documentation retrieved for this task:
{retrieved_docs}
"""

SWE_USER_PROMPT = """TASK CONTEXT:
- Action Type: {action_type}
- Target Scope: {target_scope}
- Advisory Event Candidates: {candidate_events}

EXISTING WORKSPACE FILES IN SCOPE:
{workspace_context}

COMPILER FEEDBACK (If recovering from an error):
{compiler_error}

PLAYER REQUEST:
"{raw_prompt}"

Synthesize the complete, indented Skript file mutations required to fulfill this request.
"""


def _format_workspace_context(ctx: Dict[str, str]) -> str:
    """Formats existing scripts into a readable context block."""
    if not ctx:
        return "(No existing files in this scope. This is a clean project or new script.)"
    formatted = []
    for path, content in ctx.items():
        formatted.append(f"--- File: {path} ---\n{content}\n")
    return "\n".join(formatted)


def swe_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: Synthesizes or repairs Skript code across one or more files.
    """
    retriever = DocRetriever()

    # 1. Dynamically retrieve syntax patterns based on prompt and candidate events
    query_terms = [state.raw_prompt] + state.candidate_events
    if state.compiler_error:
        query_terms.append(state.compiler_error)
    search_query = " ".join(query_terms)

    # Fetch relevant documentation from SQLite FTS5
    retrieved_docs = retriever.format_for_prompt(search_query, limit=5)

    # 2. Build prompts
    prompt = ChatPromptTemplate.from_messages([
        ("system", SWE_SYSTEM_PROMPT),
        ("user", SWE_USER_PROMPT),
    ])

    # 3. Initialize model with structured schema
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=0.1,
    )
    structured_llm = llm.with_structured_output(SweResult)

    chain = prompt | structured_llm

    # 4. Invoke LLM
    result: SweResult = chain.invoke({
        "retrieved_docs": retrieved_docs,
        "action_type": state.action_type,
        "target_scope": state.target_scope,
        "candidate_events": ", ".join(state.candidate_events) if state.candidate_events else "None",
        "workspace_context": _format_workspace_context(state.workspace_context),
        "compiler_error": state.compiler_error or "None (Clean compilation)",
        "raw_prompt": state.raw_prompt,
    })

    trace_entry = {
        "node": "swe",
        "mutations_count": len(result.mutations),
        "files_modified": [m.path for m in result.mutations],
        "rationale": result.rationale,
    }

    return {
        "mutations": result.mutations,
        "swe_rationale": result.rationale,
        "traces": state.traces + [trace_entry],
    }