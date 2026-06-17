from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from assistant.db.database import get_session
from assistant.db.models import Memory
from assistant.embeddings.store import delete_memory_index, index_memory, search_memories
from assistant.memory.categories import MemoryCategory
from assistant.memory.rules import classify_content_heuristic, should_promote_to_permanent


class MemoryStore:
    def create(
        self,
        content: str,
        category: MemoryCategory | str | None = None,
        title: str = "",
        source: str = "manual",
        source_ref: str = "",
        confidence: float = 1.0,
        summary: str = "",
    ) -> Memory:
        if category is None:
            category = classify_content_heuristic(content)
        if isinstance(category, MemoryCategory):
            category = category.value

        with get_session() as session:
            mem = Memory(
                category=category,
                title=title or content[:80],
                content=content,
                summary=summary,
                source=source,
                source_ref=source_ref,
                confidence=confidence,
            )
            session.add(mem)
            session.flush()
            memory_id = mem.id
            data = {
                "id": mem.id,
                "category": mem.category,
                "title": mem.title,
                "content": mem.content,
                "summary": mem.summary,
                "source": mem.source,
                "confidence": mem.confidence,
            }

        index_memory(memory_id, content, category, title, source)
        return data  # type: ignore[return-value]

    def get(self, memory_id: str) -> dict | None:
        with get_session() as session:
            mem = session.get(Memory, memory_id)
            if not mem:
                return None
            mem.access_count += 1
            return self._to_dict(mem)

    def list_all(self, category: str | None = None, active_only: bool = True) -> list[dict]:
        with get_session() as session:
            q = select(Memory)
            if category:
                q = q.where(Memory.category == category)
            if active_only:
                q = q.where(Memory.is_active == 1)
            q = q.order_by(Memory.updated_at.desc())
            return [self._to_dict(m) for m in session.scalars(q).all()]

    def update(self, memory_id: str, **fields) -> dict | None:
        with get_session() as session:
            mem = session.get(Memory, memory_id)
            if not mem:
                return None
            for key, val in fields.items():
                if hasattr(mem, key) and val is not None:
                    setattr(mem, key, val)
            session.flush()
            data = self._to_dict(mem)

        if "content" in fields:
            index_memory(mem.id, mem.content, mem.category, mem.title, mem.source)
        return data

    def delete(self, memory_id: str) -> bool:
        with get_session() as session:
            mem = session.get(Memory, memory_id)
            if not mem:
                return False
            mem.is_active = 0
        delete_memory_index(memory_id)
        return True

    def search(self, query: str, limit: int = 8, categories: list[str] | None = None) -> list[dict]:
        hits = search_memories(query, limit=limit, categories=categories)
        results = []
        for hit in hits:
            mem = self.get(hit["memory_id"])
            if mem:
                mem["relevance_score"] = hit["score"]
                results.append(mem)
        return results

    def promote_from_session(self, content: str, confidence: float = 0.7) -> dict | None:
        category = classify_content_heuristic(content)
        if should_promote_to_permanent(content, category, confidence, "session"):
            return self.create(content, category=category, source="session_promoted", confidence=confidence)
        return None

    def migrate_legacy_json(self, path: Path) -> int:
        if not path.exists():
            return 0
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for key, val in data.items():
            self.create(str(val), title=key, category=MemoryCategory.USER_PROFILE, source="legacy_json")
            count += 1
        return count

    @staticmethod
    def _to_dict(mem: Memory) -> dict:
        return {
            "id": mem.id,
            "category": mem.category,
            "title": mem.title,
            "content": mem.content,
            "summary": mem.summary,
            "source": mem.source,
            "source_ref": mem.source_ref,
            "confidence": mem.confidence,
            "access_count": mem.access_count,
            "is_active": mem.is_active,
            "created_at": mem.created_at.isoformat() if mem.created_at else None,
            "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
        }