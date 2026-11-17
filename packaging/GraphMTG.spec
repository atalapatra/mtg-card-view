# PyInstaller spec for GraphMTG: Python, the mtgcv package and the built web UI
# (web/dist -> webui inside the bundle).
#
#   Windows: packaging\build_exe.ps1   -> dist\GraphMTG.exe (one file, console window = "running")
#   macOS:   packaging/build_mac.sh    -> dist/GraphMTG.app (menu-bar app, Apple Silicon; D-022)
#
# Both scripts build the web UI first.

import os
import re
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
WEB_DIST = os.path.join(ROOT, "web", "dist")
if not os.path.isfile(os.path.join(WEB_DIST, "index.html")):
    raise SystemExit("web/dist is missing: run `npm run build` in web/ first (the build scripts do this).")

MAC = sys.platform == "darwin"
with open(os.path.join(ROOT, "src", "mtgcv", "__init__.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__ = "(.+?)"', f.read()).group(1)

datas = [(WEB_DIST, "webui")]
# uvicorn picks its loop/protocol implementations dynamically.
hiddenimports = collect_submodules("uvicorn") + ["mtgcv.server"]
if MAC:
    datas.append((os.path.join(SPECPATH, "graphmtg-menubar.png"), "."))
    hiddenimports += ["mtgcv.macapp", "rumps"]

a = Analysis(
    [os.path.join(SPECPATH, "graphmtg_entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if not MAC:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="GraphMTG",
        icon=os.path.join(SPECPATH, "graphmtg.ico"),
        console=True,  # the console window is the "app is running" indicator; closing it quits
        upx=False,
        debug=False,
        strip=False,
    )
else:
    # A .app bundle is a folder build (PyInstaller 6 deprecates one-file .app bundles).
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="GraphMTG",
        console=False,
        target_arch="arm64",
        upx=False,
        debug=False,
        strip=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="GraphMTG", upx=False, strip=False)
    app = BUNDLE(
        coll,
        name="GraphMTG.app",
        icon=os.path.join(SPECPATH, "graphmtg.icns"),
        bundle_identifier="app.graphmtg.GraphMTG",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "GraphMTG",
            "CFBundleShortVersionString": VERSION,
            "LSUIElement": True,  # menu-bar only: no Dock icon, no app menu
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
        },
    )
