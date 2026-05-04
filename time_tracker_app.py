import json
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "TimeTracker"
DATA_FILE_NAME = "time_entries.json"
TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_app_dir() -> Path:
    """
    Returns the directory where the app stores its JSON file.

    When bundled with PyInstaller, sys.executable points to the .exe path.
    When run as a normal Python script, __file__ points to this source file.

    This intentionally uses the application folder, not AppData, so the JSON file
    is easy to find and manually verify.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DATA_FILE = get_app_dir() / DATA_FILE_NAME


@dataclass
class TimeEntry:
    id: str
    day: str
    task: str
    start: str
    end: str
    minutes: int
    note: str
    created_at: str
    updated_at: str


def now_string() -> str:
    return datetime.now().strftime(DATETIME_FORMAT)


def today_string() -> str:
    return date.today().isoformat()


def parse_hhmm(value: str) -> time:
    return datetime.strptime(value.strip(), TIME_FORMAT).time()


def minutes_between(start_value: str, end_value: str) -> int:
    """
    Calculates duration in minutes for the current day.
    If end is before start, it assumes the work crossed midnight.
    """
    start_time = parse_hhmm(start_value)
    end_time = parse_hhmm(end_value)

    base_day = date.today()
    start_dt = datetime.combine(base_day, start_time)
    end_dt = datetime.combine(base_day, end_time)

    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    return int((end_dt - start_dt).total_seconds() // 60)


def format_minutes(minutes: int) -> str:
    hours, mins = divmod(max(0, minutes), 60)
    return f"{hours}h {mins:02d}m"


def load_entries() -> list[dict]:
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        backup_file = DATA_FILE.with_suffix(".json.corrupted")
        DATA_FILE.rename(backup_file)
        messagebox.showwarning(
            "File JSON non valido",
            f"Il file {DATA_FILE_NAME} non era leggibile ed è stato rinominato in:\n{backup_file}\n\n"
            "Verrà creato un nuovo file JSON.",
        )
        return []

    if not isinstance(data, list):
        messagebox.showwarning(
            "Formato JSON non valido",
            f"Il file {DATA_FILE_NAME} deve contenere una lista di consuntivazioni.",
        )
        return []

    return data


def save_entries(entries: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = DATA_FILE.with_suffix(".json.tmp")

    with tmp_file.open("w", encoding="utf-8") as file:
        json.dump(entries, file, ensure_ascii=False, indent=2)

    tmp_file.replace(DATA_FILE)


class TimeTrackerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_NAME)
        self.geometry("860x560")
        self.minsize(760, 480)

        self.entries: list[dict] = load_entries()
        self.running_start: datetime | None = None
        self.running_task = tk.StringVar()

        self.task_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.note_var = tk.StringVar()
        self.timer_status_var = tk.StringVar(value="Timer non avviato")
        self.total_today_var = tk.StringVar(value="Totale oggi: 0h 00m")
        self.data_file_var = tk.StringVar(value=f"File dati: {DATA_FILE}")

        self._configure_style()
        self._build_layout()
        self.refresh_day_view()
        self.tick_timer()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Total.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Treeview", rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X)

        ttk.Label(header, text="Time Tracker", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Registra a minuti il lavoro della giornata. Lo storico completo resta nel JSON.",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(2, 10))

        form = ttk.LabelFrame(root, text="Nuova consuntivazione", padding=12)
        form.pack(fill=tk.X, pady=(0, 10))

        form.columnconfigure(1, weight=2)
        form.columnconfigure(3, weight=1)
        form.columnconfigure(5, weight=1)

        ttk.Label(form, text="Task / progetto").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(form, textvariable=self.task_var).grid(row=0, column=1, sticky=tk.EW, padx=(0, 12), pady=4)

        ttk.Label(form, text="Inizio").grid(row=0, column=2, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(form, textvariable=self.start_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=(0, 12), pady=4)

        ttk.Label(form, text="Fine").grid(row=0, column=4, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(form, textvariable=self.end_var, width=8).grid(row=0, column=5, sticky=tk.W, pady=4)

        ttk.Label(form, text="Nota").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(form, textvariable=self.note_var).grid(row=1, column=1, columnspan=5, sticky=tk.EW, pady=4)

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=6, sticky=tk.EW, pady=(10, 0))

        ttk.Button(buttons, text="Ora come inizio", command=self.set_start_now).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Ora come fine", command=self.set_end_now).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Aggiungi", command=self.add_manual_entry).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Pulisci", command=self.clear_form).pack(side=tk.LEFT)

        timer = ttk.LabelFrame(root, text="Timer rapido", padding=12)
        timer.pack(fill=tk.X, pady=(0, 10))
        timer.columnconfigure(1, weight=1)

        ttk.Label(timer, text="Task corrente").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        ttk.Entry(timer, textvariable=self.running_task).grid(row=0, column=1, sticky=tk.EW, padx=(0, 12))
        ttk.Button(timer, text="Start", command=self.start_timer).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(timer, text="Stop e salva", command=self.stop_timer).grid(row=0, column=3)
        ttk.Label(timer, textvariable=self.timer_status_var).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(8, 0))

        summary = ttk.Frame(root)
        summary.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(summary, textvariable=self.total_today_var, style="Total.TLabel").pack(side=tk.LEFT)
        ttk.Label(summary, textvariable=self.data_file_var, style="Subtitle.TLabel").pack(side=tk.RIGHT)

        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("start", "end", "minutes", "task", "note")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("start", text="Inizio")
        self.tree.heading("end", text="Fine")
        self.tree.heading("minutes", text="Durata")
        self.tree.heading("task", text="Task / progetto")
        self.tree.heading("note", text="Nota")

        self.tree.column("start", width=80, anchor=tk.CENTER, stretch=False)
        self.tree.column("end", width=80, anchor=tk.CENTER, stretch=False)
        self.tree.column("minutes", width=90, anchor=tk.CENTER, stretch=False)
        self.tree.column("task", width=260, anchor=tk.W)
        self.tree.column("note", width=260, anchor=tk.W)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Frame(root)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(footer, text="Elimina riga selezionata", command=self.delete_selected_entry).pack(side=tk.LEFT)
        ttk.Button(footer, text="Ricarica JSON", command=self.reload_from_json).pack(side=tk.LEFT, padx=(6, 0))

        self.bind("<Control-Return>", lambda _event: self.add_manual_entry())
        self.bind("<F5>", lambda _event: self.refresh_day_view())

    def set_start_now(self) -> None:
        self.start_var.set(datetime.now().strftime(TIME_FORMAT))

    def set_end_now(self) -> None:
        self.end_var.set(datetime.now().strftime(TIME_FORMAT))

    def clear_form(self) -> None:
        self.task_var.set("")
        self.start_var.set("")
        self.end_var.set("")
        self.note_var.set("")

    def validate_entry_input(self, task: str, start: str, end: str) -> int | None:
        if not task.strip():
            messagebox.showerror("Task mancante", "Inserisci il nome del task/progetto.")
            return None

        try:
            minutes = minutes_between(start, end)
        except ValueError:
            messagebox.showerror("Orario non valido", "Usa il formato HH:MM, ad esempio 09:30 o 17:05.")
            return None

        if minutes <= 0:
            messagebox.showerror("Durata non valida", "La durata deve essere maggiore di zero minuti.")
            return None

        return minutes

    def add_manual_entry(self) -> None:
        task = self.task_var.get().strip()
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()
        note = self.note_var.get().strip()

        minutes = self.validate_entry_input(task, start, end)
        if minutes is None:
            return

        self.add_entry(task=task, start=start, end=end, minutes=minutes, note=note)
        self.clear_form()

    def add_entry(self, task: str, start: str, end: str, minutes: int, note: str = "") -> None:
        timestamp = now_string()
        entry = TimeEntry(
            id=str(uuid.uuid4()),
            day=today_string(),
            task=task,
            start=start,
            end=end,
            minutes=minutes,
            note=note,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.entries.append(asdict(entry))
        save_entries(self.entries)
        self.refresh_day_view()

    def start_timer(self) -> None:
        task = self.running_task.get().strip()
        if not task:
            messagebox.showerror("Task mancante", "Inserisci il task corrente prima di avviare il timer.")
            return

        self.running_start = datetime.now().replace(second=0, microsecond=0)
        self.timer_status_var.set(f"Timer avviato alle {self.running_start.strftime(TIME_FORMAT)} per: {task}")

    def stop_timer(self) -> None:
        if self.running_start is None:
            messagebox.showerror("Timer non avviato", "Avvia prima il timer.")
            return

        task = self.running_task.get().strip()
        if not task:
            messagebox.showerror("Task mancante", "Il task corrente è vuoto.")
            return

        end_dt = datetime.now().replace(second=0, microsecond=0)
        if end_dt <= self.running_start:
            end_dt = self.running_start + timedelta(minutes=1)

        minutes = int((end_dt - self.running_start).total_seconds() // 60)
        self.add_entry(
            task=task,
            start=self.running_start.strftime(TIME_FORMAT),
            end=end_dt.strftime(TIME_FORMAT),
            minutes=minutes,
            note="registrato con timer",
        )

        self.running_start = None
        self.running_task.set("")
        self.timer_status_var.set("Timer salvato")

    def tick_timer(self) -> None:
        if self.running_start is not None:
            elapsed = int((datetime.now() - self.running_start).total_seconds() // 60)
            task = self.running_task.get().strip() or "task senza nome"
            self.timer_status_var.set(
                f"Timer attivo: {task} — iniziato alle {self.running_start.strftime(TIME_FORMAT)} — elapsed {format_minutes(elapsed)}"
            )
        self.after(1000, self.tick_timer)

    def today_entries(self) -> list[dict]:
        current_day = today_string()
        return [entry for entry in self.entries if entry.get("day") == current_day]

    def refresh_day_view(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        entries = sorted(self.today_entries(), key=lambda item: (item.get("start", ""), item.get("end", "")))
        total_minutes = 0

        for entry in entries:
            minutes = int(entry.get("minutes", 0))
            total_minutes += minutes
            self.tree.insert(
                "",
                tk.END,
                iid=entry.get("id"),
                values=(
                    entry.get("start", ""),
                    entry.get("end", ""),
                    format_minutes(minutes),
                    entry.get("task", ""),
                    entry.get("note", ""),
                ),
            )

        self.total_today_var.set(f"Totale oggi: {format_minutes(total_minutes)}")

    def delete_selected_entry(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Nessuna riga selezionata", "Seleziona una riga da eliminare.")
            return

        entry_id = selected[0]
        confirmed = messagebox.askyesno("Conferma eliminazione", "Vuoi eliminare la riga selezionata?")
        if not confirmed:
            return

        self.entries = [entry for entry in self.entries if entry.get("id") != entry_id]
        save_entries(self.entries)
        self.refresh_day_view()

    def reload_from_json(self) -> None:
        self.entries = load_entries()
        self.refresh_day_view()


if __name__ == "__main__":
    app = TimeTrackerApp()
    app.mainloop()
