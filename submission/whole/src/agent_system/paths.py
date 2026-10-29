import os
from pathlib import Path


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_CANDIDATES = (
    Path(__file__).resolve().parents[2],
    _PACKAGE_ROOT,
)
PROJECT_ROOT = next(
    (candidate for candidate in _PROJECT_CANDIDATES if (candidate / "data").exists()),
    _PACKAGE_ROOT,
)
MC_SERVER_DIR = Path(
    os.getenv("MC_SERVER_DIR", str(PROJECT_ROOT.parent / "mc_server"))
)
DATA_DIR = PROJECT_ROOT / "data"
TRACES_DIR = PROJECT_ROOT / "traces"
SCRIPTS_ROOT = MC_SERVER_DIR / "plugins" / "Skript" / "scripts"
LOG_PATH = MC_SERVER_DIR / "logs" / "latest.log"
