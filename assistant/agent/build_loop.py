from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from assistant.llm.router import LLMRouter
from assistant.memory.retrieval import ContextRetriever
from assistant.memory.store import MemoryStore
from assistant.tools.filesystem import register_filesystem_tools
from assistant.tools.memory_search import register_memory_tools
from assistant.tools.registry import ToolRegistry
from assistant.tools.shell import register_shell_tools
from assistant.workspace.context import set_workspace
from assistant.workspace.manager import ProjectWorkspace
from assistant.workspace.retrieval import RelevantFileFinder

TOOL_PATTERN = re.compile(r"TOOL:(\w+)\s*(\{.*\})", re.DOTALL)


@dataclass
class BuildResult:
    plan: str = ""
    response: str = ""
    phases: list[dict] = field(default_factory=list)
    files_changed: list[dict] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    relevant_files: list[dict] = field(default_factory=list)
    project_scan: dict = field(default_factory=dict)


class BuildLoop:
    """
    Grok Build-style pipeline:
    chat request → project scan → relevant file retrieval → plan → file edits → command run → summary
    """

    def __init__(self):
        self.llm = LLMRouter()
        self.memory = MemoryStore()
        self.retriever = ContextRetriever(self.memory)
        self.tools = ToolRegistry()
        register_filesystem_tools(self.tools)
        register_memory_tools(self.tools, self.memory)
        register_shell_tools(self.tools)

    def run(
        self,
        user_message: str,
        project_path: str,
        mode: str = "safe",
        max_tool_rounds: int = 10,
        auto_test: bool = True,
    ) -> BuildResult:
        workspace = ProjectWorkspace(project_path)
        set_workspace(workspace)

        result = BuildResult()

        # Phase 1: Scan
        result.project_scan = workspace.scan()
        result.phases.append({"phase": "scan", "status": "done", "files": result.project_scan["file_count"]})

        # Phase 2: Relevant file retrieval
        finder = RelevantFileFinder(workspace)
        result.relevant_files = finder.find(user_message, limit=8)
        result.phases.append({"phase": "retrieve", "status": "done", "files": len(result.relevant_files)})

        # Load file contents for top relevant files
        file_context = self._load_file_context(workspace, result.relevant_files[:5])

        # Memory context
        memories = self.retriever.retrieve(user_message)
        memory_context = self.retriever.format_for_prompt(memories)

        conventions = result.project_scan["conventions"]

        # Phase 3: Plan
        plan_prompt = self._plan_prompt(user_message, result.project_scan, result.relevant_files, file_context)
        result.plan = self.llm.generate(plan_prompt, system=self._planner_system(), mode=mode)
        result.phases.append({"phase": "plan", "status": "done"})

        # Phase 4: Execute (edits + commands)
        exec_system = self._executor_system(conventions, memory_context)
        exec_prompt = self._executor_prompt(user_message, result.plan, file_context)
        response, changes, commands = self._run_with_tools(
            exec_prompt, exec_system, mode, max_tool_rounds, workspace
        )
        result.files_changed = changes
        result.commands_run = commands
        result.phases.append({
            "phase": "execute",
            "status": "done",
            "files_changed": len(changes),
            "commands": len(commands),
        })

        # Phase 5: Auto-test if edits were made
        test_output = ""
        if auto_test and changes and conventions.get("test_commands"):
            test_cmd = conventions["test_commands"][0]
            from assistant.tools.shell import _run_command
            test_output = _run_command(test_cmd)
            result.commands_run.append(test_cmd)
            result.phases.append({"phase": "test", "status": "done", "command": test_cmd})

            if "exit_code=0" not in test_output and "error" in test_output.lower():
                fix_prompt = (
                    f"Tests failed:\n{test_output}\n\n"
                    f"Fix the errors. Read affected files first, use edit_file for surgical fixes.\n"
                    f"Original task: {user_message}"
                )
                fix_response, fix_changes, fix_cmds = self._run_with_tools(
                    fix_prompt, exec_system, mode, 5, workspace
                )
                response = fix_response
                result.files_changed.extend(fix_changes)
                result.commands_run.extend(fix_cmds)
                result.phases.append({"phase": "debug", "status": "done"})

        # Phase 6: Summary
        summary_prompt = (
            f"Summarize what you changed for the user. Be specific about files and why.\n\n"
            f"Task: {user_message}\n"
            f"Plan: {result.plan}\n"
            f"Files changed: {json.dumps(result.files_changed)}\n"
            f"Commands run: {result.commands_run}\n"
            f"Last response: {response}\n"
            f"Test output: {test_output[:1000]}"
        )
        result.response = self.llm.generate(summary_prompt, system=self._summary_system(), mode=mode)
        result.phases.append({"phase": "summary", "status": "done"})

        set_workspace(None)
        return result

    def _load_file_context(self, workspace: ProjectWorkspace, files: list[dict]) -> str:
        parts = []
        for f in files:
            content = workspace.read_file(f["path"], max_chars=3000)
            parts.append(f"### {f['path']}\n{content}")
        return "\n\n".join(parts) if parts else "(no files loaded)"

    def _planner_system(self) -> str:
        return (
            "You are a senior engineer planning changes to an existing project.\n"
            "The directory is the source of truth — never assume files that aren't shown.\n"
            "Output a concise numbered plan. Do NOT write code yet.\n"
            "Preserve existing conventions, naming, and architecture.\n"
            "Prefer edit_file over write_file for modifications."
        )

    def _executor_system(self, conventions: dict, memory_context: str) -> str:
        parts = [
            "You are a build partner executing a plan on a real project.",
            "RULES:",
            "- The project directory is the source of truth, not this chat.",
            "- Read files before editing. Use edit_file for small changes, write_file only for new files.",
            "- Match existing code style, imports, naming, and patterns.",
            "- Never rewrite entire files when a surgical edit suffices.",
            "- After edits, run tests/build if appropriate using run_command.",
            "- If a command fails, read the error output and fix the code.",
            f"- Detected stack: {conventions.get('primary')}. "
            f"Test commands: {conventions.get('test_commands')}. "
            f"Build commands: {conventions.get('build_commands')}.",
            self.tools.describe_for_prompt(),
            "To use a tool, respond with exactly: TOOL:tool_name {\"arg\": \"value\"}",
        ]
        if memory_context:
            parts.append(memory_context)
        return "\n\n".join(parts)

    def _summary_system(self) -> str:
        return (
            "Summarize changes clearly for the user.\n"
            "List: what changed, which files, why, and any test results.\n"
            "Be concise and actionable."
        )

    def _plan_prompt(self, task, scan, relevant, file_context) -> str:
        tree_preview = "\n".join(scan["tree"][:30])
        relevant_list = "\n".join(f"- {f['path']} ({f['reason']})" for f in relevant)
        return (
            f"Task: {task}\n\n"
            f"Project: {scan['root']} ({scan['file_count']} files)\n"
            f"Stack: {scan['conventions']['primary']}\n\n"
            f"Directory (sample):\n{tree_preview}\n\n"
            f"Relevant files:\n{relevant_list}\n\n"
            f"File contents:\n{file_context}\n\n"
            f"Create a numbered plan. Identify which files to read, edit, create, or delete."
        )

    def _executor_prompt(self, task, plan, file_context) -> str:
        return (
            f"Execute this plan on the project.\n\n"
            f"Task: {task}\n\n"
            f"Plan:\n{plan}\n\n"
            f"Known file contents:\n{file_context}\n\n"
            f"Start by reading any files you need, then make changes."
        )

    def _run_with_tools(self, prompt, system, mode, max_rounds, workspace):
        changes = []
        commands = []
        current_prompt = prompt
        response = ""

        for _ in range(max_rounds):
            response = self.llm.generate(current_prompt, system=system, mode=mode)
            match = TOOL_PATTERN.search(response)
            if not match:
                break

            tool_name, args_str = match.group(1), match.group(2)
            tool_result = self.tools.run(tool_name, args_str)
            commands.append(tool_name) if tool_name == "run_command" else None

            if tool_name in ("write_file", "edit_file", "delete_file"):
                changes.append({"tool": tool_name, "result": tool_result})

            current_prompt = (
                f"Tool '{tool_name}' returned:\n{tool_result}\n\n"
                f"Continue executing the plan. Use more tools if needed, or give a brief status update."
            )

        return response, changes, [c for c in commands if c]