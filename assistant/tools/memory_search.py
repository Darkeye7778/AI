from assistant.memory.store import MemoryStore
from assistant.tools.registry import Tool, ToolRegistry


def register_memory_tools(registry: ToolRegistry, store: MemoryStore) -> None:
    def search_memories(query: str, limit: int = 5) -> str:
        hits = store.search(query, limit=limit)
        if not hits:
            return "No relevant memories found."
        lines = []
        for h in hits:
            score = h.get("relevance_score", 0)
            lines.append(f"[{h['category']}] {h['title']} (score={score:.2f}): {h['content'][:300]}")
        return "\n".join(lines)

    def save_memory(content: str, title: str = "", category: str = "") -> str:
        kwargs = {"content": content, "source": "explicit_user_save"}
        if title:
            kwargs["title"] = title
        if category:
            kwargs["category"] = category
        mem = store.create(**kwargs)
        return f"Saved memory: {mem['id']} — {mem['title']}"

    registry.register(Tool(
        name="search_memories",
        description="Search long-term memory semantically",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
        handler=search_memories,
    ))
    registry.register(Tool(
        name="save_memory",
        description="Save something to permanent memory",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "title": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["content"],
        },
        handler=save_memory,
    ))