"""Chat sessions and project folders — ChatGPT-style organization."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from assistant.chat.organizer import (
    assign_imported_conversation,
    get_recent_messages,
    heuristic_title,
    llm_title,
    match_project,
    should_refresh_title,
)
from assistant.db.database import get_session
from assistant.db.models import ChatMessage, ChatSession, Project


class ChatManager:
    def __init__(self, llm=None):
        self.llm = llm

    def list_projects(self, active_only: bool = True) -> list[dict]:
        with get_session() as session:
            q = select(Project)
            if active_only:
                q = q.where(Project.status == "active")
            q = q.order_by(Project.name)
            return [self._project_dict(p) for p in session.scalars(q).all()]

    def list_sessions(self, project_id: str | None = None, limit: int = 100) -> list[dict]:
        with get_session() as session:
            q = select(ChatSession).order_by(ChatSession.updated_at.desc())
            if project_id == "":
                q = q.where(ChatSession.project_id.is_(None))
            elif project_id:
                q = q.where(ChatSession.project_id == project_id)
            q = q.limit(limit)
            return [self._session_dict(s) for s in session.scalars(q).all()]

    def grouped_sidebar(self) -> dict:
        projects = self.list_projects()
        uncategorized = self.list_sessions(project_id="")
        groups = []
        for p in projects:
            chats = self.list_sessions(project_id=p["id"])
            groups.append({"project": p, "chats": chats})
        return {"projects": groups, "uncategorized": uncategorized}

    def get_messages(self, session_id: str) -> list[dict]:
        with get_session() as session:
            rows = session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            ).all()
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in rows
            ]

    def create_project(self, name: str, path: str = "", description: str = "") -> dict:
        with get_session() as session:
            existing = session.scalars(select(Project).where(Project.name == name)).first()
            if existing:
                return self._project_dict(existing)
            p = Project(name=name, path=path, description=description)
            session.add(p)
            session.flush()
            return self._project_dict(p)

    def ensure_project_for_path(self, folder_path: str) -> dict:
        path = str(Path(folder_path).resolve())
        name = Path(path).name or "Project"
        with get_session() as session:
            existing = session.scalars(select(Project).where(Project.path == path)).first()
            if existing:
                return self._project_dict(existing)
            p = Project(name=name, path=path, description=f"Code workspace at {path}")
            session.add(p)
            session.flush()
            return self._project_dict(p)

    def assign_session_project(self, session_id: str, project_id: str | None) -> None:
        with get_session() as session:
            s = session.get(ChatSession, session_id)
            if s:
                s.project_id = project_id
                s.updated_at = datetime.utcnow()

    def rename_session(self, session_id: str, title: str) -> None:
        with get_session() as session:
            s = session.get(ChatSession, session_id)
            if s:
                s.title = title[:300]
                s.updated_at = datetime.utcnow()

    def touch_session(self, session_id: str) -> None:
        with get_session() as session:
            s = session.get(ChatSession, session_id)
            if s:
                s.updated_at = datetime.utcnow()

    def delete_session(self, session_id: str) -> None:
        with get_session() as session:
            for msg in session.scalars(
                select(ChatMessage).where(ChatMessage.session_id == session_id)
            ).all():
                session.delete(msg)
            s = session.get(ChatSession, session_id)
            if s:
                session.delete(s)

    def get_session(self, session_id: str) -> dict | None:
        with get_session() as session:
            s = session.get(ChatSession, session_id)
            return self._session_dict(s) if s else None

    def find_by_external_id(self, source: str, external_id: str) -> dict | None:
        if not external_id:
            return None
        with get_session() as session:
            s = session.scalars(
                select(ChatSession).where(
                    ChatSession.import_source == source,
                    ChatSession.external_id == external_id,
                )
            ).first()
            return self._session_dict(s) if s else None

    def import_conversation(
        self,
        title: str,
        messages: list[dict],
        external_id: str = "",
        source: str = "chatgpt",
        created_at: datetime | None = None,
        skip_duplicate: bool = True,
        auto_organize: bool = True,
    ) -> dict:
        """Create a sidebar chat from an imported conversation."""
        if skip_duplicate and external_id:
            existing = self.find_by_external_id(source, external_id)
            if existing:
                return {
                    "session_id": existing["id"],
                    "title": existing["title"],
                    "skipped": True,
                    "project_id": existing.get("project_id"),
                }

        clean_title = (title or "Untitled").strip()[:300]
        chat_messages = [
            m for m in messages
            if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
        ]
        if not chat_messages:
            return {"skipped": True, "reason": "no_messages"}

        project_id = None
        project_name = None
        if auto_organize:
            projects = self.list_projects()
            project_id, project_name = assign_imported_conversation(
                clean_title,
                chat_messages,
                projects,
                create_project_fn=self.create_project,
                ensure_project_for_path_fn=self.ensure_project_for_path,
            )

        now = datetime.utcnow()
        session_created = created_at or now
        session_updated = created_at or now

        with get_session() as session:
            chat = ChatSession(
                title=clean_title,
                project_id=project_id,
                import_source=source if external_id else None,
                external_id=external_id or None,
                created_at=session_created,
                updated_at=session_updated,
            )
            session.add(chat)
            session.flush()
            session_id = chat.id

            for msg in chat_messages:
                session.add(ChatMessage(
                    session_id=session_id,
                    role=msg["role"],
                    content=msg["content"].strip(),
                    created_at=msg.get("timestamp") or session_created,
                ))

        return {
            "session_id": session_id,
            "title": clean_title,
            "project_id": project_id,
            "project_name": project_name,
            "message_count": len(chat_messages),
            "skipped": False,
        }

    def after_message(
        self,
        session_id: str,
        user_message: str,
        build_mode: bool = False,
        build_path: str = "",
    ) -> dict:
        changes: dict = {}

        with get_session() as session:
            chat = session.get(ChatSession, session_id)
            if not chat:
                return changes
            current_project_id = chat.project_id
            current_title = chat.title
            msg_count = session.scalar(
                select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
            ) or 0
            projects = [
                self._project_dict(p)
                for p in session.scalars(select(Project).where(Project.status == "active")).all()
            ]

        # Auto-assign project
        new_project_id = current_project_id
        if build_mode and build_path:
            proj = self.ensure_project_for_path(build_path)
            new_project_id = proj["id"]
            if new_project_id != current_project_id:
                self.assign_session_project(session_id, new_project_id)
                changes["project_id"] = new_project_id
                changes["project_name"] = proj["name"]
        elif not current_project_id:
            matched = match_project(user_message, projects, build_path)
            if matched:
                new_project_id = matched
                self.assign_session_project(session_id, matched)
                changes["project_id"] = matched
                for p in projects:
                    if p["id"] == matched:
                        changes["project_name"] = p["name"]
                        break

        # Auto-rename (use a simple object for should_refresh_title)
        class _S:
            title = current_title

        if should_refresh_title(_S(), msg_count):
            msgs = get_recent_messages(session_id)
            if self.llm and len(msgs) >= 2:
                try:
                    new_title = llm_title(self.llm, msgs)
                except Exception:
                    new_title = heuristic_title(user_message)
            else:
                new_title = heuristic_title(user_message)
            if new_title and new_title != current_title:
                self.rename_session(session_id, new_title)
                changes["title"] = new_title

        self.touch_session(session_id)
        return changes

    @staticmethod
    def _project_dict(p: Project) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "path": p.path,
            "description": p.description,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    @staticmethod
    def _session_dict(s: ChatSession) -> dict:
        return {
            "id": s.id,
            "title": s.title,
            "project_id": s.project_id,
            "import_source": s.import_source,
            "external_id": s.external_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }