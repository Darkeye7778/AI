from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from assistant.agent.loop import AgentLoop
from assistant.config import settings
from assistant.db.database import init_db
from assistant.ingest.chatgpt import ChatGPTImporter
from assistant.memory.categories import CATEGORY_LABELS, MemoryCategory
from assistant.memory.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = ROOT / "web"

app = FastAPI(title="Personal AI Assistant", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")

agent = AgentLoop()
memory_store = MemoryStore()
importer = ChatGPTImporter(memory_store)


@app.on_event("startup")
def startup():
    init_db()
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    migrated = memory_store.migrate_legacy_json(settings.legacy_memory_path)
    if migrated:
        print(f"Migrated {migrated} legacy memories from memory.json")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    return templates.TemplateResponse("memory.html", {
        "request": request,
        "categories": CATEGORY_LABELS,
    })


@app.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return templates.TemplateResponse("import.html", {"request": request})


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse("projects.html", {"request": request})


@app.post("/api/chat")
async def api_chat(
    message: str = Form(...),
    session_id: str = Form(""),
    mode: str = Form("safe"),
    build_mode: str = Form("false"),
    project_path: str = Form(""),
):
    result = agent.chat(
        message,
        session_id=session_id or None,
        mode=mode,
        build_mode=build_mode.lower() in ("true", "1", "yes"),
        project_path=project_path.strip(),
    )
    return result


@app.post("/api/project/scan")
async def api_scan_project(project_path: str = Form(...)):
    from assistant.workspace.manager import ProjectWorkspace
    from assistant.workspace.retrieval import RelevantFileFinder
    ws = ProjectWorkspace(project_path)
    return {
        "scan": ws.scan(),
        "sample_files": ws.scan()["tree"][:30],
    }


@app.get("/api/project/active")
async def api_active_project():
    active_file = settings.data_dir / "active_project.txt"
    if active_file.exists():
        return {"path": active_file.read_text(encoding="utf-8").strip()}
    return {"path": str(settings.workspace_dir)}


@app.post("/api/project/active")
async def api_set_active_project(project_path: str = Form(...)):
    from assistant.workspace.manager import ProjectWorkspace
    ws = ProjectWorkspace(project_path)
    active_file = settings.data_dir / "active_project.txt"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    active_file.write_text(str(ws.root), encoding="utf-8")
    return {"path": str(ws.root), "scan": ws.scan()}


@app.get("/api/memories")
async def api_list_memories(category: str = ""):
    return memory_store.list_all(category=category or None)


@app.post("/api/memories")
async def api_create_memory(
    content: str = Form(...),
    title: str = Form(""),
    category: str = Form(""),
):
    return memory_store.create(content, title=title, category=category or None)


@app.put("/api/memories/{memory_id}")
async def api_update_memory(memory_id: str, request: Request):
    body = await request.json()
    result = memory_store.update(memory_id, **body)
    if not result:
        return {"error": "not found"}
    return result


@app.delete("/api/memories/{memory_id}")
async def api_delete_memory(memory_id: str):
    return {"deleted": memory_store.delete(memory_id)}


@app.post("/api/import/chatgpt")
async def api_import_chatgpt(file: UploadFile = File(...)):
    settings.imports_path.mkdir(parents=True, exist_ok=True)
    dest = settings.imports_path / file.filename
    content = await file.read()
    dest.write_bytes(content)
    result = importer.import_file(dest)
    return result


@app.get("/api/categories")
async def api_categories():
    return {c.value: label for c, label in CATEGORY_LABELS.items()}