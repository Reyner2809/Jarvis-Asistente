# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para jarvis-bridge.exe

Genera un ejecutable standalone que contiene:
  - Python runtime
  - FastAPI + uvicorn
  - Todos los modulos de Jarvis (bridge, tools, voice, config, etc.)
  - Dependencias de requirements.txt

Uso:
  pyinstaller jarvis-bridge.spec

Output:
  dist/jarvis-bridge/jarvis-bridge.exe
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Directorio raiz del proyecto
ROOT = os.path.abspath('.')

# Recoger todos los submodulos necesarios
hiddenimports = [
    # Bridge
    'bridge', 'bridge.server', 'bridge.processor', 'bridge.voice_loop',
    # Config
    'config',
    # Tools
    'tools', 'tools.executor', 'tools.pc_control', 'tools.fast_commands',
    'tools.intent_router',
    # Voice
    'voice', 'voice.tts', 'voice.stt',
    # Providers
    'providers', 'providers.provider_manager',
    # Memory
    'memory',
    # Dependencies
    'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'fastapi', 'fastapi.routing', 'fastapi.middleware', 'fastapi.middleware.cors',
    'starlette', 'starlette.routing', 'starlette.websockets',
    'pydantic', 'pydantic.fields',
    'dotenv',
    'anthropic', 'openai',
    'edge_tts',
    'websockets',
    'httpx', 'httpcore', 'anyio', 'sniffio',
    'rich', 'rich.console', 'rich.panel',
]

# Recoger data files de paquetes que lo necesitan
datas = [
    # .env y config si existen
    (os.path.join(ROOT, '.env'), '.') if os.path.exists(os.path.join(ROOT, '.env')) else None,
    (os.path.join(ROOT, 'config.py'), '.'),
]
datas = [d for d in datas if d is not None]

# Agregar carpetas del proyecto como datos
for folder in ['tools', 'voice', 'providers', 'memory', 'bridge', 'knowledge']:
    folder_path = os.path.join(ROOT, folder)
    if os.path.isdir(folder_path):
        for root_dir, dirs, files in os.walk(folder_path):
            for f in files:
                if f.endswith('.py'):
                    src = os.path.join(root_dir, f)
                    dst = os.path.relpath(root_dir, ROOT)
                    datas.append((src, dst))

a = Analysis(
    [os.path.join(ROOT, 'bridge', 'jarvis_bridge.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'numpy.testing',
        'IPython', 'jupyter', 'notebook',
        'pytest', 'unittest',
    ],
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
    name='jarvis-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # console=True para ver logs; cambiar a False para release silencioso
    icon=os.path.join(ROOT, 'desktop', 'assets', 'icon.ico')
        if os.path.exists(os.path.join(ROOT, 'desktop', 'assets', 'icon.ico'))
        else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='jarvis-bridge',
)
