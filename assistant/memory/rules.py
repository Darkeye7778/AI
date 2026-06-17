from datetime import timedelta

from assistant.memory.categories import (
    EPHEMERAL_CATEGORIES,
    PERMANENT_CATEGORIES,
    MemoryCategory,
)


def should_promote_to_permanent(
    content: str,
    category: MemoryCategory,
    confidence: float,
    source: str,
) -> bool:
    if category in EPHEMERAL_CATEGORIES:
        return False
    if source == "explicit_user_save":
        return True
    if category in PERMANENT_CATEGORIES and confidence >= 0.6:
        return True

    signals = [
        "prefer", "always", "never", "my name", "i work", "i live",
        "project", "goal", "plan", "budget", "deadline", "stack",
        "framework", "architecture", "decision", "constraint",
    ]
    hits = sum(1 for s in signals if s in content.lower())
    return hits >= 2 and confidence >= 0.5


def session_context_ttl() -> timedelta:
    return timedelta(hours=24)


def classify_content_heuristic(text: str) -> MemoryCategory:
    lower = text.lower()
    if any(w in lower for w in ["prefer", "i like", "my style", "always use"]):
        return MemoryCategory.USER_PROFILE
    if any(w in lower for w in ["salary", "budget", "finance", "car", "job"]):
        return MemoryCategory.FINANCIAL_CONTEXT
    if any(w in lower for w in ["business", "revenue", "market", "startup"]):
        return MemoryCategory.BUSINESS_PLANS
    if any(w in lower for w in ["react", "python", "api", "database", "code", "bug"]):
        return MemoryCategory.TECHNICAL_BUILDS
    if any(w in lower for w in ["project", "milestone", "roadmap", "sprint"]):
        return MemoryCategory.ACTIVE_PROJECTS
    if any(w in lower for w in ["note", "reminder", "idea", "journal"]):
        return MemoryCategory.PERSONAL_NOTES
    return MemoryCategory.ARCHIVED_HISTORY