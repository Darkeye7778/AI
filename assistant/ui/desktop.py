"""Local desktop chat — ChatGPT-style sidebar with projects and chat history."""

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from assistant.agent.loop import AgentLoop
from assistant.chat.manager import ChatManager
from assistant.config import settings, validate_installation
from assistant.db.database import init_db
from assistant.ingest.chatgpt import ChatGPTImporter
from assistant.memory.store import MemoryStore

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "Personal Assistant"
SIDEBAR_W = 280
ACTIVE_BTN = ("#2b5278", "#1f3d5c")
NORMAL_BTN = ("gray25", "gray20")


class DesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1200x760")
        self.minsize(900, 520)

        init_db()
        issues = validate_installation()
        if issues:
            messagebox.showwarning("Setup warning", "\n".join(issues))

        self.agent: AgentLoop | None = None
        self.chats = ChatManager()
        self.memory = MemoryStore()
        self.memory.migrate_legacy_json(settings.legacy_memory_path)

        self.session_id: str | None = None
        self.current_mode = "chat"
        self.project_path = self._load_active_project()
        self.is_busy = False
        self.chat_row = 0
        self.session_buttons: dict[str, ctk.CTkButton] = {}
        self._collapsed_projects: set[str] = set()
        self._project_chat_rows: dict[str, list[ctk.CTkButton]] = {}

        self.chats.ensure_project_for_path(self.project_path)
        self._build_layout()
        self._refresh_sidebar()
        self._show_welcome()

    def _load_active_project(self) -> str:
        active = settings.data_dir / "active_project.txt"
        if active.exists():
            return active.read_text(encoding="utf-8").strip()
        return str(settings.workspace_dir)

    def _save_active_project(self, path: str) -> None:
        active = settings.data_dir / "active_project.txt"
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text(path, encoding="utf-8")
        self.project_path = path
        self.chats.ensure_project_for_path(path)

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, width=SIDEBAR_W, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(4, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sidebar, text=APP_NAME, font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(16, 10), sticky="w"
        )

        ctk.CTkButton(sidebar, text="+ New chat", command=self._new_chat, height=34).grid(
            row=1, column=0, padx=10, pady=3, sticky="ew"
        )
        ctk.CTkButton(sidebar, text="+ New project", command=self._new_project, height=30,
                      fg_color="gray30", hover_color="gray25").grid(
            row=2, column=0, padx=10, pady=3, sticky="ew"
        )
        ctk.CTkButton(sidebar, text="Import ChatGPT...", command=self._import_chatgpt, height=30,
                      fg_color="gray30", hover_color="gray25").grid(
            row=3, column=0, padx=10, pady=3, sticky="ew"
        )

        self.sidebar_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.sidebar_scroll.grid(row=4, column=0, sticky="nsew", padx=6, pady=6)
        self.sidebar_scroll.grid_columnconfigure(0, weight=1)

        # Bottom controls
        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 12))

        self.mode_var = ctk.StringVar(value="chat")
        ctk.CTkRadioButton(bottom, text="Chat", variable=self.mode_var, value="chat",
                           command=self._on_mode_change).pack(anchor="w")
        ctk.CTkRadioButton(bottom, text="Build", variable=self.mode_var, value="build",
                           command=self._on_mode_change).pack(anchor="w", pady=(0, 6))

        self.project_label = ctk.CTkLabel(
            bottom, text=self._short_path(self.project_path),
            font=ctk.CTkFont(size=10), text_color="gray60", wraplength=240,
        )
        self.project_label.pack(anchor="w")
        ctk.CTkButton(bottom, text="Set build folder", command=self._pick_project,
                      height=26, fg_color="gray30").pack(fill="x", pady=(4, 0))

        # ── Main area ────────────────────────────────────────────
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.chat_title_label = ctk.CTkLabel(
            main, text="New chat", font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        self.chat_title_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))

        self.chat_frame = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        input_frame = ctk.CTkFrame(main, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkTextbox(input_frame, height=76, font=ctk.CTkFont(size=14))
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input_box.bind("<Return>", self._on_enter)

        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="ns")
        self.send_btn = ctk.CTkButton(btn_frame, text="Send", width=76, command=self._send)
        self.send_btn.pack(pady=(0, 4))
        self.status_label = ctk.CTkLabel(btn_frame, text="", font=ctk.CTkFont(size=10), text_color="gray60")
        self.status_label.pack()

    def _short_path(self, path: str) -> str:
        return path if len(path) <= 34 else "…" + path[-31:]

    def _refresh_sidebar(self):
        for w in self.sidebar_scroll.winfo_children():
            w.destroy()
        self.session_buttons.clear()
        self._project_chat_rows.clear()

        data = self.chats.grouped_sidebar()
        row = 0

        # Project folders — collapsible like ChatGPT
        visible_projects = [
            g for g in data["projects"]
            if g["chats"] or g["project"].get("path")
        ]
        if visible_projects:
            ctk.CTkLabel(
                self.sidebar_scroll, text="Projects",
                font=ctk.CTkFont(size=11, weight="bold"), text_color="gray55", anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=6, pady=(6, 4))
            row += 1

        for group in visible_projects:
            proj = group["project"]
            pid = proj["id"]
            collapsed = pid in self._collapsed_projects
            chevron = "▸" if collapsed else "▾"
            count = len(group["chats"])
            label = f"{chevron} {proj['name']}"
            if count:
                label += f"  ({count})"

            header = ctk.CTkButton(
                self.sidebar_scroll,
                text=label,
                anchor="w",
                height=28,
                fg_color="transparent",
                hover_color=("gray30", "gray25"),
                text_color="gray80",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda p=proj: self._toggle_project(p["id"]),
            )
            header.grid(row=row, column=0, sticky="ew", padx=2, pady=1)
            header.bind(
                "<Button-3>",
                lambda e, p=proj: self._project_context_menu(e, p),
            )
            row += 1

            chat_btns: list[ctk.CTkButton] = []
            if not collapsed:
                for chat in group["chats"]:
                    btn = self._add_sidebar_chat_button(row, chat, indent=16)
                    chat_btns.append(btn)
                    row += 1
            self._project_chat_rows[pid] = chat_btns

        # Uncategorized chats
        if data["uncategorized"]:
            ctk.CTkLabel(
                self.sidebar_scroll, text="Recent chats",
                font=ctk.CTkFont(size=11, weight="bold"), text_color="gray55", anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=6, pady=(12, 4))
            row += 1
            for chat in data["uncategorized"]:
                self._add_sidebar_chat_button(row, chat)
                row += 1

        self._highlight_active_session()

    def _toggle_project(self, project_id: str):
        if project_id in self._collapsed_projects:
            self._collapsed_projects.discard(project_id)
        else:
            self._collapsed_projects.add(project_id)
        self._refresh_sidebar()

    def _project_context_menu(self, event, project: dict):
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        if project.get("path"):
            menu.add_command(
                label="Set as build folder",
                command=lambda: self._activate_project_folder(project["path"]),
            )
        menu.add_command(
            label="Expand" if project["id"] in self._collapsed_projects else "Collapse",
            command=lambda: self._toggle_project(project["id"]),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _activate_project_folder(self, path: str):
        if path:
            self._save_active_project(path)
            self.project_label.configure(text=self._short_path(path))

    def _add_sidebar_chat_button(
        self, row: int, chat: dict, indent: int = 8
    ) -> ctk.CTkButton:
        title = chat["title"][:34] + ("…" if len(chat["title"]) > 34 else "")
        btn = ctk.CTkButton(
            self.sidebar_scroll,
            text=title,
            anchor="w",
            height=30,
            fg_color=NORMAL_BTN[0],
            hover_color=NORMAL_BTN[1],
            font=ctk.CTkFont(size=12),
            command=lambda sid=chat["id"]: self._open_session(sid),
        )
        btn.grid(row=row, column=0, sticky="ew", padx=(indent, 2), pady=1)
        btn.bind("<Button-3>", lambda e, c=chat: self._chat_context_menu(e, c))
        self.session_buttons[chat["id"]] = btn
        return btn

    def _chat_context_menu(self, event, chat: dict):
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Rename", command=lambda: self._rename_chat(chat["id"]))
        projects = self.chats.list_projects()
        if projects:
            submenu = tk.Menu(menu, tearoff=0)
            for p in projects:
                submenu.add_command(
                    label=p["name"],
                    command=lambda pid=p["id"], sid=chat["id"]: self._move_chat(sid, pid),
                )
            submenu.add_command(
                label="(No project)",
                command=lambda sid=chat["id"]: self._move_chat(sid, None),
            )
            menu.add_cascade(label="Move to project", menu=submenu)
        menu.add_command(label="Delete", command=lambda: self._delete_chat(chat["id"]))
        menu.tk_popup(event.x_root, event.y_root)

    def _rename_chat(self, session_id: str):
        current = self.chats.get_session(session_id)
        if not current:
            return
        new_title = simpledialog.askstring("Rename chat", "Title:", initialvalue=current["title"])
        if new_title and new_title.strip():
            self.chats.rename_session(session_id, new_title.strip())
            if session_id == self.session_id:
                self.chat_title_label.configure(text=new_title.strip())
            self._refresh_sidebar()

    def _move_chat(self, session_id: str, project_id: str | None):
        self.chats.assign_session_project(session_id, project_id)
        self._refresh_sidebar()

    def _delete_chat(self, session_id: str):
        if not messagebox.askyesno("Delete chat", "Delete this conversation?"):
            return
        self.chats.delete_session(session_id)
        if session_id == self.session_id:
            self._new_chat()
        else:
            self._refresh_sidebar()

    def _highlight_active_session(self):
        for sid, btn in self.session_buttons.items():
            if sid == self.session_id:
                btn.configure(fg_color=ACTIVE_BTN[0], hover_color=ACTIVE_BTN[1])
            else:
                btn.configure(fg_color=NORMAL_BTN[0], hover_color=NORMAL_BTN[1])

    def _clear_chat_view(self):
        for w in self.chat_frame.winfo_children():
            w.destroy()
        self.chat_row = 0

    def _show_welcome(self):
        self._clear_chat_view()
        self.chat_title_label.configure(text="New chat")
        self._add_bubble(
            "assistant",
            "Talk to me like ChatGPT — ideas, plans, thinking out loud.\n"
            "Chats auto-organize into project folders and rename as context builds.",
        )

    def _open_session(self, session_id: str):
        if self.is_busy:
            return
        self.session_id = session_id
        self._clear_chat_view()

        messages = self.chats.get_messages(session_id)
        session = self.chats.get_session(session_id)
        self.chat_title_label.configure(text=session["title"] if session else "Chat")

        if not messages:
            self._add_bubble("assistant", "Empty conversation. Say something to continue.")
        else:
            for m in messages:
                role = "user" if m["role"] == "user" else "assistant"
                if m["role"] in ("plan", "system"):
                    role = m["role"]
                self._add_bubble(role, m["content"])

        self._highlight_active_session()

    def _new_chat(self):
        self.session_id = None
        self._show_welcome()
        self._highlight_active_session()

    def _new_project(self):
        name = simpledialog.askstring("New project", "Project name:")
        if not name:
            return
        path = filedialog.askdirectory(title="Optional: link a folder") or ""
        self.chats.create_project(name.strip(), path=path)
        self._refresh_sidebar()

    def _on_mode_change(self):
        self.current_mode = self.mode_var.get()

    def _pick_project(self):
        path = filedialog.askdirectory(title="Choose build folder")
        if path:
            self._save_active_project(path)
            self.project_label.configure(text=self._short_path(path))
            self._refresh_sidebar()

    def _import_chatgpt(self):
        path = filedialog.askopenfilename(
            title="Import ChatGPT export",
            filetypes=[("ChatGPT export", "*.zip *.json"), ("All", "*.*")],
        )
        if not path:
            return
        self._set_busy(True)

        def run():
            try:
                settings.imports_path.mkdir(parents=True, exist_ok=True)
                dest = settings.imports_path / Path(path).name
                dest.write_bytes(Path(path).read_bytes())
                result = ChatGPTImporter(self.memory, self.chats).import_file(dest)
                msg = (
                    f"Imported {result['conversations_parsed']} conversations into "
                    f"{result.get('chats_imported', 0)} sidebar chats "
                    f"({result.get('projects_organized', 0)} project folders). "
                    f"Skipped {result.get('chats_skipped', 0)} duplicates. "
                    f"Extracted {result['memories_extracted']} memories."
                )
                self.after(0, lambda: self._finish_import(msg, refresh=True))
            except Exception as e:
                self.after(0, lambda: self._finish_import(f"Import failed: {e}", refresh=False))

        threading.Thread(target=run, daemon=True).start()

    def _finish_import(self, message: str, refresh: bool = False):
        self._add_bubble("assistant", message)
        if refresh:
            self._refresh_sidebar()
        self._set_busy(False)

    def _on_enter(self, event):
        if not event.state & 0x1:
            self._send()
            return "break"

    def _send(self):
        if self.is_busy:
            return
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return
        self.input_box.delete("1.0", "end")
        self._add_bubble("user", text)
        self._set_busy(True)
        threading.Thread(target=self._process_message, args=(text,), daemon=True).start()

    def _get_agent(self) -> AgentLoop:
        if self.agent is None:
            self.agent = AgentLoop()
            self.chats = self.agent.chats
        return self.agent

    def _process_message(self, text: str):
        try:
            build_mode = self.current_mode == "build"
            if build_mode and not self.project_path:
                self._show_response({"response": "Set a build folder first (sidebar → Set build folder)."})
                return

            result = self._get_agent().chat(
                text,
                session_id=self.session_id,
                mode="safe",
                build_mode=build_mode,
                project_path=self.project_path,
            )
            self.session_id = result.get("session_id", self.session_id)
            self._show_response(result)
        except Exception as e:
            self._show_response({"response": f"Error: {e}"})

    def _show_response(self, result: dict):
        self.after(0, lambda: self._display_result(result))

    def _display_result(self, result: dict):
        response = result.get("response", result.get("error", "No response."))
        self._add_bubble("assistant", response)

        meta = result.get("meta") or {}
        if meta.get("title"):
            self.chat_title_label.configure(text=meta["title"])
        if meta.get("project_name"):
            self._add_bubble("system", f"Organized under project: {meta['project_name']}")

        if result.get("build_mode") and result.get("plan"):
            self._add_bubble("plan", result["plan"])

        self._refresh_sidebar()
        self._set_busy(False)

    def _add_bubble(self, role: str, text: str):
        colors = {
            "user": ("#2b5278", "right"),
            "assistant": ("#2d2d30", "left"),
            "system": ("#1a1a1a", "left"),
            "plan": ("#1e2a3a", "left"),
        }
        bg, align = colors.get(role, ("#2d2d30", "left"))

        frame = ctk.CTkFrame(self.chat_frame, fg_color=bg, corner_radius=12)
        frame.grid(
            row=self.chat_row, column=0,
            sticky="ew" if align == "left" else "e",
            pady=4, padx=(0, 60) if align == "left" else (60, 0),
        )
        self.chat_row += 1

        labels = {"user": "You", "assistant": "Assistant", "plan": "Plan", "system": ""}
        if labels.get(role):
            ctk.CTkLabel(frame, text=labels[role], font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="gray60").pack(anchor="w", padx=12, pady=(6, 0))
        ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=14), wraplength=620,
                     justify="left", anchor="w").pack(anchor="w", padx=12, pady=(4, 10))
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    def _set_busy(self, busy: bool):
        self.is_busy = busy
        self.send_btn.configure(state="disabled" if busy else "normal")
        self.status_label.configure(text="Thinking…" if busy else "")


def run_desktop():
    import traceback
    try:
        app = DesktopApp()
        app.mainloop()
    except Exception as e:
        log_path = settings.data_dir / "crash.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            messagebox.showerror("Startup Error", f"{e}\n\nSee {log_path}")
        except Exception:
            print(traceback.format_exc())
        raise