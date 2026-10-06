# -*- mode: python ; coding: utf-8 -*-

import os
import importlib.util

# ─────────────────────────────────────────────────────────────────────
# Caminho base: pasta onde este arquivo .spec está
# ─────────────────────────────────────────────────────────────────────
SPEC_DIR = SPECPATH

# ─────────────────────────────────────────────────────────────────────
# Carrega o version.py manualmente (evita problemas de sys.path)
# ─────────────────────────────────────────────────────────────────────
version_file = os.path.abspath(os.path.join(SPEC_DIR, '..', 'app', 'version.py'))


if not os.path.exists(version_file):
    raise FileNotFoundError(f"version.py não encontrado em: {version_file}")

spec = importlib.util.spec_from_file_location("version", version_file)
version_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version_module)

__version__ = version_module.__version__
APP_NAME = version_module.APP_NAME

print(f"[BUILD] {APP_NAME} v{__version__}")

# Converte versão "1.4.3" para formato Windows "1.4.3.0"
version_parts = __version__.split('.')
while len(version_parts) < 4:
    version_parts.append('0')
version_tuple = tuple(int(p) for p in version_parts[:4])
version_str = '.'.join(str(p) for p in version_tuple)

# ─────────────────────────────────────────────────────────────────────
# Gera version_info.txt dinamicamente (metadados do executável Windows)
# ─────────────────────────────────────────────────────────────────────
version_info_content = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'041604B0',
          [StringStruct(u'CompanyName', u'Nathan Cruz'),
           StringStruct(u'FileDescription', u'{APP_NAME} - Sistema de Portaria'),
           StringStruct(u'FileVersion', u'{version_str}'),
           StringStruct(u'InternalName', u'sisport'),
           StringStruct(u'LegalCopyright', u'Copyright (c) 2026 Nathan Cruz'),
           StringStruct(u'OriginalFilename', u'sisport.exe'),
           StringStruct(u'ProductName', u'{APP_NAME}'),
           StringStruct(u'ProductVersion', u'{version_str}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1046, 1200])])
  ]
)
'''

# Escreve o arquivo temporariamente
version_info_path = os.path.join(SPEC_DIR, 'version_info.txt')
with open(version_info_path, 'w', encoding='utf-8') as f:
    f.write(version_info_content)

# ─────────────────────────────────────────────────────────────────────
# Dados da aplicação
# ─────────────────────────────────────────────────────────────────────
datas = [
    ('../icone.ico', '.'),
    ("../app/templates", "app/templates"),
    ("../app/static", "app/static"),
    ("../migrations", "migrations"),
    ("../migrations/versions", "migrations/versions"),
]

# ─────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────
a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'logging.config',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ─────────────────────────────────────────────────────────────────────
# Executável
# ─────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    icon='../icone.ico',
    name='sisport',
    version=version_info_path,          # ← Usa o version_info.txt gerado dinamicamente
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

# ─────────────────────────────────────────────────────────────────────
# Coleta final
# ─────────────────────────────────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='sisport',
)
