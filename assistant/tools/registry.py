from __future__ import annotations

import json
from typing import Any, Callable


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., str],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self, **kwargs) -> str:
        return self.handler(**kwargs)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]

    def run(self, name: str, arguments: dict | str) -> str:
        if name not in self._tools:
            return f"Unknown tool: {name}"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"input": arguments}
        try:
            return self._tools[name].run(**arguments)
        except Exception as e:
            return f"Tool error ({name}): {e}"

    def describe_for_prompt(self) -> str:
        lines = ["Available tools (respond with TOOL:<name> <json_args> to use):"]
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)