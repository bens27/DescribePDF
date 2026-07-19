@echo off
REM Build DescribePDF.exe on Windows. Run from the repository root:
REM   packaging\build-windows.bat
REM Requires Python 3.13 (https://www.python.org/downloads/) on PATH as "py".

setlocal
cd /d "%~dp0\.."

py -3.13 -m venv .venv-build || goto :error
.venv-build\Scripts\python -m pip install --upgrade pip || goto :error
.venv-build\Scripts\python -m pip install -r requirements.txt pyinstaller || goto :error
.venv-build\Scripts\python -m PyInstaller packaging\DescribePDF-win.spec --noconfirm --distpath dist --workpath build || goto :error

echo.
echo Build complete: dist\DescribePDF\DescribePDF.exe
goto :eof

:error
echo Build failed. See output above.
exit /b 1
