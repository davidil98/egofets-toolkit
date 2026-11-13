#!/usr/bin/env python3
"""EGOFET Toolkit desktop launcher (consumer mode).

Starts the Marimo apps as a local gallery and exports static HTML reports.
Only the Python standard library is required.

Usage:
    python consumer/launcher.py            # open the GUI
    python consumer/launcher.py --check    # validate environment + manifest
    python consumer/launcher.py --export   # generate HTML reports headlessly
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONSUMER_DIR = PROJECT_ROOT / "consumer"
MANIFEST_PATH = CONSUMER_DIR / "reports.json"
OUTPUT_DIR = PROJECT_ROOT / "output" / "reports"
DATA_DIR = PROJECT_ROOT / "data" / "raw"

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import messagebox, ttk

    TK_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the Python build
    tk = None
    tkfont = None
    messagebox = None
    ttk = None
    TK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------
def marimo_version() -> str | None:
    """Return the installed Marimo version, or None if it is not available."""
    try:
        import marimo

        return getattr(marimo, "__version__", "unknown")
    except Exception:
        return None


def python_executable() -> str:
    """Interpreter used to run Marimo.

    On Windows the launcher is started with ``pythonw.exe`` (no console), but
    Marimo runs better with ``python.exe`` so that its logs can be captured.
    """
    exe = Path(sys.executable)
    if IS_WINDOWS and exe.name.lower() == "pythonw.exe":
        candidate = exe.with_name("python.exe")
        if candidate.exists():
            return str(candidate)
    return str(exe)


def environment_summary() -> tuple[str, bool]:
    version = marimo_version()
    summary = f"Python {platform.python_version()}  ·  Marimo {version or 'not installed'}"
    if not TK_AVAILABLE:
        summary += "  ·  tkinter not available"
    return summary, version is not None and TK_AVAILABLE


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def server_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def wait_for_server(proc: subprocess.Popen, url: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 400:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def open_path(path: Path) -> None:
    path_str = str(path)
    if IS_WINDOWS:
        os.startfile(path_str)  # type: ignore[attr-defined]
    elif IS_MACOS:
        subprocess.Popen(["open", path_str])
    else:
        subprocess.Popen(["xdg-open", path_str])


def subprocess_kwargs() -> dict:
    """Options shared by every child process started by the launcher.

    On POSIX the child gets its own session so that it can be stopped (and any
    helper process it spawns) without signalling the launcher itself. The
    :func:`_send_signal` helper still verifies the group before using
    ``killpg``, so a missing session can never take down the GUI.
    """
    if IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


def _send_signal(proc: subprocess.Popen, sig: int) -> None:
    """Signal the child process, or its whole group when it owns one."""
    if IS_WINDOWS:
        if sig == signal.SIGTERM:
            proc.terminate()
        else:
            proc.kill()
        return

    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = None

    # Only use killpg when the child is the leader of a separate group.
    if pgid is not None and pgid == proc.pid and pgid != os.getpgid(0):
        try:
            os.killpg(pgid, sig)
            return
        except OSError:
            pass

    try:
        proc.send_signal(sig)
    except OSError:
        pass


def terminate_process(proc: subprocess.Popen | None, timeout: float = 5.0) -> None:
    if proc is None or proc.poll() is not None:
        return

    _send_signal(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass

    _send_signal(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass


# ---------------------------------------------------------------------------
# Manifest and report generation
# ---------------------------------------------------------------------------
def load_manifest() -> tuple[dict, list[dict], list[dict]]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    apps: list[dict] = []
    missing: list[dict] = []

    for entry in data.get("apps", []):
        raw_path = entry.get("path", "")
        path = (PROJECT_ROOT / raw_path).resolve()
        record = {**entry, "path": path}
        if path.is_file():
            apps.append(record)
        else:
            missing.append(record)

    return data, apps, missing


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "report"


def generate_html_reports(apps: list[dict], log=print) -> list[dict]:
    """Export every app to static HTML using Marimo's CLI."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    used_names: set[str] = set()

    for app in apps:
        name = app.get("name") or Path(app["path"]).stem
        base = slugify(name)
        candidate = base
        suffix = 2
        while candidate in used_names:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used_names.add(candidate)

        output_path = OUTPUT_DIR / f"{candidate}.html"
        command = [
            python_executable(),
            "-m",
            "marimo",
            "export",
            "html",
            str(app["path"]),
            "-o",
            str(output_path),
            "--no-include-code",
        ]

        log(f"Exporting {name} -> {output_path.relative_to(PROJECT_ROOT)}")
        try:
            proc = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                **subprocess_kwargs(),
            )
            ok = proc.returncode == 0
            error = "" if ok else (proc.stderr or proc.stdout or "").strip()[-1500:]
        except OSError as exc:
            ok = False
            error = str(exc)

        results.append(
            {"name": name, "path": output_path, "ok": ok, "error": error}
        )
        log("  " + ("OK" if ok else "FAILED"))

    return results


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
def ui_fonts(root) -> tuple[tuple, tuple, tuple]:
    """Return font tuples for the launcher: body, title, section heading.

    Some Tk builds (notably Tk 9.0 on Linux) report a broken default font
    (``fixed`` at a tiny size), so an explicit family is chosen when the
    platform default cannot be trusted.
    """
    family, size = "TkDefaultFont", 10
    try:
        actual = tkfont.nametofont("TkDefaultFont").actual()
        family = str(actual.get("family", family))
        size = int(actual.get("size", size))
    except Exception:
        pass

    if family.lower() == "fixed" or size < 7:
        available = {name.lower() for name in tkfont.families(root)}
        family = "TkDefaultFont"
        for candidate in (
            "Segoe UI",
            "SF Pro Text",
            "Helvetica Neue",
            "DejaVu Sans",
            "Noto Sans",
            "Liberation Sans",
            "Nimbus Sans L",
            "Helvetica",
            "Arial",
            "Verdana",
        ):
            if candidate.lower() in available:
                family = candidate
                break
        size = 10

    return (family, size), (family, size + 6, "bold"), (family, size + 1, "bold")


class LauncherApp:
    def __init__(self, root, manifest: dict, apps: list[dict], missing: list[dict]):
        self.root = root
        self.manifest = manifest
        self.apps = apps
        self.missing = missing
        self.server_proc: subprocess.Popen | None = None
        self.server_port: int | None = None
        self.busy = False
        self._queue: queue.Queue = queue.Queue()
        self._server_output: deque[str] = deque(maxlen=100)

        self._build_ui()
        self._refresh_buttons()

        for entry in missing:
            self.log(f"Missing app (ignored): {entry['path']}")

        self.root.after(100, self._poll_queue)

    # -- UI ----------------------------------------------------------------
    def _build_ui(self) -> None:
        # Layout numbers are written for a 96 DPI screen and scaled for
        # high-DPI displays, which Tk reports through winfo_fpixels.
        scale = self.root.winfo_fpixels("1i") / 96.0
        px = lambda value: int(round(value * scale))  # noqa: E731

        self.root.title(self.manifest.get("title", "EGOFET Toolkit"))
        self.root.geometry(f"{px(660)}x{px(500)}")
        self.root.minsize(px(580), px(440))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.body_font, self.title_font, self.heading_font = ui_fonts(self.root)
        style.configure(".", font=self.body_font)
        style.configure("TLabelframe.Label", font=self.heading_font)

        outer = ttk.Frame(self.root, padding=px(16))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(
            header,
            text=self.manifest.get("title", "EGOFET Toolkit"),
            font=self.title_font,
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Open the analysis reports or generate a static HTML copy.",
            foreground="#555555",
        ).pack(anchor="w", pady=(px(2), px(12)))

        environment = ttk.LabelFrame(outer, text="Environment", padding=px(8))
        environment.pack(fill="x", pady=(0, px(12)))

        summary, ready = environment_summary()
        self.environment_var = tk.StringVar(value=summary)
        environment_label = ttk.Label(environment, textvariable=self.environment_var)
        environment_label.pack(anchor="w")
        if not ready:
            environment_label.configure(foreground="#a40000")

        self.activity_var = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=self.activity_var, foreground="#333333").pack(
            anchor="w", pady=(0, px(8))
        )

        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        gap = px(6)
        row_gap = px(3)
        buttons = [
            ("Open reports", self.open_reports, 0, 0),
            ("Generate HTML reports", self.start_export, 0, 1),
            ("Open data folder", self.open_data_folder, 1, 0),
            ("Open reports folder", self.open_reports_folder, 1, 1),
            ("Stop server", self.stop_server, 2, 0),
            ("Quit", self._on_close, 2, 1),
        ]

        self.action_buttons: list[ttk.Button] = []
        for text, command, row, column in buttons:
            button = ttk.Button(actions, text=text, command=command)
            button.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0, gap) if column == 0 else (gap, 0),
                pady=row_gap,
            )
            self.action_buttons.append(button)

        (
            self.open_btn,
            self.export_btn,
            self.data_btn,
            self.reports_btn,
            self.stop_btn,
            self.quit_btn,
        ) = self.action_buttons

        log_frame = ttk.LabelFrame(outer, text="Activity", padding=px(6))
        log_frame.pack(fill="both", expand=True, pady=(px(12), 0))

        self.log_text = tk.Text(
            log_frame,
            height=8,
            wrap="word",
            state="disabled",
            relief="flat",
            background="#f7f7f7",
            font=self.body_font,
        )
        scrollbar = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(
            outer,
            text="Reports are served only on this computer (127.0.0.1).",
            foreground="#777777",
        ).pack(anchor="w", pady=(px(8), 0))

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _post(self, kind: str, payload=None) -> None:
        self._queue.put((kind, payload))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "server_ready":
                    self._on_server_ready(*payload)
                elif kind == "export_done":
                    self._on_export_done(payload)
                elif kind == "error":
                    messagebox.showerror("EGOFET Toolkit", payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self.busy = busy
        if message is not None:
            self.activity_var.set(message)
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        running = self.server_proc is not None and self.server_proc.poll() is None
        normal = ["disabled"] if self.busy else ["!disabled"]

        self.open_btn.state(normal)
        self.export_btn.state(normal)
        self.data_btn.state(normal)
        self.reports_btn.state(normal)
        self.quit_btn.state(["!disabled"])

        if running and not self.busy:
            self.stop_btn.state(["!disabled"])
        else:
            self.stop_btn.state(["disabled"])

    # -- Server ------------------------------------------------------------
    def open_reports(self) -> None:
        if self.busy:
            return

        if self.server_proc is not None and self.server_proc.poll() is None:
            webbrowser.open(server_url(self.server_port))
            return

        if self.server_proc is not None:
            self.server_proc = None
            self.server_port = None

        if not self.apps:
            messagebox.showerror(
                "No reports", "No valid report apps were found in the manifest."
            )
            return
        if marimo_version() is None:
            messagebox.showerror(
                "Marimo not found",
                "Marimo is not installed in this Python environment.\n"
                "Ask the toolkit maintainer to update the environment.",
            )
            return

        port = find_free_port()
        command = [
            python_executable(),
            "-m",
            "marimo",
            "run",
            *[str(app["path"]) for app in self.apps],
            "--headless",
            "--no-token",
            "--port",
            str(port),
        ]

        self._set_busy(True, "Starting the report gallery...")
        self.log("Starting the Marimo gallery...")

        try:
            proc = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                **subprocess_kwargs(),
            )
        except OSError as exc:
            self._set_busy(False, "Could not start the server.")
            self.log(f"Failed to start Marimo: {exc}")
            messagebox.showerror("Could not start reports", str(exc))
            return

        self.server_proc = proc
        self.server_port = port
        self._refresh_buttons()

        threading.Thread(
            target=self._read_server_output, args=(proc,), daemon=True
        ).start()
        threading.Thread(
            target=self._wait_server, args=(proc, port), daemon=True
        ).start()

    def _read_server_output(self, proc: subprocess.Popen) -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            text = line.rstrip()
            if text:
                self._server_output.append(text)
                self._post("log", text)

    def _wait_server(self, proc: subprocess.Popen, port: int) -> None:
        ok = wait_for_server(proc, server_url(port))
        self._post("server_ready", (ok, port))

    def _on_server_ready(self, ok: bool, port: int) -> None:
        self._set_busy(False, "Ready.")
        if ok:
            url = server_url(port)
            self.log(f"Report gallery ready: {url}")
            webbrowser.open(url)
        else:
            self.log("The report server did not start.")
            recent = "\n".join(list(self._server_output)[-12:])
            self.stop_server()
            messagebox.showerror(
                "Could not start reports",
                "Marimo did not start correctly.\n\n" + recent,
            )

    def stop_server(self) -> None:
        proc = self.server_proc
        self.server_proc = None
        self.server_port = None
        if proc is not None:
            terminate_process(proc)
            self.log("Report server stopped.")
        self._refresh_buttons()

    # -- Export ------------------------------------------------------------
    def start_export(self) -> None:
        if self.busy:
            return
        if not self.apps:
            messagebox.showerror(
                "No reports", "No valid report apps were found in the manifest."
            )
            return
        if marimo_version() is None:
            messagebox.showerror(
                "Marimo not found",
                "Marimo is not installed in this Python environment.",
            )
            return

        self._set_busy(True, "Generating HTML reports...")
        self.log("Generating static HTML with the default widget values...")
        apps = list(self.apps)
        threading.Thread(
            target=self._export_worker, args=(apps,), daemon=True
        ).start()

    def _export_worker(self, apps: list[dict]) -> None:
        results = generate_html_reports(
            apps, log=lambda message: self._post("log", message)
        )
        self._post("export_done", results)

    def _on_export_done(self, results: list[dict]) -> None:
        self._set_busy(False, "Ready.")
        ok = [item for item in results if item["ok"]]
        failed = [item for item in results if not item["ok"]]
        folder = OUTPUT_DIR.relative_to(PROJECT_ROOT)
        self.log(f"Finished: {len(ok)}/{len(results)} reports in {folder}")

        if failed:
            detail = "\n\n".join(
                f"{item['name']}: {item['error']}" for item in failed
            )
            messagebox.showwarning(
                "Some reports failed",
                f"{len(ok)} of {len(results)} reports were generated.\n\n"
                + detail[:1500],
            )
        else:
            messagebox.showinfo(
                "Reports generated",
                f"{len(ok)} report(s) saved to:\n{OUTPUT_DIR}",
            )

    # -- Folders -----------------------------------------------------------
    def open_data_folder(self) -> None:
        if DATA_DIR.is_dir():
            open_path(DATA_DIR)
        else:
            messagebox.showerror(
                "Data folder not found", f"Expected folder:\n{DATA_DIR}"
            )

    def open_reports_folder(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        open_path(OUTPUT_DIR)

    # -- Lifecycle ---------------------------------------------------------
    def _on_close(self) -> None:
        self.stop_server()
        self.root.destroy()


def run_gui(manifest: dict, apps: list[dict], missing: list[dict]) -> int:
    if not TK_AVAILABLE:
        print(
            "error: tkinter is not available in this Python build.\n"
            "Install a Python distribution with Tk support (conda-forge "
            "python includes it).",
            file=sys.stderr,
        )
        return 1

    root = tk.Tk()
    app = LauncherApp(root, manifest, apps, missing)

    def shutdown(signum, frame) -> None:
        # The queue poll keeps the interpreter responsive, so this runs shortly
        # after SIGINT/SIGTERM (e.g. on logout) and the Marimo child is stopped.
        try:
            app.stop_server()
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    for signal_name in ("SIGINT", "SIGTERM", "SIGHUP"):
        sig = getattr(signal, signal_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, shutdown)
        except (OSError, ValueError):
            pass

    root.mainloop()
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def check_environment(manifest: dict, apps: list[dict], missing: list[dict]) -> int:
    summary, ready = environment_summary()
    print(f"Project:  {PROJECT_ROOT}")
    print(f"Python:   {sys.executable}")
    print(f"Runtime:  {summary}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Apps:     {len(apps)}")

    for app in apps:
        print(f"  OK      {app['name']} -> {app['path']}")
    for app in missing:
        print(f"  MISSING {app['name']} -> {app['path']}", file=sys.stderr)

    if not apps:
        print("error: no valid apps in the manifest", file=sys.stderr)
        return 1
    if missing:
        print("error: some manifest entries point to missing files", file=sys.stderr)
        return 1
    if not ready:
        print("error: the runtime is incomplete", file=sys.stderr)
        return 1

    print("OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="EGOFET Toolkit desktop launcher (consumer mode)."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the environment and the report manifest, then exit",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="generate the static HTML reports without opening the GUI",
    )
    args = parser.parse_args(argv)

    try:
        manifest, apps, missing = load_manifest()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        return check_environment(manifest, apps, missing)

    if args.export:
        if not apps:
            print("error: no valid apps in the manifest", file=sys.stderr)
            return 1
        results = generate_html_reports(apps)
        return 0 if all(item["ok"] for item in results) else 1

    return run_gui(manifest, apps, missing)


if __name__ == "__main__":
    raise SystemExit(main())
