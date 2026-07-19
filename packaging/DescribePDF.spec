# PyInstaller spec for the macOS DescribePDF.app bundle.
# Build from the repo root:  pyinstaller packaging/DescribePDF.spec --noconfirm

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("../prompts", "prompts"),
    ("../assets/logo-square.png", "assets"),
]
datas += collect_data_files("gradio")
datas += collect_data_files("gradio_client")
datas += collect_data_files("safehttpx")
datas += collect_data_files("groovy")
# magika (markitdown's file-type detector) loads its ONNX model dir lazily;
# without this, MarkItDown extraction fails only in the frozen app.
datas += collect_data_files("magika")

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
    console=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="DescribePDF",
)

app = BUNDLE(
    coll,
    name="DescribePDF.app",
    icon="icon.icns",
    bundle_identifier="com.davidlms.describepdf",
    info_plist={
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "CFBundleShortVersionString": "0.1.0",
    },
)
