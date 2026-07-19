"""
Entry point for the frozen desktop app (macOS .app bundle / Windows .exe).

Launches the DescribePDF Gradio web UI (OpenRouter) and opens it in the
default browser.

macOS: a minimal Cocoa application runs on the main thread so the bundle
behaves like a normal Dock app (icon settles, Quit works) while the server
runs in a background thread.

Windows: the server runs in the console process; closing the console window
quits the app.

Configuration can be provided via a .env file in the per-user data folder
(~/Library/Application Support/DescribePDF on macOS, %APPDATA%\\DescribePDF
on Windows), since a packaged app does not run from the project directory.
Saved prompt defaults live in the same folder.
"""

import multiprocessing
import os
import sys
import threading
import webbrowser
from pathlib import Path

SERVER_URL = "http://127.0.0.1:7860/"


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "DescribePDF"
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        base = Path(appdata) if appdata else Path.home()
        return base / "DescribePDF"
    return Path.home() / ".describepdf"


def prepare_environment() -> None:
    app_data = user_data_dir()
    app_data.mkdir(parents=True, exist_ok=True)

    env_file = app_data / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)

    # A packaged app may launch with an unwritable cwd (e.g. "/" on macOS);
    # relative paths (Gradio temp files, logs) need a writable home.
    os.chdir(app_data)

    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    # Saved prompt defaults and other user data live next to the .env.
    os.environ.setdefault("DESCRIBEPDF_USER_DIR", str(app_data))


def start_server() -> None:
    from describepdf import ui

    app = ui.create_ui()
    app.launch(inbrowser=True, show_error=True)


def run_cocoa_app() -> None:
    from AppKit import NSApp, NSApplication, NSMenu, NSMenuItem
    from Foundation import NSObject
    from PyObjCTools import AppHelper

    class AppDelegate(NSObject):
        def applicationSupportsSecureRestorableState_(self, app):
            return True

        def applicationShouldHandleReopen_hasVisibleWindows_(self, app, has_windows):
            # Clicking the Dock icon brings the UI back up in the browser.
            webbrowser.open(SERVER_URL)
            return False

    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    # Minimal menu bar so Cmd-Q and the app menu behave like a normal app.
    menubar = NSMenu.alloc().init()
    app_menu_item = NSMenuItem.alloc().init()
    menubar.addItem_(app_menu_item)
    app_menu = NSMenu.alloc().init()
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit DescribePDF", "terminate:", "q"
    )
    app_menu.addItem_(quit_item)
    app_menu_item.setSubmenu_(app_menu)
    app.setMainMenu_(menubar)

    AppHelper.runEventLoop()


def main() -> None:
    prepare_environment()
    if sys.platform == "darwin":
        threading.Thread(target=start_server, daemon=True).start()
        run_cocoa_app()
    else:
        print("DescribePDF is starting; your browser will open shortly.")
        print("Keep this window open while using the app - closing it quits DescribePDF.")
        start_server()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
