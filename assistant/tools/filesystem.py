from assistant.config import settings
from assistant.tools.registry import Tool, ToolRegistry
from assistant.workspace.context import get_workspace
from assistant.workspace.manager import ProjectWorkspace


def _ws() -> ProjectWorkspace:
    ws = get_workspace()
    return ws if ws else ProjectWorkspace(settings.workspace_dir)


def _read_file(path: str) -> str:
    ws = _ws()
    return ws.read_file(path)


def _write_file(path: str, content: str) -> str:
    ws = _ws()
    result = ws.write_file(path, content)
    return str(result)


def _edit_file(path: str, old_text: str, new_text: str) -> str:
    ws = _ws()
    result = ws.edit_file(path, old_text, new_text)
    return str(result)


def _delete_file(path: str) -> str:
    ws = _ws()
    result = ws.delete_file(path)
    return str(result)


def _list_dir(path: str = ".") -> str:
    ws = _ws()
    return ws.list_dir(path)


def _scan_project() -> str:
    ws = _ws()
    scan = ws.scan()
    lines = [
        f"Root: {scan['root']}",
        f"Files: {scan['file_count']}",
        f"Stack: {scan['conventions']['primary']}",
        f"Test commands: {scan['conventions']['test_commands']}",
        f"Build commands: {scan['conventions']['build_commands']}",
        "Tree (first 50):",
    ]
    lines.extend(scan["tree"][:50])
    return "\n".join(lines)


def _find_relevant_files(query: str, limit: int = 8) -> str:
    from assistant.workspace.retrieval import RelevantFileFinder
    hits = RelevantFileFinder(_ws()).find(query, limit=limit)
    if not hits:
        return "No relevant files found."
    lines = []
    for h in hits:
        lines.append(f"- {h['path']} (score={h['score']}, {h['reason']})")
        if h["preview"]:
            lines.append(f"  preview: {h['preview'][:150]}...")
    return "\n".join(lines)


def register_filesystem_tools(registry: ToolRegistry) -> None:
    registry.register(Tool(
        name="read_file",
        description="Read a file from the active project (source of truth)",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        handler=_read_file,
    ))
    registry.register(Tool(
        name="write_file",
        description="Create or overwrite a file. Prefer edit_file for small changes.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        handler=_write_file,
    ))
    registry.register(Tool(
        name="edit_file",
        description="Surgical edit: replace exact old_text with new_text in a file. Preserves the rest.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
        handler=_edit_file,
    ))
    registry.register(Tool(
        name="delete_file",
        description="Delete a single file (not directories)",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        handler=_delete_file,
    ))
    registry.register(Tool(
        name="list_dir",
        description="List files in a project directory",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        handler=_list_dir,
    ))
    registry.register(Tool(
        name="scan_project",
        description="Scan project structure, stack, and available test/build commands",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _scan_project(),
    ))
    registry.register(Tool(
        name="find_relevant_files",
        description="Find files relevant to the current task based on names and content",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["query"],
        },
        handler=_find_relevant_files,
    ))