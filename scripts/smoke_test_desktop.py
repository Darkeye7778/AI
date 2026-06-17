"""Headless-ish smoke test: init app, verify core imports, exit."""
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

errors = []


def test_imports():
    import sqlalchemy
    from assistant.db.database import init_db
    from assistant.agent.loop import AgentLoop
    from assistant.ui.desktop import DesktopApp
    init_db()
    AgentLoop()
    print("imports OK")


def test_desktop_init():
    import customtkinter as ctk
    from assistant.ui.desktop import DesktopApp

    app = DesktopApp()
    assert app.chat_row >= 1, "welcome bubble should increment chat_row"
    app.destroy()
    print("desktop init OK")


if __name__ == "__main__":
    for name, fn in [("imports", test_imports), ("desktop_init", test_desktop_init)]:
        try:
            fn()
        except Exception as e:
            errors.append(f"{name}: {e}\n{traceback.format_exc()}")
            print(f"FAIL {name}: {e}")

    if errors:
        log = ROOT / "data" / "smoke_test_failures.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("\n\n".join(errors), encoding="utf-8")
        print(f"SMOKE TEST FAILED — see {log}")
        sys.exit(1)
    print("ALL SMOKE TESTS PASSED")
    sys.exit(0)