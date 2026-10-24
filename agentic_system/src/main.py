import sys
from pathlib import Path

# Add project root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from datetime import datetime
import json
import re

from agentic_system.src.bridge.log_tailer import LogTailer
from agentic_system.src.bridge.rcon_client import RconClient
from agentic_system.src.graph import create_agent_graph
from agentic_system.src.state import AgentState

TRACES_DIR = ROOT_DIR / "agentic_system" / "traces"


def save_trace_log(trigger_player: str, initial_state: AgentState, final_state: dict) -> Path:
    """Serializes the complete run state and trace history to agentic_system/traces/."""
    TRACES_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scope = final_state.get("target_scope", "unknown")
    scope_slug = re.sub(r"[^a-zA-Z0-9_]", "_", scope.replace(".sk", ""))
    filename = f"{timestamp}_{scope_slug}.json"
    file_path = TRACES_DIR / filename

    # Serialize mutations
    mutations_dump = []
    for m in final_state.get("mutations", []):
        if hasattr(m, "model_dump"):
            mutations_dump.append(m.model_dump())
        elif isinstance(m, dict):
            mutations_dump.append(m)

    payload = {
        "timestamp": datetime.now().isoformat(),
        "player": trigger_player,
        "action_type": final_state.get("action_type"),
        "raw_prompt": initial_state.raw_prompt,
        "target_scope": final_state.get("target_scope"),
        "success": final_state.get("compiler_error") is None,
        "compiler_error": final_state.get("compiler_error"),
        "reviewer_feedback": final_state.get("reviewer_feedback"),
        "usage_instructions": final_state.get("usage_instructions", []),
        "retry_count": final_state.get("retry_count", 0),
        "mutations": mutations_dump,
        "traces": final_state.get("traces", []),
    }

    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path


async def run_agent_daemon():
    print("=" * 60)
    print("  AUTONOMOUS MINECRAFT SKRIPT AGENT (LangGraph + Gemini)")
    print("=" * 60)

    app = create_agent_graph()
    tailer = LogTailer(Path("server/logs/latest.log"))
    loop = asyncio.get_running_loop()

    tailer.start(loop)
    print("[+] Bridge active. Listening for in-game triggers (!create, !update, !fix)...")
    print("[+] Press Ctrl+C in terminal to stop daemon.\n")

    try:
        async for trigger in tailer.watch():
            print(f"\n[!] Trigger intercepted from <{trigger.player}>: !{trigger.action} {trigger.prompt}")

            try:
                rcon = RconClient()
                await rcon.connect()
                await rcon.broadcast_chat(
                    f"Agent processing request from {trigger.player}...",
                    color="yellow"
                )
                await rcon.close()
            except Exception as e:
                print(f"[!] Warning: Failed to send initial in-game notice: {e}")

            initial_state = AgentState(
                raw_prompt=f"!{trigger.action.lower()} {trigger.prompt}",
                action_type=trigger.action,
            )

            try:
                final_state = await app.ainvoke(initial_state)

                # Persist the trace file to disk
                saved_path = save_trace_log(trigger.player, initial_state, final_state)
                print(f"[+] Saved execution trace to: {saved_path.relative_to(ROOT_DIR)}")

                if final_state.get("compiler_error"):
                    print(f"[-] Workflow finished with unresolved errors after {final_state.get('retry_count')} retries.")
                    rcon = RconClient()
                    await rcon.connect()
                    await rcon.broadcast_chat(
                        f"Failed to compile [{final_state.get('target_scope')}]. Check console for details.",
                        color="red"
                    )
                    await rcon.close()
                else:
                    print(f"[+] Successfully handled task for scope: {final_state.get('target_scope')}")
                    print(f"    Trace steps: {[t['node'] for t in final_state.get('traces', [])]}")

            except Exception as err:
                print(f"[-] Execution error in agent graph: {err}")
                try:
                    rcon = RconClient()
                    await rcon.connect()
                    await rcon.broadcast_chat(f"Internal error processing request: {err}", color="red")
                    await rcon.close()
                except Exception:
                    pass

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down daemon...")
    finally:
        tailer.stop()
        print("[+] Log watcher closed. Daemon terminated.")


if __name__ == "__main__":
    asyncio.run(run_agent_daemon())