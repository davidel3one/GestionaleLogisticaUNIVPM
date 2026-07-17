# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent

datas = []
datas += collect_data_files("pulp")
datas += [
    (str(ROOT / "src/gestionale_logistica/gui/assets"), "gestionale_logistica/gui/assets"),
    (str(ROOT / "src/gestionale_logistica/data/geocoding"), "gestionale_logistica/data/geocoding"),
    (str(ROOT / ".env"), "."),
]

a = Analysis(
    [str(ROOT / "packaging/entry_point.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["sqlcipher3", "sqlcipher3.dbapi2"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GestionaleLogistica",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GestionaleLogistica",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="GestionaleLogistica.app",
        icon=None,
        bundle_identifier="it.univpm.gestionalelogistica",
        info_plist={
            "CFBundleName": "Gestionale Logistica",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
