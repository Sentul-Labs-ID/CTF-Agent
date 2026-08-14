from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

import yaml

# Source UI lives in frontend/, while runtime data remains at the project root.
ROOT = Path(__file__).resolve().parent.parent
CHALLENGES_DIR = ROOT / "challenges"
LOGS_DIR = ROOT / "logs"
ENV_FILE = ROOT / ".env"
CLI = ROOT / ".venv" / "Scripts" / "ctf-solve.exe"
MODEL_OPTIONS = {
    "HEMAT | Codex GPT-5.6 Luna": "codex/gpt-5.6-luna",
    "SEDANG | Codex GPT-5.6 Terra": "codex/gpt-5.6-terra",
    "KUAT | Codex GPT-5.6 Sol": "codex/gpt-5.6-sol",
    "HEMAT | Claude Haiku 4.5": "anthropic/claude-haiku-4-5",
    "SEDANG | Claude Sonnet 4.6": "anthropic/claude-sonnet-4-6",
    "KUAT | Claude Opus 4.8": "anthropic/claude-opus-4-8",
    "HEMAT | Groq GPT-OSS 20B": "groq/openai/gpt-oss-20b",
    "SEDANG | Groq Llama 3.3 70B": "groq/llama-3.3-70b-versatile",
    "KUAT | Groq GPT-OSS 120B": "groq/openai/gpt-oss-120b",
    "HEMAT | Gemini 3.5 Flash-Lite": "google/gemini-3.5-flash-lite",
    "SEDANG | Gemini 3.6 Flash": "google/gemini-3.6-flash",
    "KUAT | Gemini 3.1 Pro Preview": "google/gemini-3.1-pro-preview",
}
MODELS = tuple(MODEL_OPTIONS)
DEFAULT_MODEL_LABEL = "SEDANG | Codex GPT-5.6 Terra"
CATEGORIES = ("web", "pwn", "reverse", "crypto", "forensics", "misc", "osint")


def _read_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    try:
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _has_api_key(name: str) -> bool:
    value = _read_env_values().get(name, "")
    return bool(value and "..." not in value and "your_" not in value.lower())


def _write_env_values(updates: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.append("# API keys added from the local GUI")
        output.extend(f"{key}={value}" for key, value in remaining.items())
    ENV_FILE.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower())
    return value.strip("-.") or "challenge"


def _find_codex() -> Path | None:
    if found := shutil.which("codex"):
        return Path(found)

    vscode_root = Path.home() / ".vscode" / "extensions"
    candidates = sorted(
        vscode_root.glob("openai.chatgpt-*/bin/windows-x86_64/codex.exe"),
        reverse=True,
    )
    return candidates[0] if candidates else None


class CTFGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CTF Agent — Local Solver")
        self.geometry("1080x780")
        self.minsize(900, 650)

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, str | int]] = queue.Queue()
        self.trace_path: Path | None = None
        self.trace_position = 0
        self.trace_files_before: set[Path] = set()
        self.metadata: dict = {}

        self.challenge_var = tk.StringVar()
        self.model_var = tk.StringVar(value=DEFAULT_MODEL_LABEL)
        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar(value="misc")
        self.value_var = tk.StringVar(value="0")
        self.connection_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Siap — pilih atau buat challenge.")
        self.model_help_var = tk.StringVar()
        self.api_status_var = tk.StringVar()

        self._configure_style()
        self._build_ui()
        self._update_model_help()
        self._refresh_api_status()
        self._refresh_challenges(select_first=True)
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Status.TLabel", padding=(8, 5))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="CTF Agent — Local Solver", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Mode aman: satu challenge, satu model AI, dan submit flag manual.",
        ).pack(anchor="w", pady=(0, 10))

        selector = ttk.LabelFrame(outer, text="Challenge", padding=10)
        selector.pack(fill="x")
        selector.columnconfigure(1, weight=1)

        ttk.Label(selector, text="Folder").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.challenge_combo = ttk.Combobox(selector, textvariable=self.challenge_var)
        self.challenge_combo.grid(row=0, column=1, sticky="ew")
        self.challenge_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_metadata())
        ttk.Button(selector, text="Refresh", command=self._refresh_challenges).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(selector, text="Pilih Folder…", command=self._browse_challenge).grid(
            row=0, column=3, padx=4
        )
        ttk.Button(selector, text="Buat Baru…", command=self._new_challenge).grid(
            row=0, column=4, padx=(4, 0)
        )

        ttk.Label(selector, text="Model").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(9, 0)
        )
        self.model_combo = ttk.Combobox(
            selector,
            textvariable=self.model_var,
            values=MODELS,
            state="readonly",
            width=40,
        )
        self.model_combo.grid(row=1, column=1, sticky="w", pady=(9, 0))
        self.model_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_model_help())
        ttk.Label(
            selector,
            textvariable=self.model_help_var,
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=8, pady=(9, 0))
        ttk.Button(selector, text="Atur API Key…", command=self._configure_api_keys).grid(
            row=1, column=4, sticky="e", pady=(9, 0)
        )
        ttk.Label(selector, textvariable=self.api_status_var).grid(
            row=2, column=1, columnspan=4, sticky="w", pady=(6, 0)
        )

        metadata = ttk.LabelFrame(outer, text="Metadata", padding=10)
        metadata.pack(fill="x", pady=(10, 0))
        metadata.columnconfigure(1, weight=1)
        metadata.columnconfigure(3, weight=1)

        ttk.Label(metadata, text="Nama").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(metadata, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 12)
        )
        ttk.Label(metadata, text="Kategori").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Combobox(
            metadata,
            textvariable=self.category_var,
            values=CATEGORIES,
        ).grid(row=0, column=3, sticky="ew")

        ttk.Label(metadata, text="Poin").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(metadata, textvariable=self.value_var, width=12).grid(
            row=1, column=1, sticky="w", pady=(8, 0)
        )
        ttk.Label(metadata, text="URL / host:port").grid(
            row=1, column=2, sticky="w", padx=(0, 8), pady=(8, 0)
        )
        ttk.Entry(metadata, textvariable=self.connection_var).grid(
            row=1, column=3, sticky="ew", pady=(8, 0)
        )

        ttk.Label(metadata, text="Deskripsi").grid(
            row=2, column=0, sticky="nw", padx=(0, 8), pady=(8, 0)
        )
        self.description_text = ScrolledText(metadata, height=5, wrap="word", font=("Segoe UI", 10))
        self.description_text.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(8, 0))

        metadata_actions = ttk.Frame(metadata)
        metadata_actions.grid(row=3, column=1, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(metadata_actions, text="Tambah File…", command=self._add_files).pack(
            side="left", padx=4
        )
        ttk.Button(metadata_actions, text="Buka Folder", command=self._open_challenge_folder).pack(
            side="left", padx=4
        )
        ttk.Button(
            metadata_actions, text="Buka Workspace", command=self._open_workspace_folder
        ).pack(side="left", padx=4)
        ttk.Button(metadata_actions, text="Simpan Metadata", command=self._save_metadata).pack(
            side="left", padx=(4, 0)
        )

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=10)
        self.start_button = ttk.Button(controls, text="▶ Mulai Solver", command=self._start_solver)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            controls, text="■ Hentikan", command=self._stop_solver, state="disabled"
        )
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(controls, text="Buka Trace Terbaru", command=self._open_latest_trace).pack(
            side="left"
        )
        ttk.Label(controls, textvariable=self.status_var, style="Status.TLabel").pack(side="right")

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)

        solver_frame = ttk.Frame(self.notebook)
        trace_frame = ttk.Frame(self.notebook)
        writeup_frame = ttk.Frame(self.notebook)
        self.notebook.add(solver_frame, text="Output Solver")
        self.notebook.add(trace_frame, text="Langkah Agent")
        self.notebook.add(writeup_frame, text="Write-up")

        self.solver_output = ScrolledText(
            solver_frame,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
            background="#101418",
            foreground="#d8dee9",
            insertbackground="white",
        )
        self.solver_output.pack(fill="both", expand=True)

        self.trace_output = ScrolledText(
            trace_frame,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
            background="#101418",
            foreground="#d8dee9",
            insertbackground="white",
        )
        self.trace_output.pack(fill="both", expand=True)

        writeup_actions = ttk.Frame(writeup_frame, padding=(0, 0, 0, 6))
        writeup_actions.pack(fill="x")
        ttk.Button(writeup_actions, text="Muat Ulang", command=self._load_writeup).pack(side="left")
        ttk.Button(writeup_actions, text="Simpan WRITEUP.md", command=self._save_writeup).pack(
            side="left", padx=6
        )
        ttk.Label(
            writeup_actions,
            text="Bisa diedit sebelum dikumpulkan; periksa ulang kredensial dan flag.",
        ).pack(side="left", padx=8)
        self.writeup_output = ScrolledText(
            writeup_frame,
            wrap="word",
            font=("Consolas", 10),
            undo=True,
        )
        self.writeup_output.pack(fill="both", expand=True)

    def _challenge_path(self) -> Path:
        raw = self.challenge_var.get().strip()
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path

    def _update_model_help(self) -> None:
        model = self._selected_model_spec()
        if model.startswith("codex/"):
            text = "Hemat = cepat/murah, Sedang = seimbang, Kuat = analisis tersulit. Codex memakai login."
        elif model.startswith("anthropic/"):
            text = "Hemat = cepat/murah, Sedang = seimbang, Kuat = analisis tersulit. Claude memakai API key, bukan kuota Claude Code."
        elif model.startswith("groq/"):
            text = "Hemat = cepat/murah, Sedang = seimbang, Kuat = analisis tersulit. Groq memakai output ringkas agar sesuai limit TPM."
        elif model.startswith("google/"):
            text = "Gemini memakai API key. Hemat dan Sedang stabil (GA); pilihan Kuat masih Preview dan mungkin memerlukan billing."
        else:
            text = "Provider model eksternal."
        self.model_help_var.set(text)

    def _selected_model_spec(self) -> str:
        return MODEL_OPTIONS.get(self.model_var.get(), MODEL_OPTIONS[DEFAULT_MODEL_LABEL])

    def _refresh_api_status(self) -> None:
        claude = "siap" if _has_api_key("ANTHROPIC_API_KEY") else "belum diatur"
        groq = "siap" if _has_api_key("GROQ_API_KEY") else "belum diatur"
        gemini = "siap" if _has_api_key("GEMINI_API_KEY") else "belum diatur"
        self.api_status_var.set(
            f"Status API — Claude: {claude} | Groq: {groq} | Gemini: {gemini}"
        )

    def _configure_api_keys(self) -> None:
        providers = {
            "anthropic/": ("Claude", "ANTHROPIC_API_KEY"),
            "groq/": ("Groq", "GROQ_API_KEY"),
            "google/": ("Gemini", "GEMINI_API_KEY"),
        }
        selected_model = self._selected_model_spec()
        selected_provider = next(
            (prefix for prefix in providers if selected_model.startswith(prefix)), None
        )
        targets = (
            [providers[selected_provider]] if selected_provider else list(providers.values())
        )
        updates = {}
        for provider_name, key_name in targets:
            value = simpledialog.askstring(
                f"{provider_name} API Key",
                f"Masukkan {key_name}. Kosongkan untuk mempertahankan key yang sudah ada:",
                parent=self,
                show="*",
            )
            if value is None:
                return
            if value.strip():
                updates[key_name] = value.strip()
        try:
            if updates:
                _write_env_values(updates)
                self.status_var.set("API key tersimpan lokal di .env.")
            self._refresh_api_status()
        except OSError as exc:
            messagebox.showerror("Gagal Menyimpan API Key", str(exc), parent=self)

    def _refresh_challenges(self, select_first: bool = False) -> None:
        CHALLENGES_DIR.mkdir(parents=True, exist_ok=True)
        choices = [
            str(path.parent.relative_to(ROOT))
            for path in sorted(CHALLENGES_DIR.glob("*/metadata.yml"))
        ]
        self.challenge_combo["values"] = choices
        current = self.challenge_var.get()
        if current in choices:
            return
        if choices and (select_first or not current):
            self.challenge_var.set(choices[0])
            self._load_metadata()

    def _browse_challenge(self) -> None:
        selected = filedialog.askdirectory(
            title="Pilih folder challenge",
            initialdir=CHALLENGES_DIR,
        )
        if selected:
            self.challenge_var.set(selected)
            self._load_metadata()

    def _new_challenge(self) -> None:
        name = simpledialog.askstring("Challenge Baru", "Nama challenge:", parent=self)
        if not name:
            return
        folder = CHALLENGES_DIR / _slugify(name)
        if folder.exists() and not messagebox.askyesno(
            "Folder Sudah Ada",
            f"{folder.name} sudah ada. Gunakan folder tersebut?",
            parent=self,
        ):
            return
        (folder / "distfiles").mkdir(parents=True, exist_ok=True)
        metadata_path = folder / "metadata.yml"
        if not metadata_path.exists():
            metadata_path.write_text(
                yaml.safe_dump(
                    {
                        "name": name,
                        "category": "misc",
                        "description": "",
                        "value": 0,
                        "connection_info": "",
                        "tags": [],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        self._refresh_challenges()
        self.challenge_var.set(str(folder.relative_to(ROOT)))
        self._load_metadata()

    def _load_metadata(self) -> None:
        path = self._challenge_path() / "metadata.yml"
        if not path.exists():
            self.metadata = {}
            self.status_var.set("metadata.yml tidak ditemukan.")
            return
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                raise ValueError("metadata.yml harus berupa mapping YAML")
            self.metadata = loaded
            self.name_var.set(str(loaded.get("name", "")))
            self.category_var.set(str(loaded.get("category", "misc")))
            self.value_var.set(str(loaded.get("value", 0)))
            self.connection_var.set(str(loaded.get("connection_info", "")))
            self.description_text.delete("1.0", "end")
            self.description_text.insert("1.0", str(loaded.get("description", "")))
            self._load_writeup(silent=True)
            self.status_var.set("Metadata dimuat.")
        except Exception as exc:
            messagebox.showerror("Metadata Tidak Valid", str(exc), parent=self)

    def _save_metadata(self, notify: bool = True) -> bool:
        folder = self._challenge_path()
        if not self.challenge_var.get().strip():
            messagebox.showerror("Challenge", "Pilih atau buat challenge dahulu.", parent=self)
            return False
        try:
            value = int(self.value_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Poin Tidak Valid", "Poin harus berupa angka.", parent=self)
            return False

        folder.mkdir(parents=True, exist_ok=True)
        (folder / "distfiles").mkdir(exist_ok=True)
        data = dict(self.metadata)
        data.update(
            {
                "name": self.name_var.get().strip() or folder.name,
                "category": self.category_var.get().strip() or "misc",
                "description": self.description_text.get("1.0", "end-1c").strip(),
                "value": value,
                "connection_info": self.connection_var.get().strip(),
            }
        )
        data.setdefault("tags", [])
        try:
            (folder / "metadata.yml").write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            self.metadata = data
            if notify:
                self.status_var.set("Metadata tersimpan.")
            self._refresh_challenges()
            return True
        except Exception as exc:
            messagebox.showerror("Gagal Menyimpan", str(exc), parent=self)
            return False

    def _add_files(self) -> None:
        folder = self._challenge_path()
        files = filedialog.askopenfilenames(title="Pilih file challenge")
        if not files:
            return
        distfiles = folder / "distfiles"
        distfiles.mkdir(parents=True, exist_ok=True)
        copied = 0
        for source_raw in files:
            source = Path(source_raw)
            destination = distfiles / source.name
            if destination.exists() and not messagebox.askyesno(
                "Timpa File?",
                f"{source.name} sudah ada. Timpa?",
                parent=self,
            ):
                continue
            shutil.copy2(source, destination)
            copied += 1
        self.status_var.set(f"{copied} file ditambahkan ke distfiles.")

    def _open_challenge_folder(self) -> None:
        folder = self._challenge_path()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # type: ignore[attr-defined]

    def _open_workspace_folder(self) -> None:
        folder = self._challenge_path() / "workspace"
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # type: ignore[attr-defined]

    def _load_writeup(self, silent: bool = False) -> None:
        path = self._challenge_path() / "WRITEUP.md"
        self.writeup_output.delete("1.0", "end")
        if path.exists():
            self.writeup_output.insert("1.0", path.read_text(encoding="utf-8"))
            if not silent:
                self.status_var.set("WRITEUP.md dimuat.")
        elif not silent:
            self.status_var.set("WRITEUP.md belum ada; file dibuat setelah flag ditemukan.")

    def _save_writeup(self) -> None:
        folder = self._challenge_path()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "WRITEUP.md"
        try:
            path.write_text(self.writeup_output.get("1.0", "end-1c"), encoding="utf-8")
            self.status_var.set("WRITEUP.md tersimpan.")
        except OSError as exc:
            messagebox.showerror("Gagal Menyimpan Write-up", str(exc), parent=self)

    def _start_solver(self) -> None:
        if self.process and self.process.poll() is None:
            return
        if not CLI.exists():
            messagebox.showerror("CTF Agent", f"CLI tidak ditemukan:\n{CLI}", parent=self)
            return
        selected_model = self._selected_model_spec()
        codex = None
        if selected_model.startswith("codex/"):
            codex = _find_codex()
            if not codex:
                messagebox.showerror(
                    "Codex Tidak Ditemukan",
                    "Codex CLI tidak ditemukan. Buka Codex/VS Code dan pastikan Codex sudah terpasang.",
                    parent=self,
                )
                return
        required_key = None
        if selected_model.startswith("anthropic/"):
            required_key = "ANTHROPIC_API_KEY"
        elif selected_model.startswith("groq/"):
            required_key = "GROQ_API_KEY"
        elif selected_model.startswith("google/"):
            required_key = "GEMINI_API_KEY"
        if required_key and not _has_api_key(required_key):
            messagebox.showerror(
                "API Key Belum Diatur",
                f"{required_key} belum tersedia. Klik 'Atur API Key…' dahulu.",
                parent=self,
            )
            return
        if not self._save_metadata(notify=False):
            return

        challenge = self._challenge_path().resolve()
        if challenge.name.lower() == "template" or self.name_var.get().strip().upper().startswith(
            "GANTI"
        ):
            messagebox.showerror(
                "Template Belum Siap",
                "Buat challenge baru atau ganti nama dan metadata template sebelum menjalankan solver.",
                parent=self,
            )
            return
        command = [
            str(CLI),
            "--challenge",
            str(challenge),
            "--models",
            selected_model,
            "--no-submit",
            "--max-challenges",
            "1",
            "-v",
        ]
        env = os.environ.copy()
        if codex:
            env["PATH"] = str(codex.parent) + os.pathsep + env.get("PATH", "")
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        self._clear_text(self.solver_output)
        self._clear_text(self.trace_output)
        self._append(self.solver_output, "$ " + subprocess.list2cmdline(command) + "\n\n")
        LOGS_DIR.mkdir(exist_ok=True)
        self.trace_files_before = set(LOGS_DIR.glob("trace-*.jsonl"))
        self.trace_path = None
        self.trace_position = 0

        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            self.process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
        except Exception as exc:
            messagebox.showerror("Gagal Menjalankan", str(exc), parent=self)
            return

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Solver sedang berjalan…")
        threading.Thread(target=self._read_process_output, daemon=True).start()

    def _read_process_output(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            self.output_queue.put(("output", line))
        return_code = self.process.wait()
        self.output_queue.put(("done", return_code))

    def _stop_solver(self) -> None:
        process = self.process
        if not process or process.poll() is not None:
            return
        self.status_var.set("Menghentikan solver…")
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.send_signal(signal.SIGINT)
        except Exception:
            process.terminate()
        self.after(4000, self._force_stop_if_needed)

    def _force_stop_if_needed(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()
                if kind == "output":
                    self._append(self.solver_output, str(payload))
                elif kind == "done":
                    return_code = int(payload)
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.status_var.set(
                        "Selesai." if return_code == 0 else f"Berhenti dengan kode {return_code}."
                    )
                    self._load_writeup(silent=True)
        except queue.Empty:
            pass
        self._poll_trace()
        self.after(100, self._poll_events)

    def _poll_trace(self) -> None:
        if self.trace_path is None and LOGS_DIR.exists():
            candidates = [
                path
                for path in LOGS_DIR.glob("trace-*.jsonl")
                if path not in self.trace_files_before
            ]
            if candidates:
                self.trace_path = max(candidates, key=lambda path: path.stat().st_mtime)
                self.trace_position = 0
                self._append(self.trace_output, f"Trace: {self.trace_path.name}\n\n")
        if not self.trace_path or not self.trace_path.exists():
            return
        try:
            with self.trace_path.open("r", encoding="utf-8") as trace_file:
                trace_file.seek(self.trace_position)
                for line in trace_file:
                    try:
                        self._render_trace_event(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                self.trace_position = trace_file.tell()
        except OSError:
            pass

    def _render_trace_event(self, event: dict) -> None:
        event_type = event.get("type", "event")
        step = event.get("step", "-")
        if event_type == "tool_call":
            self._append(
                self.trace_output,
                f"\n[LANGKAH {step}] {event.get('tool', '')}\n{event.get('args', '')}\n",
            )
        elif event_type == "tool_result":
            self._append(self.trace_output, f"[HASIL {step}]\n{event.get('result', '')}\n")
        elif event_type == "usage":
            self._append(
                self.trace_output,
                f"[USAGE] input={event.get('input_tokens', 0)}, "
                f"output={event.get('output_tokens', 0)}, "
                f"cache={event.get('cache_read_tokens', 0)}\n",
            )
        elif event_type == "model_response":
            self._append(self.trace_output, f"[RESPONS MODEL]\n{event.get('text', '')}\n")
        else:
            details = {key: value for key, value in event.items() if key not in {"ts", "type"}}
            self._append(self.trace_output, f"[{event_type.upper()}] {details}\n")

    def _open_latest_trace(self) -> None:
        traces = sorted(LOGS_DIR.glob("trace-*.jsonl"), key=lambda path: path.stat().st_mtime)
        if not traces:
            messagebox.showinfo("Trace", "Belum ada trace. Jalankan solver dahulu.", parent=self)
            return
        os.startfile(traces[-1])  # type: ignore[attr-defined]

    @staticmethod
    def _append(widget: ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", text)
        widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _clear_text(widget: ScrolledText) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno(
                "Solver Masih Berjalan",
                "Hentikan solver dan tutup aplikasi?",
                parent=self,
            ):
                return
            self._stop_solver()
        self.destroy()


if __name__ == "__main__":
    CTFGui().mainloop()
