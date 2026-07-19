# Packaging DescribePDF as a desktop app

The desktop builds wrap the Gradio web UI (OpenRouter) in a standalone
executable: launching it starts a local server and opens the UI in the
default browser. No Python installation is needed on the target machine.

PyInstaller cannot cross-compile, so each platform's build must run on that
platform.

## Windows (standard: GitHub Actions)

The standard Windows build runs in CI — no Windows machine needed:

1. Trigger the **Build Windows app** workflow
   (`.github/workflows/build-windows.yml`) from the Actions tab, with
   `gh workflow run build-windows.yml --ref <branch>`, or by pushing a
   `v*` tag.
2. The workflow builds the exe on a `windows-latest` runner, then
   smoke-tests it: launches the built app, waits for the UI to serve, and
   verifies the expected tabs before uploading. A green run is a
   launch-tested app.
3. Download the `DescribePDF-windows` artifact from the run page (or
   `gh run download <run-id> --name DescribePDF-windows`). Ship the whole
   folder; the user runs `DescribePDF.exe` inside it (a shortcut is fine).

### Windows (fallback: local build)

On a Windows PC with [Python 3.13](https://www.python.org/downloads/)
installed ("Add python.exe to PATH" checked during install): get this
repository onto the PC, open Command Prompt in the repository root, and run
`packaging\build-windows.bat`. The app lands in `dist\DescribePDF\`.

Notes for the PC user:

- The console window that opens with the app shows server status; closing
  it quits DescribePDF.
- Windows SmartScreen may warn on first run of an unsigned exe — choose
  "More info" → "Run anyway", or sign the exe with a code-signing
  certificate for wider distribution.
- User data (optional `.env` with `OPENROUTER_API_KEY`, saved prompt
  defaults, Future Ideas notes) lives in `%APPDATA%\DescribePDF`.

## macOS

With Python 3.13 available (e.g. `uv venv --python 3.13 .venv-build`):

```sh
uv pip install --python .venv-build/bin/python -r requirements.txt pyinstaller pyobjc-framework-Cocoa
.venv-build/bin/python -m PyInstaller packaging/DescribePDF.spec --noconfirm
```

The bundle lands in `dist/DescribePDF.app`. User data lives in
`~/Library/Application Support/DescribePDF`.

## Files

- `app_launcher.py` — shared entry point (platform-aware: Cocoa shell on
  macOS, console server on Windows)
- `DescribePDF.spec` — macOS build (produces the .app bundle)
- `DescribePDF-win.spec` — Windows build (produces DescribePDF.exe)
- `build-windows.bat` — one-shot Windows build script
- `icon.icns` / `icon.ico` — app icons generated from `assets/logo-square.png`
