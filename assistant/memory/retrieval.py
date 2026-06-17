from assistant.memory.categories import MemoryCategory
from assistant.memory.store import MemoryStore


class ContextRetriever:
    """Retrieve only relevant memories for a given prompt."""

    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def retrieve(
        self,
        prompt: str,
        max_memories: int = 6,
        include_session: bool = True,
    ) -> list[dict]:
        categories = [c.value for c in MemoryCategory if c != MemoryCategory.ARCHIVED_HISTORY]
        if not include_session:
            categories.remove(MemoryCategory.SESSION_CONTEXT.value)

        hits = self.store.search(prompt, limit=max_memories, categories=categories)

        # Boost user profile hits for preference-related queries
        pref_signals = ["prefer", "style", "always", "how do i", "what do i"]
        if any(s in prompt.lower() for s in pref_signals):
            profile = self.store.list_all(category=MemoryCategory.USER_PROFILE.value, active_only=True)
            for p in profile[:2]:
                if p["id"] not in {h["id"] for h in hits}:
                    hits.append(p)

        return hits[:max_memories]

    def format_for_prompt(self, memories: list[dict]) -> str:
        if not memories:
            return ""
        lines = ["## Relevant memories (cite when used):"]
        for m in memories:
            score = m.get("relevance_score")
            score_str = f" (relevance: {score:.2f})" if score else ""
            lines.append(f"- [{m['category']}] {m['title']}{score_str}: {m['content'][:500]}")
        return "\n".join(lines)