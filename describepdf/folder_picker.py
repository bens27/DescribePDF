"""
Native folder picker dialogs for the batch conversion UI.

The dialog opens on the machine running the server; for the packaged desktop
app that is the user's own machine, which is the intended use. Subprocess
dialogs are used instead of a GUI toolkit so they work from Gradio's worker
threads on every platform.
"""

import logging
import queue
import subprocess
import sys
from typing import Optional

logger = logging.getLogger('describepdf')

# Upper bound on how long a dialog may stay open before the UI request is
# released; prevents a dialog that failed to appear from wedging the UI.
DIALOG_TIMEOUT_S = 300


def _cocoa_loop_running() -> bool:
    """Whether a Cocoa event loop is running (true in the packaged mac app)."""
    try:
        from AppKit import NSApp
        return NSApp is not None and bool(NSApp.isRunning())
    except Exception:
        return False


def _pick_folder_nsopenpanel(title: str) -> Optional[str]:
    """
    Show NSOpenPanel via the running Cocoa main loop.

    Called from a Gradio worker thread; the panel itself must run on the main
    thread, so it is scheduled with callAfter and the result is passed back
    through a queue. Unlike the osascript dialog, NSOpenPanel can force
    itself in front of the browser window.
    """
    from AppKit import NSApp, NSOpenPanel, NSModalResponseOK
    from PyObjCTools import AppHelper

    result_queue: "queue.Queue[Optional[str]]" = queue.Queue()

    def show_panel() -> None:
        try:
            NSApp.activateIgnoringOtherApps_(True)
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseDirectories_(True)
            panel.setCanChooseFiles_(False)
            panel.setAllowsMultipleSelection_(False)
            panel.setCanCreateDirectories_(True)
            panel.setMessage_(title)
            response = panel.runModal()
            if response == NSModalResponseOK and panel.URLs():
                result_queue.put(str(panel.URLs()[0].path()))
            else:
                result_queue.put(None)
        except Exception as e:
            logger.error(f"NSOpenPanel failed: {e}")
            result_queue.put(None)

    AppHelper.callAfter(show_panel)
    try:
        return result_queue.get(timeout=DIALOG_TIMEOUT_S)
    except queue.Empty:
        logger.warning("Folder dialog timed out without a selection.")
        return None


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
            if _cocoa_loop_running():
                return _pick_folder_nsopenpanel(title)
            script = f'POSIX path of (choose folder with prompt "{title}")'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=DIALOG_TIMEOUT_S
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
                capture_output=True, text=True, timeout=DIALOG_TIMEOUT_S
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None

        result = subprocess.run(
            ["zenity", "--file-selection", "--directory", "--title", title],
            capture_output=True, text=True, timeout=DIALOG_TIMEOUT_S
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    except FileNotFoundError:
        logger.warning("No folder picker available on this platform; enter the path manually.")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("Folder dialog timed out without a selection.")
        return None
    except Exception as e:
        logger.error(f"Folder picker failed: {e}")
        return None
