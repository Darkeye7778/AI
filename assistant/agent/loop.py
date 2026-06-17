from __future__ import annotations

import json
import re

from assistant.agent.build_loop import BuildLoop
from assistant.chat.manager import ChatManager
from assistant.db.database import get_session
from assistant.db.models import ChatMessage, ChatSession
from assistant.llm.router import LLMRouter
from assistant.memory.retrieval import ContextRetriever
from assistant.memory.store import MemoryStore
from assistant.tools.filesystem import register_filesystem_tools
from assistant.tools.memory_search import register_memory_tools
from assistant.tools.registry import ToolRegistry
from assistant.tools.shell import register_shell_tools
from assistant.workspace.context import set_workspace
from assistant.workspace.manager import ProjectWorkspace

TOOL_PATTERN = re.compile(r"TOOL:(\w+)\s*(\{.*\})", re.DOTALL)


class AgentLoop:
    def __init__(self):
        self.llm = LLMRouter()
        self.memory = MemoryStore()
        self.retriever = ContextRetriever(self.memory)
        self.tools = ToolRegistry()
        self.build = BuildLoop()
        self.chats = ChatManager(self.llm)
        register_filesystem_tools(self.tools)
        register_memory_tools(self.tools, self.memory)
        register_shell_tools(self.tools)

    def chat(
        self,
        user_message: str,
        session_id: str | None = None,
        mode: str = "safe",
        max_tool_rounds: int = 3,
        build_mode: bool = False,
        project_path: str = "",
    ) -> dict:
        # Build mode: full pipeline treating the directory as source of truth
        if build_mode and project_path:
            return self._chat_build(user_message, project_path, session_id, mode)

        # Standard chat (optionally with workspace tools if project is set)
        workspace = None
        if project_path:
            try:
                workspace = ProjectWorkspace(project_path)
                set_workspace(workspace)
            except (FileNotFoundError, NotADirectoryError) as e:
                set_workspace(None)
                return {"error": str(e), "response": f"Cannot access project: {e}"}

        try:
            return self._chat_standard(
                user_message, session_id, mode, max_tool_rounds, project_path=project_path
            )
        finally:
            set_workspace(None)

    def _chat_build(self, user_message, project_path, session_id, mode) -> dict:
        with get_session() as session:
            if not session_id:
                chat_session = ChatSession(title=user_message[:60])
                session.add(chat_session)
                session.flush()
                session_id = chat_session.id
            session.add(ChatMessage(session_id=session_id, role="user", content=user_message))

        try:
            result = self.build.run(user_message, project_path, mode=mode)
        except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
            return {"session_id": session_id, "error": str(e), "response": str(e)}

        with get_session() as session:
            session.add(ChatMessage(
                session_id=session_id,
                role="assistant",
                content=result.response,
                memories_used="[]",
            ))

        meta = self.chats.after_message(
            session_id, user_message, build_mode=True, build_path=project_path
        )

        return {
            "session_id": session_id,
            "response": result.response,
            "meta": meta,
            "build_mode": True,
            "plan": result.plan,
            "phases": result.phases,
            "files_changed": result.files_changed,
            "commands_run": result.commands_run,
            "relevant_files": result.relevant_files,
            "project_root": result.project_scan.get("root", project_path),
        }

    def _chat_standard(
        self, user_message, session_id, mode, max_tool_rounds, project_path: str = ""
    ) -> dict:
        with get_session() as session:
            if not session_id:
                chat_session = ChatSession(title=user_message[:60])
                session.add(chat_session)
                session.flush()
                session_id = chat_session.id
            session.add(ChatMessage(session_id=session_id, role="user", content=user_message))

        memories = self.retriever.retrieve(user_message)
        memory_context = self.retriever.format_for_prompt(memories)
        memory_ids = [m["id"] for m in memories]

        system = self._build_system_prompt(memory_context)
        response = self._run_with_tools(user_message, system, mode, max_tool_rounds)

        with get_session() as session:
            session.add(ChatMessage(
                session_id=session_id,
                role="assistant",
                content=response,
                memories_used=json.dumps(memory_ids),
            ))

        if any(w in user_message.lower() for w in ["remember", "my preference", "i always", "i prefer"]):
            self.memory.promote_from_session(user_message, confidence=0.8)

        meta = self.chats.after_message(
            session_id, user_message, build_path=project_path if project_path else ""
        )

        return {
            "session_id": session_id,
            "response": response,
            "memories_used": memories,
            "meta": meta,
        }

    def _build_system_prompt(self, memory_context: str) -> str:
        parts = [
            "You are a personal AI assistant running locally on the user's PC.",
            "Your primary role is conversational — like ChatGPT for ideas, thinking, planning, "
            "brainstorming, life context, and working through problems out loud.",
            "Be natural, helpful, and thoughtful. You are their brain buffer.",
            "When you have relevant memories, weave them in naturally — don't list them mechanically.",
            "Only use tools if the user explicitly asks you to save a memory, search memories, "
            "or work with files. For normal conversation, just talk.",
            "To use a tool, respond with exactly: TOOL:tool_name {\"arg\": \"value\"}",
            self.tools.describe_for_prompt(),
        ]
        if memory_context:
            parts.append(memory_context)
        return "\n\n".join(parts)

    def _run_with_tools(self, prompt: str, system: str, mode: str, max_rounds: int) -> str:
        current_prompt = prompt
        response = ""
        for _ in range(max(1, max_rounds)):
            response = self.llm.generate(current_prompt, system=system, mode=mode)
            match = TOOL_PATTERN.search(response)
            if not match:
                return response

            tool_name, args_str = match.group(1), match.group(2)
            tool_result = self.tools.run(tool_name, args_str)
            current_prompt = (
                f"Tool '{tool_name}' returned:\n{tool_result}\n\n"
                f"Continue helping with the original request: {prompt}"
            )

        return response