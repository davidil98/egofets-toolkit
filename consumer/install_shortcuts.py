#!/usr/bin/env python3
"""Create desktop and start-menu shortcuts for the EGOFET Toolkit launcher.

Run this once with the Python interpreter of the environment that will power
the consumer launcher::

    .venv/bin/python consumer/install_shortcuts.py
    # or
    conda run -n egofets python consumer/install_shortcuts.py

Consumers then only need to double-click "EGOFET Toolkit".
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONSUMER_DIR = Path(__file__).resolve().parent
LAUNCHER = CONSUMER_DIR / "launcher.py"
MANIFEST = CONSUMER_DIR / "reports.json"

SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_LINUX = SYSTEM == "Linux"
IS_MACOS = SYSTEM == "Darwin"

APP_NAME = "EGOFET Toolkit"


def launcher_python() -> Path:
    """Interpreter used to start the GUI (pythonw on Windows: no console)."""
    exe = Path(sys.executable)
    if IS_WINDOWS:
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return exe


def check_runtime() -> tuple[str | None, str | None]:
    python = Path(sys.executable)
    if IS_WINDOWS and python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")
    code = "import marimo, tkinter; print(marimo.__version__)"
    result = subprocess.run(
        [str(python), "-c", code],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()
    return result.stdout.strip(), None


def ps_quote(value: str) -> str:
    """Single-quoted PowerShell string."""
    return "'" + value.replace("'", "''") + "'"


def linux_desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Open EGOFET analysis reports\n"
        f'Exec="{sys.executable}" "{LAUNCHER}"\n'
        f"Path={PROJECT_ROOT}\n"
        "Terminal=false\n"
        "Categories=Science;Education;\n"
        "StartupNotify=true\n"
    )


def install_linux(dry_run: bool, include_desktop: bool) -> list[Path]:
    applications = Path.home() / ".local" / "share" / "applications"
    entry_path = applications / "egofet-toolkit.desktop"
    content = linux_desktop_entry()
    created: list[Path] = []

    if dry_run:
        print(f"[dry-run] Would write {entry_path}:")
        print(content)
    else:
        applications.mkdir(parents=True, exist_ok=True)
        entry_path.write_text(content, encoding="utf-8")
        entry_path.chmod(0o755)
        created.append(entry_path)

    if include_desktop:
        desktop_dir = Path.home() / "Desktop"
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DESKTOP"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                desktop_dir = Path(result.stdout.strip())
        except FileNotFoundError:
            pass

        if desktop_dir.is_dir():
            desktop_entry = desktop_dir / "egofet-toolkit.desktop"
            if dry_run:
                print(f"[dry-run] Would copy the shortcut to {desktop_entry}")
            else:
                shutil.copy2(entry_path, desktop_entry)
                desktop_entry.chmod(0o755)
                created.append(desktop_entry)
                try:
                    subprocess.run(
                        [
                            "gio",
                            "set",
                            str(desktop_entry),
                            "metadata::trusted",
                            "true",
                        ],
                        capture_output=True,
                        check=False,
                    )
                except FileNotFoundError:
                    pass
        elif not dry_run:
            print(f"Note: desktop folder not found ({desktop_dir}); skipping.")

    if not dry_run and shutil.which("update-desktop-database"):
        subprocess.run(
            ["update-desktop-database", str(applications)],
            capture_output=True,
            check=False,
        )

    return created


def windows_shortcut_script(include_desktop: bool) -> str:
    target = launcher_python()
    arguments = f'"{LAUNCHER}"'
    icon = target

    targets: list[str] = []
    if include_desktop:
        targets.append("$desktop")
    targets.append("$programs")

    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$desktop = [Environment]::GetFolderPath('Desktop')",
        "$programs = [Environment]::GetFolderPath('Programs')",
        "foreach ($dir in @(" + ", ".join(targets) + ")) {",
        "    if (-not $dir) { continue }",
        f"    $lnk = Join-Path $dir {ps_quote(APP_NAME + '.lnk')}",
        "    $shell = New-Object -ComObject WScript.Shell",
        "    $shortcut = $shell.CreateShortcut($lnk)",
        f"    $shortcut.TargetPath = {ps_quote(str(target))}",
        f"    $shortcut.Arguments = {ps_quote(arguments)}",
        f"    $shortcut.WorkingDirectory = {ps_quote(str(PROJECT_ROOT))}",
        f"    $shortcut.IconLocation = {ps_quote(str(icon))}",
        f"    $shortcut.Description = {ps_quote(APP_NAME)}",
        "    $shortcut.Save()",
        "    Write-Output $lnk",
        "}",
    ]
    return "\n".join(lines) + "\n"


def install_windows(dry_run: bool, include_desktop: bool) -> list[Path]:
    script = windows_shortcut_script(include_desktop)

    if dry_run:
        print("[dry-run] Would run this PowerShell script:")
        print(script)
        return []

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return _install_windows_batch_fallback(include_desktop)

    with tempfile.NamedTemporaryFile(
        "w", suffix=".ps1", delete=False, encoding="utf-8-sig"
    ) as handle:
        handle.write(script)
        script_path = Path(handle.name)

    try:
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            capture_output=True,
            text=True,
        )
    finally:
        script_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print("PowerShell could not create the shortcut; using a .bat fallback.")
        print((result.stderr or result.stdout).strip())
        return _install_windows_batch_fallback(include_desktop)

    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def _install_windows_batch_fallback(include_desktop: bool) -> list[Path]:
    desktop = Path.home() / "Desktop"
    if not include_desktop or not desktop.is_dir():
        return []

    batch = desktop / f"{APP_NAME}.bat"
    content = (
        "@echo off\n"
        f'start "" "{launcher_python()}" "{LAUNCHER}"\n'
    )
    batch.write_text(content, encoding="utf-8")
    return [batch]


def install_macos(dry_run: bool, include_desktop: bool) -> list[Path]:
    if not include_desktop:
        return []

    desktop = Path.home() / "Desktop"
    command_path = desktop / f"{APP_NAME}.command"
    content = (
        "#!/bin/sh\n"
        f'cd "{PROJECT_ROOT}" || exit 1\n'
        f'exec "{sys.executable}" "{LAUNCHER}"\n'
    )

    if dry_run:
        print(f"[dry-run] Would write {command_path}:")
        print(content)
        return []

    if not desktop.is_dir():
        print(f"Note: desktop folder not found ({desktop}); skipping.")
        return []

    command_path.write_text(content, encoding="utf-8")
    command_path.chmod(0o755)
    return [command_path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create desktop shortcuts for the EGOFET Toolkit."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be created without writing anything",
    )
    parser.add_argument(
        "--no-desktop",
        action="store_true",
        help="do not copy the shortcut to the desktop",
    )
    args = parser.parse_args(argv)

    if not LAUNCHER.is_file():
        print(f"error: launcher not found: {LAUNCHER}", file=sys.stderr)
        return 1
    if not MANIFEST.is_file():
        print(f"error: manifest not found: {MANIFEST}", file=sys.stderr)
        return 1

    version, error = check_runtime()
    if error:
        print(
            "error: this interpreter cannot run the launcher.\n"
            f"  Interpreter: {launcher_python()}\n"
            f"  Details: {error}\n\n"
            "Use the toolkit environment instead:\n"
            "  uv sync && .venv/bin/python consumer/install_shortcuts.py\n"
            "  conda env update -f environment.yml\n"
            "  conda run -n egofets python consumer/install_shortcuts.py",
            file=sys.stderr,
        )
        return 1

    print(f"Python:  {launcher_python()}")
    print(f"Marimo:  {version}")
    print(f"Project: {PROJECT_ROOT}")

    include_desktop = not args.no_desktop
    if IS_LINUX:
        created = install_linux(args.dry_run, include_desktop)
    elif IS_WINDOWS:
        created = install_windows(args.dry_run, include_desktop)
    elif IS_MACOS:
        created = install_macos(args.dry_run, include_desktop)
    else:
        print(f"error: unsupported operating system: {SYSTEM}", file=sys.stderr)
        return 1

    if created:
        print("\nCreated:")
        for path in created:
            print(f"  {path}")
        if IS_LINUX:
            print(
                "\nIf the desktop icon is not clickable, right-click it and "
                "choose 'Allow launching' (GNOME)."
            )
    elif not args.dry_run:
        print("\nNo shortcuts were created.")

    print(f'\nDouble-click "{APP_NAME}" to start the toolkit.')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
