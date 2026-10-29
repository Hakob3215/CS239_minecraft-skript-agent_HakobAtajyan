# Minecraft Skript Agent
Multi-agent software engineering system that enables Minecraft players to create, update, and repair server-side Skript mechanics in real time through in-game chat.

## Workspace Layout
When unpacked, the archive provides `src/` and `tests/`. Because server binaries, live worlds, and credentials cannot be bundled, the evaluator must supply an external PaperMC server directory named `mc_server/` at the root alongside `src/`:

```text
extracted_root/
├── mc_server/                  # Evaluator-created Minecraft server
│   ├── paper.jar               # PaperMC 1.21.5+ server binary
│   ├── eula.txt                # eula=true
│   ├── server.properties       # RCON enabled
│   └── plugins/
│       └── Skript.jar          # Skript 2.17.1+ plugin binary
├── src/                        # Packaged agent application & assets
│   ├── .env                    # Evaluator-created credentials file
│   ├── data/
│   │   ├── skript_knowledge.db # Pre-indexed SQLite FTS5 documentation
│   │   └── event_manifest.json # Skript event catalog
│   ├── traces/                 # Recorded execution traces
│   ├── agent_system/           # Application source code
│   ├── pyproject.toml          # Project configuration & dependencies
│   ├── uv.lock                 # Locked dependency tree
│   ├── start.sh                # Automated launcher (Bash / macOS / Linux)
│   └── start.ps1               # Automated launcher (PowerShell / Windows)
└── tests/
    └── test_agent_system.py    # Offline unit test suite
```

## Prerequisites

- **Operating System:** Windows, macOS, or Linux
- **Python:** Version 3.12 or newer
- **Package Manager:** `uv` (recommended) or standard `pip`
- **Java:** OpenJDK 21 or newer (required to execute PaperMC)
- **API Access:** Google Gemini API key with access to `gemini-3.8-flash` or `gemini-3.1-flash-lite`

## Step 1: Python Environment & Offline Testing
All unit tests run completely offline with mocked RCON sockets and mocked LLM nodes. No running Minecraft server or API key is required to execute the test suite.

From the root directory:

```bash
# 1. Sync isolated dependencies
uv sync --project src

# 2. Run unit tests
PYTHONPATH=src uv run --project src python -m unittest discover -s tests -t .
```

On Windows PowerShell:

```powershell
uv sync --project src
$env:PYTHONPATH = "src"
uv run --project src python -m unittest discover -s tests -t .
```

*Expected output:* `Ran 11 tests ... OK`

## Step 2: PaperMC Server Setup

1. **Create the Server Directory:**
   Create a directory named `mc_server` directly beside `src/` and `tests/`:

   ```bash
   mkdir mc_server
   cd mc_server
   ```

2. **Download PaperMC 1.21.5:**
   Download the PaperMC server binary for version 1.21.5 directly from the [PaperMC Download Portal](https://fill-ui.papermc.io/projects/paper/version/1.21.5). Save the downloaded jar file directly into `mc_server/` as `paper.jar`.

3. **Accept EULA:**
   Run the jar once to generate the initial server configuration files:

   ```bash
   java -jar paper.jar --nogui
   ```

   Open the generated `eula.txt` file and set:

   ```properties
   eula=true
   ```

4. **Install Skript Plugin:**
   Download the official Skript release compatible with 1.21.5 from [Skript Releases](https://github.com/skriptlang/skript/releases). Place the downloaded plugin jar file into:

   ```text
   mc_server/plugins/Skript.jar
   ```

5. **Configure RCON in `server.properties`:**
   Open `mc_server/server.properties` and verify or set:

   ```properties
   enable-rcon=true
   rcon.port=25575
   rcon.password=change-me-local
   broadcast-rcon-to-ops=false
   ```

## Step 3: Environment Configuration
Create a file named `.env` inside the `src/` directory:

```bash
# File: src/.env
GOOGLE_API_KEY=your-gemini-api-key-here
RCON_HOST=127.0.0.1
RCON_PORT=25575
RCON_PASSWORD=change-me-local
SWE_MODEL=gemini-3.8-flash
```

### Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | Yes | None | API key for Google Gemini model inference. |
| `RCON_PASSWORD` | Yes | None | RCON authentication password configured in `server.properties`. |
| `RCON_HOST` | No | `127.0.0.1` | Host address of the PaperMC server. |
| `RCON_PORT` | No | `25575` | TCP port configured for RCON. |
| `SWE_MODEL` | No | `gemini-3.8-flash` | Model selection (`gemini-3.8-flash` or `gemini-3.1-flash-lite`). |
| `MC_SERVER_DIR` | No | `../mc_server` | Path to the server root; defaults to a sibling `mc_server` folder. |

## Step 4: Running the Application
You can run the system using the combined automated launcher or in two separate terminal windows.

### Method A: Automated Launcher (Recommended)
The launcher boots PaperMC, polls the log and socket until both the server engine and RCON are fully initialized, and then automatically spawns the multi-agent daemon:

- **Linux / macOS / Git Bash:**

  ```bash
  cd src
  chmod +x start.sh
  ./start.sh
  ```

- **Windows PowerShell:**

  ```powershell
  cd src
  .\start.ps1
  ```

Pressing `Ctrl+C` terminates both the Minecraft server and the background agent process cleanly.

### Method B: Manual Two-Terminal Execution

#### Terminal 1: Launch PaperMC Server

```bash
cd mc_server
java -Xms2G -Xmx2G -jar paper.jar --nogui
```

Wait until the console outputs `Done (X.XXs)! For help, type "help"`.

#### Terminal 2: Launch Agent System
From the root directory:

```bash
PYTHONPATH=src uv run --project src python -m agent_system.main
```

## In-Game Usage & Verification

1. Connect to `localhost` using a Minecraft 1.21.5 client.
2. Ensure your player is an operator (`op <username>` in the server console) or has permission to run chat triggers.
3. Submit a feature request using one of the three command triggers:

**Creation:**

```text
!create a custom firework rocket named &bTeleport Elytra that teleports the user to the closest ground on left click
```

**Modification:**

```text
!update tp_elytra.sk to play an enderman teleport sound and particle effect when teleporting
```

**Self-Healing / Fix:**

```text
!fix resolve the variable syntax errors in items/tp_elytra.sk
```

The lifecycle is:

- The Secretary Agent triages the intent and resolves target script paths.
- The SWE Agent queries `src/data/skript_knowledge.db` via FTS5 and writes the `.sk` buffer.
- The Reviewer Agent validates sandbox constraints, applies disk writes to `mc_server/plugins/Skript/scripts/`, and triggers `/skript reload` via RCON.
- If compilation fails, the Reviewer routes the error trace back to the SWE Agent for up to three repair iterations.
- On approval, usage instructions are broadcast to in-game chat and an auditable trace is recorded in `src/traces/`.

## Limitations & Edge Cases

- **Live Compilation Oracle:** Closed-loop syntax verification requires an active PaperMC instance running the Skript plugin; without RCON connectivity, changes cannot be compiled or verified.
- **Vanilla Skript DSL Scope:** To maintain deterministic stability, the prompt strictly enforces vanilla Skript patterns. Third-party addons such as SkBee or SkQuery and raw NBT parsing are prohibited.
- **Bounded Retries:** The self-healing loop enforces a maximum threshold of three compiler retry attempts. If the script fails compilation three times, the transaction halts and an explicit failure is logged to prevent runaway token expenditure.
