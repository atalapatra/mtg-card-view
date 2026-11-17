# PyInstaller spec for GraphMTG.exe: one self-contained Windows executable with
# Python, the mtgcv package and the built web UI (web/dist -> webui inside the bundle).
#
#   packaging\build_exe.ps1        (builds the web UI first, then runs this spec)

import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
WEB_DIST = os.path.join(ROOT, "web", "dist")
if not os.path.isfile(os.path.join(WEB_DIST, "index.html")):
    raise SystemExit("web/dist is missing: run `npm run build` in web/ first (build_exe.ps1 does this).")

a = Analysis(
    [os.path.join(SPECPATH, "graphmtg_entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=[(WEB_DIST, "webui")],
    # uvicorn picks its loop/protocol implementations dynamically.
    hiddenimports=collect_submodules("uvicorn") + ["mtgcv.server"],
    excludes=["tkinter", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
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
