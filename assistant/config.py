import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _root_dir() -> Path:
    """Project root. Exe in dist/ -> parent folder; else exe folder."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "dist":
            return exe_dir.parent
        # Also check if models/ exists here; if not, try parent
        if not (exe_dir / "models").exists() and (exe_dir.parent / "models").exists():
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _root_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="ASSISTANT_",
        extra="ignore",
    )

    llm_provider: str = "local"
    llm_model: str = "models/mistral-7b-instruct-v0.1.Q6_K.gguf"
    llm_api_key: str = ""
    llm_base_url: str = ""
    nsfw_api_url: str = "http://localhost:5000/v1/chat/completions"
    embedding_model: str = "all-MiniLM-L6-v2"
    host: str = "127.0.0.1"
    port: int = 8420
    data_dir: Path = ROOT_DIR / "data"
    workspace_dir: Path = ROOT_DIR / "workspace" / "projects"
    legacy_memory_path: Path = ROOT_DIR / "memory" / "memory.json"
    invokeai_api_url: str = "http://192.168.40.236:9090"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "memory" / "assistant.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def imports_path(self) -> Path:
        return self.data_dir / "imports"

    @property
    def llm_model_path(self) -> Path:
        p = Path(self.llm_model)
        return p if p.is_absolute() else ROOT_DIR / p


settings = Settings()


def validate_installation() -> list[str]:
    """Return list of fatal issues (empty = OK)."""
    issues = []
    if not settings.llm_model_path.exists():
        issues.append(f"LLM model not found: {settings.llm_model_path}")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return issues