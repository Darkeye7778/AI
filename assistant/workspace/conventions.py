from __future__ import annotations

import json
from pathlib import Path


MANIFEST_FILES = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "Makefile": "make",
    "CMakeLists.txt": "cmake",
}

TEST_COMMANDS = {
    "node": ["npm test", "npm run test", "npx jest"],
    "python": ["python -m pytest", "python -m unittest discover"],
    "rust": ["cargo test"],
    "go": ["go test ./..."],
    "java": ["mvn test", "./gradlew test"],
    "make": ["make test"],
}

BUILD_COMMANDS = {
    "node": ["npm run build", "npm run dev"],
    "python": ["python -m build"],
    "rust": ["cargo build"],
    "go": ["go build ./..."],
    "java": ["mvn package", "./gradlew build"],
}


def detect_stack(root: Path) -> dict:
    stacks = []
    manifests = {}
    for name, stack in MANIFEST_FILES.items():
        path = root / name
        if path.exists():
            stacks.append(stack)
            manifests[name] = _read_manifest_summary(path)

    primary = stacks[0] if stacks else "unknown"
    return {
        "stacks": list(dict.fromkeys(stacks)),
        "primary": primary,
        "manifests": manifests,
        "test_commands": TEST_COMMANDS.get(primary, []),
        "build_commands": BUILD_COMMANDS.get(primary, []),
    }


def _read_manifest_summary(path: Path) -> dict:
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            deps = list(data.get("dependencies", {}).keys())[:15]
            return {"scripts": scripts, "dependencies": deps}
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"preview": text[:500]}
    except Exception as e:
        return {"error": str(e)}