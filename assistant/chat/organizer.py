"""Auto-assign chats to projects and generate titles from context."""

from __future__ import annotations

import re
from pathlib import Path

from assistant.db.database import get_session
from assistant.db.models import ChatMessage, ChatSession
from sqlalchemy import select


DEFAULT_TITLES = {"new chat", "untitled", "untitled conversation"}
STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "to", "in", "on", "at", "of", "with",
    "how", "what", "why", "when", "where", "help", "need", "want", "please",
    "my", "me", "i", "is", "are", "was", "be", "can", "could", "would", "should",
    "about", "using", "make", "create", "fix", "build", "write", "question",
}
PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]+)")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def heuristic_title(first_message: str, max_len: int = 48) -> str:
    text = first_message.strip().replace("\n", " ")
    if len(text) <= max_len:
        return text or "New Chat"
    return text[: max_len - 1].rstrip() + "…"


def match_project(message: str, projects: list[dict], build_path: str = "") -> str | None:
    """Return project_id if message clearly belongs to a project folder."""
    lower = _normalize(message)
    if not lower:
        return None

    # Build mode path match
    if build_path:
        for p in projects:
            if p.get("path") and _normalize(p["path"]) in _normalize(build_path):
                return p["id"]

    best_id, best_score = None, 0.0
    for p in projects:
        score = 0.0
        name = _normalize(p.get("name", ""))
        if name and name in lower:
            score += 3.0
        path = p.get("path") or ""
        if path:
            folder = _normalize(Path(path).name)
            if folder and folder in lower:
                score += 2.0
        description = p.get("description") or ""
        if description:
            for word in _normalize(description).split():
                if len(word) > 4 and word in lower:
                    score += 0.5
        if score > best_score:
            best_score, best_id = score, p["id"]

    return best_id if best_score >= 2.0 else None


def should_refresh_title(session: ChatSession, message_count: int) -> bool:
    title = _normalize(session.title)
    if title in DEFAULT_TITLES or title == "":
        return True
    if message_count <= 2:
        return True
    # Refresh after more context every 6 messages
    return message_count > 0 and message_count % 6 == 0


def llm_title(llm, messages: list[tuple[str, str]]) -> str:
    """Generate a short chat title from recent messages."""
    transcript = "\n".join(f"{role}: {content[:300]}" for role, content in messages[-6:])
    prompt = (
        "Write a very short chat title (3-6 words) summarizing this conversation.\n"
        "Reply with ONLY the title, no quotes or punctuation at the end.\n\n"
        f"{transcript}"
    )
    title = llm.generate(prompt, system="You name chat conversations concisely.", max_tokens=24)
    title = title.strip().strip('"').strip("'").split("\n")[0][:60]
    return title or heuristic_title(messages[0][1] if messages else "New Chat")


def build_import_context(title: str, messages: list[dict], max_msgs: int = 5) -> str:
    parts = [title]
    for msg in messages:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            parts.append(msg["content"][:500])
        if len(parts) >= max_msgs + 1:
            break
    return " ".join(parts)


def extract_paths(text: str) -> list[str]:
    return [m.group(0).rstrip(".,;:") for m in PATH_PATTERN.finditer(text)]


def infer_project_name(title: str, messages: list[dict]) -> str | None:
    """Guess a project folder name from an imported conversation."""
    title = title.strip()
    lower = _normalize(title)
    if lower in DEFAULT_TITLES or len(lower) < 3:
        title = ""

    if title and ":" in title:
        prefix = title.split(":", 1)[0].strip()
        if len(prefix) >= 3 and _normalize(prefix) not in DEFAULT_TITLES:
            return prefix[:80]

    if title:
        words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", title)
                 if _normalize(w) not in STOPWORDS]
        if len(words) >= 2:
            return " ".join(words[:3])[:80]
        if len(words) == 1 and len(words[0]) >= 4:
            return words[0][:80]

    context = build_import_context(title or "chat", messages, max_msgs=3).lower()
    if any(w in context for w in ["python", "react", "api", "database", "code", "bug", "deploy"]):
        return "Technical Builds"
    if any(w in context for w in ["business", "startup", "revenue", "market", "client"]):
        return "Business"
    if any(w in context for w in ["budget", "finance", "salary", "invest", "tax"]):
        return "Finance"
    return None


def assign_imported_conversation(
    title: str,
    messages: list[dict],
    projects: list[dict],
    create_project_fn,
    ensure_project_for_path_fn,
) -> tuple[str | None, str | None]:
    """Return (project_id, project_name) for an imported ChatGPT conversation."""
    context = build_import_context(title, messages)

    matched = match_project(context, projects)
    if matched:
        for p in projects:
            if p["id"] == matched:
                return matched, p["name"]

    for path in extract_paths(context):
        try:
            proj = ensure_project_for_path_fn(path)
            projects.append(proj)
            return proj["id"], proj["name"]
        except Exception:
            continue

    inferred = infer_project_name(title, messages)
    if inferred:
        proj = create_project_fn(
            inferred,
            description="Auto-created while importing ChatGPT history",
        )
        if not any(p["id"] == proj["id"] for p in projects):
            projects.append(proj)
        return proj["id"], proj["name"]

    return None, None


def get_recent_messages(session_id: str, limit: int = 10) -> list[tuple[str, str]]:
    with get_session() as session:
        rows = session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()
        return [(r.role, r.content) for r in reversed(list(rows))]