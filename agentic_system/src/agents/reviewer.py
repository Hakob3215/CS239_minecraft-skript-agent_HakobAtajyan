import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agentic_system.src.bridge.rcon_client import RconClient
from agentic_system.src.state import AgentState, FileMutation

load_dotenv()

SCRIPTS_ROOT = Path("server/plugins/Skript/scripts").resolve()

# Hard boundary: prevent malicious server manipulation
DANGEROUS_PATTERNS = [
    re.compile(r"execute\s+console\s+command\s+[\"'].*?(stop|op\s+\*|restart|reload\s+all)[\"']", re.IGNORECASE),
    re.compile(r"make\s+console\s+execute\s+[\"'].*?(stop|op\s+\*|restart)[\"']", re.IGNORECASE),
]


class ReviewerEvaluation(BaseModel):
    meets_requirements: bool = Field(
        ...,
        description="Whether the code genuinely satisfies all functional requirements in the user's prompt.",
    )
    critique: Optional[str] = Field(
        None,
        description="If meets_requirements is False, describe what was missed or flawed so SWE can fix it.",
    )
    user_summary: str = Field(
        ...,
        description="A concise 1-sentence summary of what was created or modified.",
    )
    usage_instructions: List[str] = Field(
        default_factory=list,
        description=(
            "1-3 concise bullet points for players in Minecraft chat explaining how to use the feature. "
            "Include commands (e.g., '/getdoublejump'), permissions/OP status, items, or mechanics. "
            "Keep each under 70 characters."
        ),
    )


REVIEWER_SYSTEM_PROMPT = """You are the Senior Reviewer Agent for an autonomous Minecraft Skript system.
The code below has successfully passed live compilation on PaperMC.

Your job is twofold:
1. VERIFY INTENT: Check if the SWE agent genuinely addressed the user's prompt. If the user asked for a command or feature and the SWE agent completely omitted it, set meets_requirements=False with a clear critique.
2. EXTRACT USER USAGE: If approved, produce a clear, friendly set of in-game instructions (commands, items, permissions, usage) so the player knows how to test and use what was just loaded.
"""

REVIEWER_USER_PROMPT = """ORIGINAL USER PROMPT:
"{raw_prompt}"

SWE RATIONALE:
{swe_rationale}

CODE MUTATIONS APPLIED:
{code_diff}

Evaluate the result and generate in-game player guidance."""


def validate_safety(mutations: List[FileMutation]) -> Tuple[bool, str]:
    """Validates that mutations remain inside the scripts sandbox."""
    for m in mutations:
        clean_path = m.path.replace("\\", "/").strip("/")
        target_file = (SCRIPTS_ROOT / clean_path).resolve()

        if not target_file.is_relative_to(SCRIPTS_ROOT):
            return False, f"Security violation: path escapes scripts sandbox: {m.path}"

        if not m.path.endswith(".sk"):
            return False, f"Security violation: only .sk files can be modified: {m.path}"

        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(m.content):
                return False, f"Security violation: prohibited command pattern detected in {m.path}"

    return True, ""


def apply_mutations_to_disk(mutations: List[FileMutation]) -> List[str]:
    """Applies file mutations to disk."""
    applied = []
    for m in mutations:
        clean_path = m.path.replace("\\", "/").strip("/")
        target_file = (SCRIPTS_ROOT / clean_path).resolve()

        if m.action in ("WRITE", "CREATE"):
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(m.content, encoding="utf-8")
            applied.append(f"WRITE:{clean_path}")
        elif m.action == "DELETE":
            if target_file.exists():
                target_file.unlink()
                applied.append(f"DELETE:{clean_path}")

    return applied


async def reviewer_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: 
    1. Validates safety sandboxing.
    2. Writes code to disk.
    3. Live-compiles via RCON.
    4. Evaluates semantic completeness and broadcasts in-game usage instructions.
    """
    # 1. Deterministic Security Sandbox
    is_safe, error_reason = validate_safety(state.mutations)
    if not is_safe:
        return {
            "compiler_error": error_reason,
            "retry_count": state.retry_count + 1,
            "traces": state.traces + [{"node": "reviewer", "status": "REJECTED_SAFETY", "error": error_reason}],
        }

    # 2. Write validated code to disk
    applied_files = apply_mutations_to_disk(state.mutations)

    # 3. Live PaperMC / Skript compilation check via RCON
    rcon = RconClient()
    await rcon.connect()

    success, reload_output = await rcon.reload_script(state.target_scope)

    if not success:
        # Compiler caught a syntax error: trigger immediate self-healing loop
        await rcon.broadcast_chat(
            f"Compilation error in [{state.target_scope}]. Initiating self-healing (Attempt {state.retry_count + 1})...",
            color="gold",
        )
        await rcon.close()

        trace_entry = {
            "node": "reviewer",
            "status": "COMPILATION_ERROR",
            "applied_files": applied_files,
            "error_trace": reload_output,
            "retry_count": state.retry_count + 1,
        }
        return {
            "compiler_error": reload_output,
            "retry_count": state.retry_count + 1,
            "traces": state.traces + [trace_entry],
        }

    # 4. Code compiled successfully: Perform Agentic Semantic Review
    prompt = ChatPromptTemplate.from_messages([
        ("system", REVIEWER_SYSTEM_PROMPT),
        ("user", REVIEWER_USER_PROMPT),
    ])

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=0.1,
    )
    structured_llm = llm.with_structured_output(ReviewerEvaluation)
    chain = prompt | structured_llm

    code_diff = "\n\n".join(f"--- {m.path} ---\n{m.content}" for m in state.mutations)

    evaluation: ReviewerEvaluation = await chain.ainvoke({
        "raw_prompt": state.raw_prompt,
        "swe_rationale": state.swe_rationale or "None provided",
        "code_diff": code_diff,
    })

    # If the code compiled but completely missed core prompt requirements:
    if not evaluation.meets_requirements:
        critique_msg = evaluation.critique or "Semantic requirements check failed."
        await rcon.broadcast_chat(
            f"Review rejected for [{state.target_scope}]: {critique_msg}. Re-evaluating...",
            color="gold",
        )
        await rcon.close()

        trace_entry = {
            "node": "reviewer",
            "status": "SEMANTIC_REJECTION",
            "critique": critique_msg,
            "retry_count": state.retry_count + 1,
        }
        return {
            "compiler_error": f"Semantic Review Critique: {critique_msg}",
            "retry_count": state.retry_count + 1,
            "traces": state.traces + [trace_entry],
        }

    # 5. Broadcast success and usage instructions to players in-game
    await rcon.broadcast_chat(
        f"Successfully loaded [{state.target_scope}]: {evaluation.user_summary}",
        color="green",
    )
    for instruction in evaluation.usage_instructions:
        await rcon.broadcast_chat(f"-> {instruction}", color="aqua")

    await rcon.close()

    trace_entry = {
        "node": "reviewer",
        "status": "APPROVED",
        "user_summary": evaluation.user_summary,
        "usage_instructions": evaluation.usage_instructions,
        "applied_files": applied_files,
    }

    return {
        "compiler_error": None,
        "reviewer_feedback": evaluation.user_summary,
        "usage_instructions": evaluation.usage_instructions,
        "traces": state.traces + [trace_entry],
    }