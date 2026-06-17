from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from assistant.config import settings
from assistant.db.models import Base


def _engine():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{settings.db_path}", echo=False)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _column_names(conn, table: str) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def _migrate() -> None:
    insp = inspect(engine)
    if "chat_sessions" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        cols = _column_names(conn, "chat_sessions")
        if "updated_at" not in cols:
            conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN updated_at DATETIME"))
            conn.execute(text(
                "UPDATE chat_sessions SET updated_at = created_at WHERE updated_at IS NULL"
            ))
            conn.execute(text(
                "UPDATE chat_sessions SET updated_at = datetime('now') WHERE updated_at IS NULL"
            ))
        cols = _column_names(conn, "chat_sessions")
        if "import_source" not in cols:
            conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN import_source VARCHAR(30)"))
        cols = _column_names(conn, "chat_sessions")
        if "external_id" not in cols:
            conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN external_id VARCHAR(100)"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate()


@contextmanager
def get_session():
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()