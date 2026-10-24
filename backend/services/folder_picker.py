"""Native Windows folder picker service executed via isolated subprocess.

Prevents GUI event loop deadlocks by running the Windows folder dialog
in a dedicated, non-blocking subprocess with guaranteed timeout cleanup.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import platform
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("repomind.folder_picker")

# Default timeout in seconds for user to pick a folder
DEFAULT_PICKER_TIMEOUT_SECONDS = 120.0


def _build_powershell_script(initial_dir: str | None = None) -> str:
    """Build PowerShell script using System.Windows.Forms.FolderBrowserDialog with active topmost owner."""
    script_lines = [
        "Add-Type -AssemblyName System.Windows.Forms",
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog",
        "$dialog.Description = 'Select Repository Folder'",
        "$dialog.ShowNewFolderButton = $true",
    ]

    if initial_dir and "\0" not in initial_dir:
        try:
            init_p = Path(initial_dir.strip()).resolve()
            if init_p.is_dir():
                escaped = str(init_p).replace("'", "''")
                script_lines.append(f"$dialog.SelectedPath = '{escaped}'")
        except Exception:
            pass

    script_lines.extend([
        "$form = New-Object System.Windows.Forms.Form",
        "$form.Opacity = 0",
        "$form.ShowInTaskbar = $false",
        "$form.Size = New-Object System.Drawing.Size(1, 1)",
        "$form.StartPosition = 'Manual'",
        "$form.Location = New-Object System.Drawing.Point(-2000, -2000)",
        "$form.TopMost = $true",
        "$form.Show()",
        "$form.Activate()",
        "$form.BringToFront()",
        "$res = $dialog.ShowDialog($form)",
        "$form.Dispose()",
        "if ($res -eq [System.Windows.Forms.DialogResult]::OK) {",
        "    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
        "    [Console]::WriteLine($dialog.SelectedPath)",
        "}",
    ])

    return "\r\n".join(script_lines)


def _build_python_script(initial_dir: str | None = None) -> str:
    """Build standalone Python script for Tkinter folder dialog with topmost foreground owner."""
    resolved_init = "None"
    if initial_dir and "\0" not in initial_dir:
        try:
            init_p = Path(initial_dir.strip()).resolve()
            if init_p.is_dir():
                resolved_init = repr(str(init_p))
        except Exception:
            pass

    return (
        "import sys\n"
        "try:\n"
        "    import tkinter as tk\n"
        "    from tkinter import filedialog\n"
        "    root = tk.Tk()\n"
        "    root.overrideredirect(True)\n"
        "    root.geometry('0x0+0+0')\n"
        "    root.attributes('-topmost', True)\n"
        "    root.lift()\n"
        "    root.focus_force()\n"
        f"    init_dir = {resolved_init}\n"
        "    p = filedialog.askdirectory(title='Select Repository Folder', initialdir=init_dir, parent=root)\n"
        "    root.destroy()\n"
        "    if p:\n"
        "        sys.stdout.buffer.write(p.encode('utf-8'))\n"
        "except Exception as e:\n"
        "    sys.stderr.buffer.write(str(e).encode('utf-8'))\n"
        "    sys.exit(1)\n"
    )


async def pick_folder_native(
    initial_dir: str | None = None,
    timeout_seconds: float = DEFAULT_PICKER_TIMEOUT_SECONDS,
) -> tuple[str, str | None, str | None]:
    """Execute native folder picker in an isolated subprocess.

    Attempts the primary standalone Python Tkinter subprocess first
    (which guarantees STA thread, topmost focus, and modern Explorer picker).
    Falls back to PowerShell on Windows if Python Tkinter fails.

    Returns:
        tuple of (status, path, error):
        - ("selected", absolute_path_str, None)
        - ("cancelled", None, error_message_or_None)
        - ("error", None, error_message)
    """
    # 1. Primary: Run Tkinter in a standalone Python subprocess
    status, path, error = await _pick_folder_python_subprocess(initial_dir, timeout_seconds)
    if status in ("selected", "cancelled"):
        return status, path, error

    # 2. If python subprocess failed with an error, attempt PowerShell on Windows as fallback
    is_windows = platform.system() == "Windows"
    powershell_bin = shutil.which("powershell.exe") or shutil.which("powershell")

    if is_windows and powershell_bin:
        logger.info("Falling back to PowerShell folder picker: %s", error)
        return await _pick_folder_powershell(powershell_bin, initial_dir, timeout_seconds)

    return status, path, error


async def _pick_folder_powershell(
    powershell_bin: str,
    initial_dir: str | None,
    timeout_seconds: float,
) -> tuple[str, str | None, str | None]:
    """Run native Windows folder dialog via PowerShell."""
    script = _build_powershell_script(initial_dir)
    encoded_cmd = base64.b64encode(script.encode("utf-16le")).decode("ascii")

    cmd = [
        powershell_bin,
        "-NoProfile",
        "-STA",
        "-EncodedCommand",
        encoded_cmd,
    ]

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        logger.warning("Folder picker dialog timed out after %.1f seconds", timeout_seconds)
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        return ("cancelled", None, f"Folder selection timed out after {int(timeout_seconds)} seconds")
    except Exception as exc:
        logger.error("Failed to spawn folder picker subprocess: %s", exc)
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        return ("error", None, f"Failed to launch folder picker: {exc}")

    if proc.returncode != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
        logger.error("Folder picker process exited with code %d: %s", proc.returncode, err_msg)
        return ("error", None, err_msg or f"Folder picker exited with code {proc.returncode}")

    selected = stdout_bytes.decode("utf-8", errors="replace").strip()
    if not selected:
        # User clicked Cancel or closed the dialog
        return ("cancelled", None, None)

    try:
        resolved = Path(selected).resolve()
        if not resolved.is_dir():
            return ("error", None, f"Selected path is not a directory: '{resolved}'")
        return ("selected", str(resolved), None)
    except Exception as e:
        return ("error", None, f"Invalid directory path: {e}")


async def _pick_folder_python_subprocess(
    initial_dir: str | None,
    timeout_seconds: float,
) -> tuple[str, str | None, str | None]:
    """Run native folder picker using a separate Python subprocess running Tkinter on its main thread."""
    py_code = _build_python_script(initial_dir)
    cmd = [sys.executable, "-c", py_code]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        logger.warning("Folder picker timed out after %.1f seconds", timeout_seconds)
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        return ("cancelled", None, f"Folder selection timed out after {int(timeout_seconds)} seconds")
    except Exception as exc:
        logger.error("Failed to spawn folder picker subprocess: %s", exc)
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        return ("error", None, f"Failed to launch folder picker: {exc}")

    if proc.returncode != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
        logger.warning("Python folder picker process exited with code %d: %s", proc.returncode, err_msg)
        return ("error", None, err_msg or f"Picker subprocess failed with code {proc.returncode}")

    selected = stdout_bytes.decode("utf-8", errors="replace").strip()
    if not selected:
        # Cancelled or closed
        return ("cancelled", None, None)

    try:
        resolved = Path(selected).resolve()
        if not resolved.is_dir():
            return ("error", None, f"Selected path is not a directory: '{resolved}'")
        return ("selected", str(resolved), None)
    except Exception as e:
        return ("error", None, f"Invalid directory path: {e}")
