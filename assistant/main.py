"""Entry point — desktop app by default (local, like ChatGPT)."""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.config import ROOT_DIR, settings, validate_installation
from assistant.db.database import init_db
from assistant.memory.store import MemoryStore


def run_smoke() -> int:
    """Non-GUI checks for debugging the frozen exe."""
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"Frozen: {getattr(sys, 'frozen', False)}")
    print(f"Executable: {sys.executable}")
    print(f"Model: {settings.llm_model_path} exists={settings.llm_model_path.exists()}")
    print(f"Data: {settings.data_dir}")
    print(f"DB: {settings.db_path}")

    issues = validate_installation()
    if issues:
        for i in issues:
            print(f"ISSUE: {i}")
        return 1

    init_db()
    print("DB init OK")

    from assistant.ui.desktop import DesktopApp
    app = DesktopApp()
    app.destroy()
    print("Desktop init OK")

    from assistant.agent.loop import AgentLoop
    agent = AgentLoop()
    result = agent.chat("Reply with exactly one word: pong")
    print(f"Chat OK: {result['response'][:120]!r}")
    return 0


def run_desktop():
    from assistant.ui.desktop import run_desktop as _run
    _run()


def run_cli():
    from assistant.agent.loop import AgentLoop
    init_db()
    agent = AgentLoop()
    memory = MemoryStore()
    memory.migrate_legacy_json(settings.legacy_memory_path)

    print("Personal AI Assistant (CLI)")
    print("Talk normally, or: remember <key>=<value> | recall <key> | quit")
    print("-" * 40)

    session_id = None
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        if user_input.startswith("remember "):
            _, keyval = user_input.split(" ", 1)
            key, val = keyval.split("=", 1)
            memory.create(val.strip(), title=key.strip(), source="explicit_user_save")
            print(f"Saved: {key.strip()}")
            continue

        if user_input.startswith("recall "):
            key = user_input.split(" ", 1)[1].strip()
            hits = memory.search(key, limit=3)
            if hits:
                for h in hits:
                    print(f"  [{h['title']}] {h['content'][:200]}")
            else:
                print("  Nothing found.")
            continue

        result = agent.chat(user_input, session_id=session_id, mode="safe")
        session_id = result["session_id"]
        print(f"Assistant: {result['response']}")


def run_server():
    import uvicorn
    init_db()
    uvicorn.run("assistant.api.app:app", host=settings.host, port=settings.port, reload=False)


def main():
    parser = argparse.ArgumentParser(description="Personal AI Assistant — local desktop app")
    parser.add_argument(
        "mode", nargs="?", default="desktop",
        choices=["desktop", "cli", "web", "smoke"],
        help="desktop (default) | cli | web | smoke (debug)",
    )
    args = parser.parse_args()

    try:
        if args.mode == "smoke":
            sys.exit(run_smoke())
        if args.mode == "desktop":
            run_desktop()
        elif args.mode == "cli":
            run_cli()
        else:
            run_server()
    except Exception:
        log = settings.data_dir / "crash.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(traceback.format_exc(), encoding="utf-8")
        print(traceback.format_exc())
        print(f"Saved to {log}")
        sys.exit(1)


if __name__ == "__main__":
    main()