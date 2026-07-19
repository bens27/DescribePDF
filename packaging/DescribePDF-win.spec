# PyInstaller spec for the Windows DescribePDF build.
# Build from the repo root on a Windows machine:
#   python -m PyInstaller packaging\DescribePDF-win.spec --noconfirm

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("../prompts", "prompts"),
    ("../assets/logo-square.png", "assets"),
]
datas += collect_data_files("gradio")
datas += collect_data_files("gradio_client")
datas += collect_data_files("safehttpx")
datas += collect_data_files("groovy")

hiddenimports = collect_submodules("markitdown")

a = Analysis(
    ["app_launcher.py"],
    pathex=[".."],
    datas=datas,
    hiddenimports=hiddenimports,
    # Gradio resolves routes via source inspection, which fails on
    # bytecode-only collection.
    module_collection_mode={"gradio": "py"},
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DescribePDF",
    icon="icon.ico",
    # Console stays visible: it shows server status and closing it quits.
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="DescribePDF",
)
