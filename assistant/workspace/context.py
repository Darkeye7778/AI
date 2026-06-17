from __future__ import annotations

from assistant.workspace.manager import ProjectWorkspace

_active: ProjectWorkspace | None = None


def set_workspace(workspace: ProjectWorkspace | None) -> None:
    global _active
    _active = workspace


def get_workspace() -> ProjectWorkspace | None:
    return _active


def require_workspace() -> ProjectWorkspace:
    if _active is None:
        raise RuntimeError("No active project workspace. Set a project path first.")
    return _active