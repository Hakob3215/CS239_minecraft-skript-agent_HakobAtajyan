from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MC_SERVER_DIR = PROJECT_ROOT.parent / "mc_server"
DATA_DIR = PROJECT_ROOT / "data"
TRACES_DIR = PROJECT_ROOT / "traces"
SCRIPTS_ROOT = MC_SERVER_DIR / "plugins" / "Skript" / "scripts"
LOG_PATH = MC_SERVER_DIR / "logs" / "latest.log"
