from __future__ import annotations

import re
from pathlib import Path

from assistant.workspace.manager import CODE_EXTENSIONS, SKIP_DIRS, ProjectWorkspace

# Map user intent keywords to likely file patterns
INTENT_PATTERNS = {
    "test": ["test", "spec", "pytest", "unittest", "jest"],
    "config": ["config", "settings", "env", ".yaml", ".toml", ".json"],
    "api": ["api", "route", "endpoint", "controller", "handler"],
    "ui": ["component", "page", "template", "view", "css", "html"],
    "db": ["model", "schema", "migration", "database", "sql"],
    "auth": ["auth", "login", "session", "token", "password"],
    "build": ["build", "webpack", "vite", "gradle", "cargo", "makefile"],
}


class RelevantFileFinder:
    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace

    def find(self, query: str, limit: int = 10) -> list[dict]:
        query_lower = query.lower()
        tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", query_lower))

        # Expand tokens from intent patterns
        for _intent, keywords in INTENT_PATTERNS.items():
            if any(k in query_lower for k in keywords):
                tokens.update(keywords)

        scored: list[tuple[float, str, str]] = []

        for dirpath, dirnames, filenames in self.workspace.root.walk():
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.startswith("."):
                    continue
                rel = dirpath.relative_to(self.workspace.root) / name
                rel_str = str(rel).replace("\\", "/")
                score = self._score_file(rel_str, name, tokens, query_lower)
                if score > 0:
                    reason = self._reason(rel_str, tokens)
                    scored.append((score, rel_str, reason))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, path, reason in scored[:limit]:
            preview = ""
            try:
                full = self.workspace.read_file(path, max_chars=400)
                preview = full[:300]
            except Exception:
                pass
            results.append({
                "path": path,
                "score": round(score, 2),
                "reason": reason,
                "preview": preview,
            })
        return results

    def _score_file(self, rel: str, name: str, tokens: set, query: str) -> float:
        rel_lower = rel.lower()
        name_lower = name.lower()
        score = 0.0

        ext = Path(name).suffix.lower()
        if ext not in CODE_EXTENSIONS:
            return 0.0

        for token in tokens:
            if token in name_lower:
                score += 3.0
            if token in rel_lower:
                score += 1.5

        # Boost entry points and manifests
        if name_lower in ("main.py", "app.py", "index.js", "index.ts", "main.go", "mod.rs"):
            score += 2.0
        if name_lower in ("package.json", "pyproject.toml", "requirements.txt", "cargo.toml"):
            score += 1.5

        # Content grep for high-value hits
        try:
            path = self.workspace.resolve(rel)
            if path.stat().st_size > 200_000:
                return score
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for token in tokens:
                if token in text:
                    score += 0.5
        except Exception:
            pass

        return score

    def _reason(self, path: str, tokens: set) -> str:
        name = Path(path).name.lower()
        matched = [t for t in tokens if t in path.lower()]
        if matched:
            return f"matches: {', '.join(matched[:4])}"
        return f"file: {name}"