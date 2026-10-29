# Minecraft Skript Agent

Minecraft Skript Agent is a multi-agent software engineering system for Minecraft PaperMC servers using the Skript plugin.

Players can submit requests through Minecraft chat using:

```text
!create ...
!update ...
!fix ...
```

The application interprets the request, identifies the relevant Skript file, retrieves Skript documentation, generates or repairs Skript code, validates the change, reloads it through Minecraft RCON, and reports the result back in-game.

---

## Phase 1 Deliverables

| Rubric Deliverable | Repository Location | Description |
| :--- | :--- | :--- |
| **Demo Video** | [YouTube (5 min)](https://www.youtube.com/watch?v=Kr84olc-k2k) | Video demonstration of architecture, live chat triggers, self-healing, and traces. |
| **Application Overview** | `submission/requirements/minecraft-skript-agent/app.md` | Core purpose, live server architecture, and supported in-game commands. |
| **System Policies** | `submission/requirements/minecraft-skript-agent/policy.md` | Application policies covering sandboxing, command blacklists, and compiler gates. |
| **Tool Manifest** | `submission/requirements/minecraft-skript-agent/tools.md` | Signatures, inputs, and outputs for all FTS5, RCON, file, and broadcast tools. |
| **Agent Prompts** | `submission/requirements/minecraft-skript-agent/agents/` | System prompts and tool allocations for Secretary, SWE, and Reviewer agents. |
| **Example Episodes** | `submission/requirements/minecraft-skript-agent/episodes/` | Documented walkthroughs of feature creation, syntax repair, and retry bounds. |
| **Requirements** | `submission/requirements/minecraft-skript-agent/requirements.md` | Functional specifications and explicit negative constraints. |
| **Phase 1 Source** | `src/agent_system/` | Multi-agent LangGraph application code. |
| **Unit Tests** | `tests/` | 11 offline test cases verifying mocked RCON, safety checks, and graph transitions. |
| **Execution Traces** | `src/traces/` | Complete JSON execution traces from live runs on PaperMC. |
| **Trace Explanations** | `src/traces/README.md` | Scenario breakdown detailing live compiler errors and trace outcomes. |

---

## System Overview

The system coordinates three specialized agents:

1. **Secretary Agent** — Routes the request, selects the target file or directory, identifies relevant Skript events, and loads workspace context.
2. **SWE Agent** — Generates or repairs Skript source code using a Gemini model and the local Skript documentation database.
3. **Reviewer Agent** — Validates file safety, applies mutations, reloads scripts through RCON, performs semantic review, broadcasts usage instructions, and records execution traces.

---

## Repository Layout

```text
minecraft-skript-agent/
├── README.md                         # This file
├── LICENSE                           # Project license
│
├── agent_system/                     # Canonical application project
│   ├── .env                          # Local credentials; not committed or submitted
│   ├── pyproject.toml                # Python project configuration and dependencies
│   ├── uv.lock                       # Locked dependency versions
│   ├── start.ps1                     # Windows combined launcher
│   ├── start.sh                      # Linux/macOS/Git Bash combined launcher
│   │
│   ├── data/                         # Documentation and event data
│   │   ├── docs.json                 # Source Skript documentation
│   │   ├── event_manifest.json       # Skript event catalog
│   │   └── skript_knowledge.db       # SQLite FTS5 documentation database
│   │
│   ├── src/agent_system/             # Python application package
│   │   ├── agents/
│   │   │   ├── secretary.py          # Secretary Agent
│   │   │   ├── swe.py                # SWE/code-generation Agent
│   │   │   └── reviewer.py           # Safety, compilation, and review Agent
│   │   │
│   │   ├── bridge/
│   │   │   ├── log_tailer.py         # Minecraft log watcher and chat parser
│   │   │   └── rcon_client.py        # Minecraft RCON client
│   │   │
│   │   ├── db/
│   │   │   ├── ingest.py             # Builds the event manifest and SQLite database
│   │   │   └── retriever.py          # Searches Skript documentation using FTS5
│   │   │
│   │   ├── graph.py                  # LangGraph workflow and retry routing
│   │   ├── main.py                   # Main daemon entry point and trace logging
│   │   ├── paths.py                  # Project, server, data, log, and script paths
│   │   └── state.py                  # AgentState and FileMutation schemas
│   │
│   ├── tests/
│   │   └── test_agent_system.py      # Offline unit test suite
│   │
│   └── traces/
│       ├── README.md                 # Explanation of verified execution traces
│       └── *.json                    # Recorded execution traces
│
├── mc_server/                        # Local PaperMC development server
│   ├── paper.jar                     # Server binary; not submitted
│   ├── logs/
│   │   └── latest.log                # Monitored by the application
│   └── plugins/
│       └── Skript/
│           └── scripts/              # Generated and modified .sk files
│
├── submission/                       # Submission staging directories
│   ├── requirements/
│   │   └── minecraft-skript-agent/
│   │       ├── app.md                # Application description
│   │       ├── policy.md             # Application policies
│   │       ├── tools.md              # Tool descriptions
│   │       ├── agents/               # Agent descriptions and exact prompts
│   │       └── episodes/             # Trace-grounded example episodes
│   │
│   └── whole/
│       ├── src/
│       │   ├── README.md             # Evaluator setup instructions
│       │   ├── pyproject.toml
│       │   ├── uv.lock
│       │   ├── start.ps1
│       │   ├── start.sh
│       │   ├── agent_system/
│       │   ├── data/
│       │   └── traces/
│       │
│       └── tests/
│           └── test_agent_system.py
│
├── HakobAtajyan-minecraft-skript-agent-005991892-requirements.tar.gz
└── HakobAtajyan-minecraft-skript-agent-005991892-whole.tar.gz
```

---

## Main Application Workflow

The application follows this workflow:

```text
Minecraft chat message
        |
        v
Minecraft logs/latest.log
        |
        v
LogTailer parses !create, !update, or !fix
        |
        v
AgentState is created
        |
        v
Secretary Agent
        |
        v
SWE Agent
        |
        v
Reviewer Agent
        |
        +--> Validate file paths and dangerous commands
        |
        +--> Write or delete .sk files
        |
        +--> Reload Skript through RCON
        |
        +--> Return compiler errors for retries
        |
        +--> Perform semantic review
        |
        v
Minecraft chat feedback
        |
        v
JSON execution trace
```

The workflow is implemented in [agent_system/src/agent_system/graph.py](agent_system/src/agent_system/graph.py).

The main daemon is implemented in [agent_system/src/agent_system/main.py](agent_system/src/agent_system/main.py).

---

## Agents

### Secretary Agent

The Secretary Agent is responsible for request triage:

- Reads active Skript files
- Resolves the target file or directory
- Determines the request scope
- Selects candidate Skript events
- Loads relevant existing source files
- Passes the workspace context to the SWE Agent

Implementation: `agent_system/src/agent_system/agents/secretary.py`

### SWE Agent

The SWE Agent is responsible for generating or repairing Skript code:

- Searches the local Skript documentation database
- Receives existing workspace files
- Receives compiler errors during retries
- Generates structured `FileMutation` objects
- Returns complete `.sk` source code
- Explains its implementation rationale

Implementation: `agent_system/src/agent_system/agents/swe.py`

### Reviewer Agent

The Reviewer Agent is responsible for safety, compilation, and semantic approval:

- Rejects paths outside the Skript scripts sandbox
- Rejects non-`.sk` files
- Rejects dangerous server-control commands
- Writes validated mutations to disk
- Reloads Skript through RCON
- Returns compiler errors to the SWE Agent
- Performs semantic review
- Broadcasts success and usage instructions
- Records the final workflow state

Implementation: `agent_system/src/agent_system/agents/reviewer.py`

---

## RCON Integration

RCON allows the Python application to communicate with the Minecraft server console.

The RCON client is implemented in: `agent_system/src/agent_system/bridge/rcon_client.py`

It supports:

```text
connect()
send_command(command)
reload_script(path)
broadcast_chat(message, color)
close()
```

The application uses RCON to:

- Reload generated Skript files
- Read PaperMC/Skript compiler output
- Broadcast status messages
- Broadcast generated usage instructions
- Report final failures

Required environment variables include:

```text
RCON_PASSWORD=your-local-password
```

Optional variables include:

```text
RCON_HOST=127.0.0.1
RCON_PORT=25575
```

RCON must be enabled in the external PaperMC server's `server.properties`:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=your-local-password
```

---

## Documentation Database

The application uses a local SQLite FTS5 database to provide Skript syntax context to the SWE Agent.

The relevant files are:

```text
agent_system/data/docs.json
agent_system/data/event_manifest.json
agent_system/data/skript_knowledge.db
```

* `docs.json` — Contains the source Skript documentation.
* `event_manifest.json` — Contains lightweight Skript event definitions used by the Secretary Agent.
* `skript_knowledge.db` — Contains the indexed documentation table (`skript_docs`) storing IDs, categories, names, syntax patterns, descriptions, and examples.

The database retriever is implemented in: `agent_system/src/agent_system/db/retriever.py`  
The database builder is implemented in: `agent_system/src/agent_system/db/ingest.py`

To rebuild the database after changing `docs.json`:

```powershell
cd agent_system
$env:PYTHONPATH = "src"
uv run python -m agent_system.db.ingest
```

---

## Minecraft Server Files

The application expects a PaperMC server directory with this general layout:

```text
mc_server/
├── paper.jar
├── eula.txt
├── server.properties
├── logs/
│   └── latest.log
└── plugins/
    └── Skript/
        └── scripts/
```

Generated Skript files are written under:

```text
mc_server/plugins/Skript/scripts/
```

For example:

```text
mc_server/plugins/Skript/scripts/items/tp_elytra.sk
mc_server/plugins/Skript/scripts/mobs/vengeful_creeper.sk
```

The application does not intentionally include server worlds, server binaries, credentials, or the local Python virtual environment in the submission archives.

---

## Environment Variables

Create a local `.env` file inside `agent_system/` for development:

```text
GOOGLE_API_KEY=your-Gemini-api-key
RCON_HOST=127.0.0.1
RCON_PORT=25575
RCON_PASSWORD=your-local-rcon-password
SWE_MODEL=gemini-3.1-flash-lite
MC_SERVER_DIR=C:\path\to\mc_server
```

Important:

- Never commit `.env`.
- Never include real credentials in traces.
- Never place API keys or RCON passwords in Skript files.
- `RCON_PASSWORD` is required for live execution.
- `GOOGLE_API_KEY` is required for LLM-powered execution.
- `MC_SERVER_DIR` can point to an external server directory.

---

## Running the Canonical Application

From the repository root:

```powershell
cd agent_system
uv sync
$env:PYTHONPATH = "src"
uv run python -m agent_system.main
```

The application then listens for Minecraft chat requests. Example:

```text
!create make a custom golden helmet that grants absorption
```

The daemon detects the message, processes it through the agents, reloads the generated script, and reports the result in Minecraft chat.

---

## Running with the Combined Launcher

### Windows PowerShell

```powershell
cd agent_system
.\start.ps1
```

The PowerShell launcher:
1. Starts PaperMC.
2. Waits for the server to report `Done`.
3. Waits for the RCON port.
4. Starts the agent daemon.
5. Stops both processes when the launcher exits.

### Linux, macOS, or Git Bash

```bash
cd agent_system
chmod +x start.sh
./start.sh
```

The Bash launcher provides equivalent behavior.

---

## Running Offline Tests

The unit tests do not require:

- A running Minecraft server
- A Minecraft client
- An RCON connection
- A live Gemini API key
- Live LLM responses

From the repository root:

```powershell
cd agent_system
uv run python -m unittest discover -s tests -t .
```

Expected result:

```text
Ran 11 tests
OK
```

The tests cover:

- Shared state schemas
- File mutation validation
- Chat trigger parsing
- Documentation query sanitization
- RCON command formatting
- Path traversal rejection
- Dangerous command rejection
- File mutation application
- Graph success routing
- Graph retry routing
- Trace serialization

---

## Execution Traces

Execution traces are stored in: `agent_system/traces/`  
The trace documentation is: `agent_system/traces/README.md`

Each trace records:

- Player name
- Action type
- Original request
- Target script scope
- Whether the request succeeded
- Compiler errors
- Retry count
- File mutations
- Agent execution steps
- Reviewer feedback
- Player usage instructions

The selected submission traces demonstrate:

* `20261028_175529_items_tp_elytra.json` — Successful Teleport Elytra creation after one compiler repair.
* `20261028_185955_mobs_vengeful_creeper.json` — Successful Vengeful Creeper repair on the first attempt.
* `20261028_183635_mobs_vengeful_creeper.json` — Vengeful Creeper creation rejected after three failed compiler retries.

---

## Submission Archives

The repository contains two CS239 submission archives.

### Requirements archive

Filename: `HakobAtajyan-minecraft-skript-agent-005991892-requirements.tar.gz`

```text
minecraft-skript-agent/
├── app.md
├── policy.md
├── tools.md
├── agents/
└── episodes/
```

This archive documents application purpose, policies, tools, agents, actual system prompts, and example execution episodes.

### Whole archive

Filename: `HakobAtajyan-minecraft-skript-agent-005991892-whole.tar.gz`

```text
src/
├── README.md
├── pyproject.toml
├── uv.lock
├── start.ps1
├── start.sh
├── agent_system/
├── data/
└── traces/

tests/
└── test_agent_system.py
```

The whole archive contains the application source, dependency configuration, tests, documentation data, selected traces, and evaluator setup instructions.

---

## Safety and Retry Behavior

The application enforces several safety boundaries:

1. Mutations must stay inside the Skript scripts directory.
2. Only `.sk` files may be modified.
3. Dangerous server-control commands are rejected.
4. Files are validated before being written or reloaded.
5. Success is reported only after compilation and semantic review.
6. Compiler errors are sent back to the SWE Agent.
7. The workflow stops after three retry attempts.
8. Failed requests are recorded in traces.

The application is intended to make controlled changes to a test Minecraft server. It should not be connected to a production server without additional operational safeguards.
