#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$ROOT_DIR/../mc_server" && pwd)"
LOG_PATH="$SERVER_DIR/logs/latest.log"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
    echo "Missing $ROOT_DIR/.env. Copy .env.example to .env and set GOOGLE_API_KEY and RCON_PASSWORD." >&2
    exit 1
fi

PYTHON_ARGS=()
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/Scripts/python.exe"
elif command -v uv >/dev/null 2>&1; then
    PYTHON_BIN="uv"
    PYTHON_ARGS=(run python)
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "No Python interpreter found. Run 'uv sync' from agent_system first." >&2
    exit 1
fi

if [[ ! -f "$SERVER_DIR/paper.jar" ]]; then
    echo "Missing mc_server/paper.jar. Install PaperMC before starting the combined launcher." >&2
    exit 1
fi

# Remove stale log from previous runs so we only detect this session's startup
rm -f "$LOG_PATH" 2>/dev/null || true

server_pid=""
agent_pid=""

cleanup() {
    trap - INT TERM EXIT
    if [[ -n "$agent_pid" ]] && kill -0 "$agent_pid" 2>/dev/null; then
        kill "$agent_pid" 2>/dev/null || true
    fi
    if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
        kill "$server_pid" 2>/dev/null || true
    fi
}
trap cleanup INT TERM EXIT

echo "[+] Starting PaperMC server..."
(
    cd "$SERVER_DIR"
    exec java -Xms2G -Xmx2G -jar paper.jar --nogui
) &
server_pid=$!
echo "[+] PaperMC PID: $server_pid"

echo "[+] Waiting for PaperMC to report readiness..."
server_ready=false

# Wait up to 120 seconds (120 * 1s)
for _ in $(seq 1 120); do
    if ! kill -0 "$server_pid" 2>/dev/null; then
        echo "PaperMC exited before reporting readiness." >&2
        exit 1
    fi

    # Check if this run has logged "Done ("
    if [[ -f "$LOG_PATH" ]] && grep -q "Done (" "$LOG_PATH" 2>/dev/null; then
        # Check RCON port once after Done is logged
        if (echo >/dev/tcp/127.0.0.1/25575) >/dev/null 2>&1; then
            server_ready=true
            break
        fi
    fi

    sleep 1
done

if [[ "$server_ready" != true ]]; then
    echo "Timed out waiting for PaperMC Done log and RCON readiness." >&2
    exit 1
fi

echo "[+] PaperMC is online and RCON is ready."
echo "[+] Starting the Minecraft assistant..."
(
    cd "$ROOT_DIR"
    exec "$PYTHON_BIN" "${PYTHON_ARGS[@]}" -m agent_system.main
) &
agent_pid=$!
echo "[+] Assistant process started (PID: $agent_pid)."
echo "[+] Both processes are running. Press Ctrl+C to stop both."

wait "$agent_pid"