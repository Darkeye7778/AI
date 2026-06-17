import subprocess

from assistant.tools.registry import Tool, ToolRegistry
from assistant.workspace.context import get_workspace

ALLOWED_COMMANDS = {
    "python", "pip", "pytest", "git", "dir", "ls", "type", "cat", "echo",
    "npm", "node", "npx", "cargo", "go", "make", "gradle", "gradlew", "mvn",
}


def _run_command(command: str, cwd: str = "") -> str:
    parts = command.strip().split()
    if not parts:
        return "Empty command"
    if parts[0].lower().rstrip(".cmd").rstrip(".exe") not in ALLOWED_COMMANDS:
        return f"Command '{parts[0]}' not in allowlist: {sorted(ALLOWED_COMMANDS)}"

    ws = get_workspace()
    work_dir = cwd or (str(ws.root) if ws else None)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=work_dir,
        )
        output = result.stdout + result.stderr
        header = f"exit_code={result.returncode}\n"
        return header + (output[:6000] or "(no output)")
    except subprocess.TimeoutExpired:
        return "Command timed out after 60s"
    except Exception as e:
        return f"Shell error: {e}"


def register_shell_tools(registry: ToolRegistry) -> None:
    registry.register(Tool(
        name="run_command",
        description="Run test/build/debug commands in the project directory. Use terminal output to fix errors.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
            },
            "required": ["command"],
        },
        handler=_run_command,
    ))