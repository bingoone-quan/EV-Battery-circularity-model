from __future__ import annotations

import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_LAUNCHER = PROJECT_ROOT / "start_static_gui.bat"
DYNAMIC_LAUNCHER = PROJECT_ROOT / "start_dynamic_gui.bat"

BG = "#f6f1e8"
PANEL = "#fffaf2"
TEXT = "#1f2a2e"
MUTED = "#5f6b70"
ACCENT = "#1e5f5a"
ACCENT_HOVER = "#174a46"
SECONDARY = "#d7e6e3"
BORDER = "#d5ccc0"


def _launch(target: Path) -> None:
    if not target.exists():
        messagebox.showerror("Launcher Error", f"启动文件不存在：\n{target}")
        return

    try:
        os.startfile(str(target))
    except OSError:
        subprocess.Popen(["cmd", "/c", str(target)], cwd=str(PROJECT_ROOT))


def _build_card(parent, title: str, subtitle: str, description: str, button_text: str, target: Path):
    card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="x", pady=10)

    top = tk.Frame(card, bg=PANEL)
    top.pack(fill="x", padx=22, pady=(18, 8))

    title_label = tk.Label(
        top,
        text=title,
        bg=PANEL,
        fg=TEXT,
        font=("Segoe UI Semibold", 18),
        anchor="w",
    )
    title_label.pack(anchor="w")

    subtitle_label = tk.Label(
        top,
        text=subtitle,
        bg=PANEL,
        fg=ACCENT,
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    )
    subtitle_label.pack(anchor="w", pady=(4, 0))

    desc_label = tk.Label(
        card,
        text=description,
        bg=PANEL,
        fg=MUTED,
        font=("Segoe UI", 11),
        justify="left",
        wraplength=640,
        anchor="w",
    )
    desc_label.pack(fill="x", padx=22, pady=(0, 16))

    button = tk.Button(
        card,
        text=button_text,
        bg=ACCENT,
        fg="white",
        activebackground=ACCENT_HOVER,
        activeforeground="white",
        relief="flat",
        bd=0,
        padx=16,
        pady=10,
        font=("Segoe UI Semibold", 11),
        cursor="hand2",
        command=lambda: _launch(target),
    )
    button.pack(anchor="w", padx=22, pady=(0, 20))

    return card


def main() -> None:
    root = tk.Tk()
    root.title("Battery Model Launcher")
    root.geometry("780x560")
    root.minsize(720, 520)
    root.configure(bg=BG)

    outer = tk.Frame(root, bg=BG)
    outer.pack(fill="both", expand=True, padx=26, pady=24)

    header = tk.Frame(outer, bg=BG)
    header.pack(fill="x", pady=(0, 18))

    title = tk.Label(
        header,
        text="EV Battery Model Launcher",
        bg=BG,
        fg=TEXT,
        font=("Segoe UI Semibold", 24),
        anchor="w",
    )
    title.pack(anchor="w")

    subtitle = tk.Label(
        header,
        text="Choose which model version to launch. The interface will call the matching Streamlit starter automatically.",
        bg=BG,
        fg=MUTED,
        font=("Segoe UI", 11),
        anchor="w",
    )
    subtitle.pack(anchor="w", pady=(6, 0))

    note = tk.Frame(outer, bg=SECONDARY, highlightbackground=BORDER, highlightthickness=1)
    note.pack(fill="x", pady=(0, 14))

    note_label = tk.Label(
        note,
        text=(
            "Start the project from this launcher instead of double-clicking app.py. "
            "If Python or Streamlit is missing, the starter script will show a clear message."
        ),
        bg=SECONDARY,
        fg=TEXT,
        font=("Segoe UI", 10),
        justify="left",
        wraplength=700,
        padx=18,
        pady=14,
    )
    note_label.pack(fill="x")

    cards = tk.Frame(outer, bg=BG)
    cards.pack(fill="both", expand=True)

    _build_card(
        cards,
        title="Static Version",
        subtitle="Static Model",
        description=(
            "Use this version for the current static scenario-comparison model. "
            "It includes EverBatt inputs, policy subsidy, market response, and static Monte Carlo visual outputs."
        ),
        button_text="Launch Static Version",
        target=STATIC_LAUNCHER,
    )

    _build_card(
        cards,
        title="Dynamic Version",
        subtitle="Dynamic Model",
        description=(
            "Use this version for the dynamic stock-flow model. "
            "It supports battery-size coupling, richer time-evolution outputs, and dynamic batch-analysis workflows."
        ),
        button_text="Launch Dynamic Version",
        target=DYNAMIC_LAUNCHER,
    )

    footer = tk.Label(
        outer,
        text=str(PROJECT_ROOT),
        bg=BG,
        fg=MUTED,
        font=("Consolas", 9),
        anchor="w",
    )
    footer.pack(fill="x", pady=(12, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
