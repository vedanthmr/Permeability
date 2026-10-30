# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT_DIR = Path(os.path.abspath('.')).resolve()

datas = [
    (str(ROOT_DIR / 'static_app'), 'static_app'),
    (str(ROOT_DIR / 'website'), 'website'),
    (str(ROOT_DIR / 'models' / 'trained_prompt_injection'), 'models/trained_prompt_injection'),
    (str(ROOT_DIR / 'data' / 'jailbreak_prompts.json'), 'data'),
    (str(ROOT_DIR / 'document_engine'), 'document_engine'),
]

if (ROOT_DIR / 'models' / 'all-MiniLM-L6-v2').exists():
    datas.append((str(ROOT_DIR / 'models' / 'all-MiniLM-L6-v2'), 'models/all-MiniLM-L6-v2'))

hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.responses',
    'starlette.middleware',
    'sklearn',
    'sklearn.utils._typedefs',
    'sklearn.linear_model._stochastic_gradient',
    'sklearn.feature_extraction.text',
    'joblib',
    'webview',
    'docx',
    'PyPDF2',
    'bs4',
    'requests',
    'sentence_transformers',
    'torch',
    'scipy',
    'numpy',
    'pandas',
    'pyarrow',
    'email_validator',
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'pytest', 'ipython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AdaptShield',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AdaptShield',
)
