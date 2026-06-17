"""Simulate frozen exe paths before rebuilding."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

sys.frozen = True
sys.executable = str(ROOT / "dist" / "PersonalAssistant.exe")

# Force reimport with frozen paths
for mod in list(sys.modules):
    if mod.startswith("assistant"):
        del sys.modules[mod]

from assistant.main import run_smoke
raise SystemExit(run_smoke())