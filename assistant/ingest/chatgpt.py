from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from assistant.chat.manager import ChatManager
from assistant.db.database import get_session
from assistant.db.models import ConversationMessage, ParsedConversation, RawImport
from assistant.memory.rules import classify_content_heuristic
from assistant.memory.store import MemoryStore


def _parse_timestamp(ts: float | int | None) -> datetime | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts))
    except (ValueError, OSError, TypeError):
        return None


def _extract_messages(mapping: dict, current_id: str) -> list[dict]:
    """Walk ChatGPT conversation tree and extract messages in order."""
    messages = []
    node = mapping.get(current_id)
    if not node:
        return messages

    msg = node.get("message")
    if msg and msg.get("content"):
        parts = msg["content"].get("parts", [])
        text = "\n".join(p for p in parts if isinstance(p, str))
        if text.strip():
            messages.append({
                "role": msg.get("author", {}).get("role", "unknown"),
                "content": text.strip(),
                "timestamp": _parse_timestamp(msg.get("create_time")),
            })

    for child_id in node.get("children", []):
        messages.extend(_extract_messages(mapping, child_id))

    return messages


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], []
    length = 0
    for paragraph in text.split("\n"):
        if length + len(paragraph) > max_chars and current:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(paragraph)
        length += len(paragraph)
    if current:
        chunks.append("\n".join(current))
    return chunks


class ChatGPTImporter:
    def __init__(self, memory_store: MemoryStore | None = None, chat_manager: ChatManager | None = None):
        self.memory = memory_store or MemoryStore()
        self.chats = chat_manager or ChatManager()

    def import_file(self, filepath: Path) -> dict:
        filepath = Path(filepath)
        if filepath.suffix == ".zip":
            return self._import_zip(filepath)
        if filepath.suffix == ".json":
            return self._import_json(filepath)
        raise ValueError(f"Unsupported file type: {filepath.suffix}")

    def _import_zip(self, zip_path: Path) -> dict:
        with zipfile.ZipFile(zip_path) as zf:
            json_files = [n for n in zf.namelist() if n.endswith("conversations.json")]
            if not json_files:
                raise ValueError("No conversations.json found in zip")
            with zf.open(json_files[0]) as f:
                conversations = json.load(f)
        return self._process_conversations(conversations, source_name=zip_path.name)

    def _import_json(self, json_path: Path) -> dict:
        with open(json_path, encoding="utf-8") as f:
            conversations = json.load(f)
        return self._process_conversations(conversations, source_name=json_path.name)

    def _process_conversations(self, conversations: list, source_name: str) -> dict:
        with get_session() as session:
            raw = RawImport(
                source="chatgpt",
                filename=source_name,
                status="processing",
                conversation_count=len(conversations),
            )
            session.add(raw)
            session.flush()
            import_id = raw.id

        parsed_count = 0
        memory_count = 0
        chats_imported = 0
        chats_skipped = 0
        projects_touched: set[str] = set()

        for conv in conversations:
            conv_id = conv.get("id", conv.get("conversation_id", ""))
            title = conv.get("title", "Untitled")
            mapping = conv.get("mapping", {})
            root_id = next((k for k, v in mapping.items() if v.get("parent") is None), None)
            if not root_id:
                continue

            messages = _extract_messages(mapping, root_id)
            if not messages:
                continue

            with get_session() as session:
                parsed = ParsedConversation(
                    import_id=import_id,
                    external_id=conv_id,
                    title=title,
                    message_count=len(messages),
                    created_at=messages[0].get("timestamp") if messages else None,
                )
                session.add(parsed)
                session.flush()
                conversation_db_id = parsed.id

                for i, msg in enumerate(messages):
                    for chunk_idx, chunk in enumerate(_chunk_text(msg["content"])):
                        session.add(ConversationMessage(
                            conversation_id=conversation_db_id,
                            role=msg["role"],
                            content=chunk,
                            timestamp=msg.get("timestamp"),
                            chunk_index=chunk_idx,
                        ))

            parsed_count += 1

            import_result = self.chats.import_conversation(
                title=title,
                messages=messages,
                external_id=conv_id,
                source="chatgpt",
                created_at=messages[0].get("timestamp") if messages else None,
            )
            if import_result.get("skipped"):
                chats_skipped += 1
            else:
                chats_imported += 1
                if import_result.get("project_name"):
                    projects_touched.add(import_result["project_name"])

            # Extract memories from user messages (preferences, projects, etc.)
            for msg in messages:
                if msg["role"] != "user" or len(msg["content"]) < 30:
                    continue
                category = classify_content_heuristic(msg["content"])
                if category.value not in ("archived_history", "session_context"):
                    self.memory.create(
                        content=msg["content"][:2000],
                        category=category,
                        title=title[:200],
                        source="chatgpt_import",
                        source_ref=conv_id,
                        confidence=0.65,
                    )
                    memory_count += 1

        with get_session() as session:
            raw = session.get(RawImport, import_id)
            if raw:
                raw.status = "completed"

        return {
            "import_id": import_id,
            "conversations_parsed": parsed_count,
            "memories_extracted": memory_count,
            "chats_imported": chats_imported,
            "chats_skipped": chats_skipped,
            "projects_organized": len(projects_touched),
            "source": source_name,
        }