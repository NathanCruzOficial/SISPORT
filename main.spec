# -*- mode: python ; coding: utf-8 -*-

import os

datas = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
]

a = Analysis(
    ['runtime_hooks.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sisport',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,     # <- padrão True
    console=True,
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
    name='sisport',
)
