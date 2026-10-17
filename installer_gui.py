"""Native Windows setup for an isolated Umbra RGB add-on installation.

The installer only reads and copies local files. It never starts Umbra or opens
the hub. Bundling this entry point with PyInstaller removes the user's need to
install Python; the patched application still uses their vendor runtime.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import installer_service
import patcher


BG = "#FFFFFF"
INK = "#171717"
MUTED = "#475569"
ACCENT = "#A16207"
BORDER = "#E5E7EB"


class InstallerWindow:
    """Keep file work off the Tk thread and ignore outdated validation results."""

    def __init__(self, root, source="", destination=""):
        self.root = root
        self.events = queue.Queue()
        self.plan = None
        self.operation = None
        self.revision = 0
        self.debounce = None
        self.closed = False
        self.completed = False
        self.last_error = ""
        self.last_error_operation = None
        self.installed_destination = None
        self.source = tk.StringVar(value=source)
        self.destination = tk.StringVar(
            value=destination or str(installer_service.default_destination()))
        self.status_title = tk.StringVar(value="Choose your original Umbra installation")
        self.status_body = tk.StringVar(
            value="Select the folder containing Sync_light.exe and its runtime files.")

        root.title("Umbra RGB Add-on Setup")
        root.iconbitmap(default=str(patcher.ROOT / "assets" / "umbra.ico"))
        root.geometry("780x640")
        root.minsize(700, 620)
        root.configure(background=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._styles()
        self._build()
        self.source.trace_add("write", self._selection_changed)
        self.destination.trace_add("write", self._selection_changed)
        root.after(80, self._drain_events)
        if source:
            self.debounce = root.after(150, self.check_selection)
        else:
            self.source_entry.focus_set()

    def _styles(self):
        style = ttk.Style(self.root)
        # The clam theme gives consistent focus rings and readable disabled
        # states on Windows without shipping a separate UI framework.
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK,
                        font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Status.TFrame", background="#F5F6F8")
        style.configure("Status.TLabel", background="#F5F6F8", foreground=MUTED)
        style.configure("StatusTitle.TLabel", background="#F5F6F8",
                        foreground=INK, font=("Segoe UI", 11, "bold"))
        style.configure("TEntry", padding=8, font=("Segoe UI", 10),
                        fieldbackground=BG, foreground=INK, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER)
        style.map("TEntry", bordercolor=[("focus", ACCENT)],
                  lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8),
                        background=BG, foreground=INK, bordercolor=BORDER,
                        focuscolor=ACCENT, focusthickness=2)
        style.map("TButton", background=[("active", "#F1F2F4")],
                  foreground=[("disabled", "#6B7280")])
        style.configure("Accent.TButton", background=ACCENT, foreground=BG,
                        bordercolor=ACCENT, focuscolor=INK)
        style.map("Accent.TButton", background=[("disabled", "#E8ECF0"),
                                                   ("active", "#854D0E")],
                  foreground=[("disabled", "#475569"), ("active", BG)])
        style.configure("Horizontal.TProgressbar", background=ACCENT,
                        troughcolor="#E5E7EB", borderwidth=0,
                        lightcolor=ACCENT, darkcolor=ACCENT)

    def _build(self):
        outer = ttk.Frame(self.root, padding=(30, 24, 30, 20))
        outer.grid(sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        ttk.Label(outer, text="Umbra RGB Add-on", style="Title.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(outer, text="Setup  " + patcher.VERSION,
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 16))
        intro = ttk.Label(outer,
                          text="Create a separate Umbra copy with manual LED count support.",
                          style="Muted.TLabel", wraplength=680)
        intro.grid(row=2, column=0, sticky="w", pady=(0, 22))

        ttk.Label(outer, text="Original Umbra folder", style="Heading.TLabel").grid(
            row=3, column=0, sticky="w", pady=(0, 6))
        source_row = ttk.Frame(outer)
        source_row.grid(row=4, column=0, sticky="ew")
        source_row.columnconfigure(0, weight=1)
        self.source_entry = ttk.Entry(source_row, textvariable=self.source)
        self.source_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.source_browse = ttk.Button(source_row, text="Browse…", command=self.browse_source)
        self.source_browse.grid(row=0, column=1)
        ttk.Label(outer, text="Supported: Umbra " + patcher.SUPPORTED_VERSION +
                  ". You can also paste a path to Sync_light.exe.",
                  style="Muted.TLabel", wraplength=680).grid(
                      row=5, column=0, sticky="w", pady=(6, 18))

        ttk.Label(outer, text="New add-on folder", style="Heading.TLabel").grid(
            row=6, column=0, sticky="w", pady=(0, 6))
        destination_row = ttk.Frame(outer)
        destination_row.grid(row=7, column=0, sticky="ew")
        destination_row.columnconfigure(0, weight=1)
        self.destination_entry = ttk.Entry(destination_row, textvariable=self.destination)
        self.destination_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.destination_browse = ttk.Button(destination_row, text="Change…",
                                             command=self.browse_destination)
        self.destination_browse.grid(row=0, column=1)
        ttk.Label(outer, text="Use a new folder. Your original installation stays unchanged.",
                  style="Muted.TLabel", wraplength=680).grid(
                      row=8, column=0, sticky="w", pady=(6, 18))

        status = ttk.Frame(outer, style="Status.TFrame", padding=16)
        status.grid(row=9, column=0, sticky="nsew")
        status.columnconfigure(0, weight=1)
        self.status_heading = ttk.Label(status, textvariable=self.status_title,
                                        style="StatusTitle.TLabel", wraplength=640)
        self.status_heading.grid(row=0, column=0, sticky="w")
        self.status_description = ttk.Label(status, textvariable=self.status_body,
                                            style="Status.TLabel", wraplength=640,
                                            justify="left")
        self.status_description.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        self.progress = ttk.Progressbar(status, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.progress.grid_remove()
        self.details_button = ttk.Button(status, text="Error details…", command=self.show_error)
        self.details_button.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.details_button.grid_remove()
        outer.rowconfigure(10, weight=1, minsize=12)

        ttk.Label(outer, text="Close Umbra and other RGB apps before installing.",
                  style="Muted.TLabel").grid(row=11, column=0, sticky="w", pady=(8, 12))
        actions = ttk.Frame(outer)
        actions.grid(row=12, column=0, sticky="ew")
        actions.columnconfigure(1, weight=1)
        self.check_button = ttk.Button(actions, text="Check installation", command=self.check_selection)
        self.check_button.grid(row=0, column=0, sticky="w")
        self.close_button = ttk.Button(actions, text="Close", command=self.close)
        self.close_button.grid(row=0, column=2, padx=(8, 8))
        self.install_button = ttk.Button(actions, text="Install add-on", style="Accent.TButton",
                                         command=self.install, state="disabled")
        self.install_button.grid(row=0, column=3, sticky="e")
        self.inputs = (self.source_entry, self.source_browse,
                       self.destination_entry, self.destination_browse)
        # Wrap explanatory text with the window, while leaving fields flexible.
        outer.bind("<Configure>", lambda event: self._resize_text(event.width))
        # Limit the form shortcut to its fields. Enter on Close, Browse or an
        # error dialog must never turn into an installation request.
        self.source_entry.bind("<Return>", self._enter)
        self.destination_entry.bind("<Return>", self._enter)

    def _resize_text(self, width):
        self.status_heading.configure(wraplength=max(360, width - 92))
        self.status_description.configure(wraplength=max(360, width - 92))

    def _enter(self, _event):
        if self.completed:
            return
        if self.plan is not None and self.operation is None:
            self.install()
        elif self.operation is None:
            self.check_selection()

    def browse_source(self):
        selected = filedialog.askdirectory(parent=self.root, title="Select original Umbra folder",
                                            mustexist=True)
        if selected:
            self.source.set(selected)

    def browse_destination(self):
        selected = filedialog.asksaveasfilename(
            parent=self.root, title="Choose a new add-on folder name",
            initialdir=str(Path(self.destination.get()).parent),
            initialfile=Path(self.destination.get()).name, confirmoverwrite=False)
        if selected:
            self.destination.set(selected)

    def _selection_changed(self, *_args):
        self.revision += 1
        self.plan = None
        self.install_button.configure(state="disabled")
        self.details_button.grid_remove()
        if self.debounce is not None:
            self.root.after_cancel(self.debounce)
            self.debounce = None
        if self.operation == "install" or self.completed:
            return
        self.status_title.set("Selection changed")
        self.status_body.set("Checking the selected paths does not change any files.")
        if self.source.get().strip() and self.destination.get().strip():
            self.debounce = self.root.after(650, self.check_selection)

    def check_selection(self):
        self.debounce = None
        if self.operation is not None or self.completed:
            return
        self.operation = "check"
        self.check_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.details_button.grid_remove()
        self.status_title.set("Checking your installation…")
        self.status_body.set("Verifying the supported app version, runtime files and new folder.")
        self.progress.grid()
        self.progress.start(12)
        revision, source, destination = self.revision, self.source.get(), self.destination.get()

        def work():
            try:
                plan = installer_service.validate_selection(source, destination)
                self.events.put(("checked", revision, plan))
            except Exception as error:
                self.events.put(("failed", revision, str(error)))

        threading.Thread(target=work, daemon=True).start()

    def install(self):
        if self.operation is not None or self.plan is None or self.completed:
            return
        if self.debounce is not None:
            self.root.after_cancel(self.debounce)
            self.debounce = None
        plan = self.plan
        self.operation = "install"
        self.last_error_operation = "install"
        self.installed_destination = plan.destination
        for widget in self.inputs:
            widget.configure(state="disabled")
        self.check_button.configure(state="disabled")
        self.close_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.status_title.set("Installing the add-on…")
        self.status_body.set("Keep this window open while the separate application copy is created.")
        self.progress.grid()
        self.progress.start(12)
        revision = self.revision

        def progress(stage, message):
            self.events.put(("progress", revision, (stage, message)))

        def work():
            try:
                installer_service.install_selection(plan, progress=progress)
                self.events.put(("installed", revision, plan.destination))
            except Exception as error:
                self.events.put(("failed", revision, str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _drain_events(self):
        if self.closed:
            return
        while True:
            try:
                kind, revision, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                titles = {"validate": "Rechecking the original installation…",
                          "copy": "Copying your Umbra runtime…",
                          "patch": "Adding manual LED count support…",
                          "complete": "Finishing installation…"}
                self.status_title.set(titles.get(value[0], "Installing…"))
                self.status_body.set(value[1])
                continue
            previous_operation = self.operation
            self.operation = None
            self.progress.stop()
            self.progress.grid_remove()
            self.check_button.configure(state="normal")
            if revision != self.revision:
                self.debounce = self.root.after(100, self.check_selection)
                continue
            if kind == "checked":
                self.plan = value
                self.last_error_operation = None
                self.status_title.set("Ready to install")
                self.status_body.set("Umbra " + patcher.SUPPORTED_VERSION +
                                     " is supported. Installation creates a separate copy and does not open the hub.")
                self.install_button.configure(state="normal")
            elif kind == "installed":
                self.completed = True
                self.status_title.set("Installation complete")
                self.status_body.set("Open the new folder and start " + patcher.OUTPUT_EXE +
                                     " manually. Keep its supporting files together. The app has not been started.")
                self.check_button.grid_remove()
                self.close_button.configure(state="normal")
                self.install_button.configure(text="Open folder", state="normal", command=self.open_folder)
                self.install_button.focus_set()
            elif kind == "failed":
                self.plan = None
                self.last_error = value
                self.last_error_operation = previous_operation
                self.status_title.set("Installation stopped" if previous_operation == "install"
                                      else "Please check your selection")
                self.status_body.set(self._friendly_error(value, previous_operation))
                self.details_button.grid()
                self.close_button.configure(state="normal")
                if previous_operation == "install":
                    for widget in self.inputs:
                        widget.configure(state="normal")
        self.root.after(80, self._drain_events)

    @staticmethod
    def _friendly_error(message, operation):
        lower = message.lower()
        if operation == "install":
            return ("The new copy was not completed. Check Error details. If a partial output "
                    "folder was created, select a different new folder before trying again.")
        if "unsupported or already modified" in lower:
            return ("Choose an unmodified Umbra " + patcher.SUPPORTED_VERSION +
                    " installation. This installer checks the exact supported executable.")
        if "already exists" in lower:
            return "The new add-on folder already exists. Choose a new, unused folder name."
        if "disjoint" in lower or "outside the add-on" in lower:
            return "Choose a separate new folder outside the original app and add-on source folder."
        if "runtime" in lower and "missing" in lower:
            return "The original folder is incomplete. Choose the complete installation, including its runtime files."
        if "sync_light.exe" in lower or "original application" in lower:
            return "Choose the original Umbra folder containing Sync_light.exe and its runtime files."
        if "linked" in lower:
            return "Choose a normal local folder. Linked files, symbolic links and junctions are not supported."
        return message if len(message) < 210 else "The selection could not be verified. Open Error details for the reason."

    def show_error(self):
        messagebox.showerror("Umbra RGB Add-on Setup", self.last_error, parent=self.root)

    def open_folder(self):
        if self.installed_destination is not None:
            try:
                os.startfile(str(self.installed_destination))
            except OSError as error:
                messagebox.showerror("Could not open folder", str(error), parent=self.root)

    def close(self):
        if self.operation == "install":
            messagebox.showinfo("Installation in progress",
                                "Please wait for installation to finish before closing this window.",
                                parent=self.root)
            return
        self.closed = True
        self.root.destroy()


def smoke_test(report_path):
    """Exercise bundled Tk/resources without opening a hub or installing files."""
    report = {"addon_version": patcher.VERSION, "hardware_accessed": False,
              "application_started": False}
    root = None
    try:
        patcher.load_bootstrap()
        report["bootstrap_valid"] = True
        report["payload_files_present"] = all(
            (patcher.ROOT / "payload" / name).is_file() for name in patcher.PAYLOAD_FILES)
        if not report["payload_files_present"]:
            raise patcher.PatchError("Bundled add-on payload is missing")
        root = tk.Tk()
        root.withdraw()
        InstallerWindow(root)
        root.update_idletasks()
        report.update({"window_created": True, "tk_version": str(root.tk.call("info", "patchlevel")),
                       "ok": True})
    except Exception as error:
        report.update({"ok": False, "error": str(error)})
    finally:
        if root is not None:
            root.destroy()
    if report_path is not None:
        Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8")
    elif sys.stdout is not None:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=patcher.VERSION)
    parser.add_argument("--source", default="", help="Prefill the original application path")
    parser.add_argument("--destination", default="", help="Prefill the new application folder")
    parser.add_argument("--smoke-test", action="store_true", help="Check bundled resources and Tk without installation")
    parser.add_argument("--report", type=Path, help="Write the smoke-test result as JSON")
    args = parser.parse_args(argv)
    if args.smoke_test:
        return smoke_test(args.report)
    root = tk.Tk()
    InstallerWindow(root, args.source, args.destination)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
