## Phase 1 

| Rubric Deliverable | Repository Location | Description |
| :--- | :--- | :--- |
| **Demo Video** | [YouTube (5 min)](https://www.youtube.com/watch?v=Kr84olc-k2k) | Video demonstration of architecture, live chat triggers, self-healing, and traces. |
| **Application Overview** | `submission/requirements/minecraft-skript-agent/app.md` | Core purpose, live server architecture, and supported in-game commands. |
| **System Policies** | `submission/requirements/minecraft-skript-agent/policy.md` | Formatted policies (P1–P8) covering sandboxing, command blacklists, and compiler gates. |
| **Tool Manifest** | `submission/requirements/minecraft-skript-agent/tools.md` | Signatures, inputs, and outputs for all FTS5, RCON, file, and broadcast tools. |
| **Agent Prompts** | `submission/requirements/minecraft-skript-agent/agents/` | System prompts and tool allocations for Secretary, SWE, and Reviewer agents. |
| **Example Episodes** | `submission/requirements/minecraft-skript-agent/episodes/` | Documented walkthroughs of feature creation, syntax repair, and retry bounds. |
| **Requirements** | `submission/requirements/minecraft-skript-agent/requirements.md` | Functional specifications and explicit negative constraints. |
| **Phase 1 Source** | `src/agent_system/` | Multi-agent LangGraph application code. |
| **Unit Tests** | `tests/` | 11 offline test cases verifying mocked RCON, safety checks, and graph transitions. |
| **Execution Traces** | `src/traces/` | Complete JSON execution traces from live runs on PaperMC. |
| **Trace Explanations** | `src/traces/README.md` | Scenario breakdown detailing live compiler errors and policy triggers. |
