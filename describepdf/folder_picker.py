"""
Native folder picker dialogs for the batch conversion UI.

The dialog opens on the machine running the server; for the packaged desktop
app that is the user's own machine, which is the intended use. Subprocess
dialogs are used instead of a GUI toolkit so they work from Gradio's worker
threads on every platform.
"""

import logging
import subprocess
import sys
from typing import Optional

logger = logging.getLogger('describepdf')


def pick_folder(title: str = "Choose a folder") -> Optional[str]:
    """
    Open a native folder picker and return the chosen path.

    Args:
        title: Prompt text shown in the dialog

    Returns:
        Optional[str]: The selected folder path, or None if the dialog was
        cancelled or no picker is available on this platform
    """
    try:
        if sys.platform == "darwin":
            script = f'POSIX path of (choose folder with prompt "{title}")'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None

        if sys.platform == "win32":
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$owner = New-Object System.Windows.Forms.Form; "
                "$owner.TopMost = $true; "
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
                f"$dialog.Description = '{title}'; "
                "if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) "
                "{ Write-Output $dialog.SelectedPath }"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None

        result = subprocess.run(
            ["zenity", "--file-selection", "--directory", "--title", title],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    except FileNotFoundError:
        logger.warning("No folder picker available on this platform; enter the path manually.")
        return None
    except Exception as e:
        logger.error(f"Folder picker failed: {e}")
        return None
