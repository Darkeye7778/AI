from __future__ import annotations

import os
from pathlib import Path

from assistant.workspace.conventions import detect_stack

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", "dist", "build", ".next", "outputs",
    "models", "databases", ".gradle", ".android",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".md", ".html", ".css", ".scss", ".sql", ".sh", ".bat",
    ".rs", ".go", ".java", ".kt", ".cs", ".cpp", ".h", ".c",
}


class ProjectWorkspace:
    """Treats a directory as source of truth for build mode."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Project path does not exist: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.root}")

    def resolve(self, rel_path: str) -> Path:
        """Resolve a path and ensure it stays inside the project root."""
        target = (self.root / rel_path).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            raise PermissionError(f"Path escapes project root: {rel_path}")
        return target

    def scan(self, max_depth: int = 4) -> dict:
        tree = []
        file_count = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            depth = Path(dirpath).relative_to(self.root).parts
            if len(depth) > max_depth:
                dirnames.clear()
                continue
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            rel = Path(dirpath).relative_to(self.root)
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                file_count += 1
                tree.append(str(rel / name) if str(rel) != "." else name)

        conventions = detect_stack(self.root)
        return {
            "root": str(self.root),
            "file_count": file_count,
            "tree": tree[:200],
            "conventions": conventions,
        }

    def read_file(self, rel_path: str, max_chars: int = 12000) -> str:
        path = self.resolve(rel_path)
        if not path.exists():
            return f"File not found: {rel_path}"
        if path.is_dir():
            return f"Path is a directory: {rel_path}"
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def write_file(self, rel_path: str, content: str) -> dict:
        path = self.resolve(rel_path)
        existed = path.exists()
        old_content = path.read_text(encoding="utf-8") if existed else ""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "path": rel_path,
            "action": "modified" if existed else "created",
            "chars": len(content),
            "lines_before": old_content.count("\n") + (1 if old_content else 0),
            "lines_after": content.count("\n") + (1 if content else 0),
        }

    def edit_file(self, rel_path: str, old_text: str, new_text: str) -> dict:
        """Surgical edit — preserves everything outside the matched block."""
        path = self.resolve(rel_path)
        if not path.exists():
            return {"error": f"File not found: {rel_path}"}
        content = path.read_text(encoding="utf-8")
        if old_text not in content:
            return {"error": f"Could not find exact match in {rel_path}. Read the file first."}
        updated = content.replace(old_text, new_text, 1)
        path.write_text(updated, encoding="utf-8")
        return {"path": rel_path, "action": "edited", "replaced_chars": len(old_text)}

    def delete_file(self, rel_path: str) -> dict:
        path = self.resolve(rel_path)
        if not path.exists():
            return {"error": f"File not found: {rel_path}"}
        if path.is_dir():
            return {"error": f"Refusing to delete directory: {rel_path}"}
        path.unlink()
        return {"path": rel_path, "action": "deleted"}

    def list_dir(self, rel_path: str = ".") -> str:
        path = self.resolve(rel_path)
        if not path.exists():
            return f"Directory not found: {rel_path}"
        lines = []
        for entry in sorted(path.iterdir()):
            if entry.name in SKIP_DIRS:
                continue
            tag = "[dir]" if entry.is_dir() else "[file]"
            lines.append(f"{tag} {entry.name}")
        return "\n".join(lines) or "(empty)"