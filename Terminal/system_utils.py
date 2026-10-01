"""System utility helpers for launching external desktop applications.

Provides cross-platform non-blocking launchers to open files, figures, spreadsheets,
and directories in the operating system's default applications (e.g. image viewers,
file managers, text editors).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def open_path_in_system(path: Path) -> tuple[bool, str]:
    """Launch the operating system default application to open a file or directory.

    Non-blocking execution using desktop environment handlers:
    - Linux: ``xdg-open``
    - macOS: ``open``
    - Windows: ``os.startfile`` or ``cmd /c start``

    Args:
        path: Path to the target file or directory.

    Returns:
        Tuple of ``(success, status_message)``.
    """
    resolved = path.resolve()
    if not resolved.exists():
        return False, f"Target path does not exist: {resolved.name}"

    try:
        if sys.platform.startswith("linux"):
            if not shutil.which("xdg-open"):
                return False, "External launcher unavailable: 'xdg-open' not found"
            subprocess.Popen(
                ["xdg-open", str(resolved)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, f"Opened {resolved.name} in system viewer"

        if sys.platform == "darwin":
            subprocess.Popen(
                ["open", str(resolved)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, f"Opened {resolved.name} in system viewer"

        if sys.platform == "win32":
            if hasattr(os, "startfile"):
                os.startfile(str(resolved))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", str(resolved)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                )
            return True, f"Opened {resolved.name} in system viewer"

        return False, f"Unsupported operating system: {sys.platform}"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Failed to open {resolved.name}: {exc}"


def open_folder_in_system(path: Path) -> tuple[bool, str]:
    """Open the containing directory of a file or folder in the system file manager.

    Args:
        path: File or directory path.

    Returns:
        Tuple of ``(success, status_message)``.
    """
    target_dir = path if path.is_dir() else path.parent
    return open_path_in_system(target_dir)
