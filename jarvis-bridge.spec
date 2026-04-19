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
    # Providers (modulo real: ai_providers)
    'ai_providers', 'ai_providers.manager',
    'ai_providers.claude_provider', 'ai_providers.openai_provider',
    'ai_providers.gemini_provider', 'ai_providers.ollama_provider',
    # Memory / knowledge
    'memory', 'knowledge', 'knowledge.rag',
    # Telegram
    'telegram_io', 'telegram_io.bot', 'telebot', 'imageio_ffmpeg',
    # Scheduler
    'scheduler',
    # Chromadb submodulos que PyInstaller no detecta por defecto
    'chromadb', 'chromadb.telemetry', 'chromadb.telemetry.product',
    'chromadb.telemetry.product.posthog', 'chromadb.api', 'chromadb.api.segment',
    'chromadb.config', 'chromadb.db', 'chromadb.segment',
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

# Incluir submodulos completos de paquetes que PyInstaller no rastrea bien
for _pkg in ('chromadb', 'ai_providers', 'edge_tts', 'telebot', 'imageio_ffmpeg',
             'telegram_io', 'scheduler'):
    try:
        _subs = collect_submodules(_pkg)
        hiddenimports += _subs
        print(f'[spec] collect_submodules({_pkg!r}): +{len(_subs)} submodulos')
    except Exception as _e:
        print(f'[spec] collect_submodules({_pkg!r}) FAILED: {_e!r}')

# Recoger data files del proyecto
# IMPORTANTE: NO empaquetar .env — contiene credenciales del dev y debe ser
# generado por el Setup Wizard en cada instalacion (%APPDATA%\Jarvis\.env).
datas = [
    (os.path.join(ROOT, 'config.py'), '.'),
]
datas = [d for d in datas if d is not None]

# Data files de paquetes externos (chromadb incluye archivos de schema;
# imageio_ffmpeg trae el binario ffmpeg portable)
for _pkg in ('chromadb', 'imageio_ffmpeg'):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

# Agregar carpetas del proyecto como datos (nota: ai_providers, no providers)
for folder in ['tools', 'voice', 'ai_providers', 'memory', 'bridge', 'knowledge', 'telegram_io', 'scheduler']:
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
    upx=False,
    console=False,  # sin ventana de consola en release (logs via stderr al padre Electron)
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
    upx=False,
    upx_exclude=[],
    name='jarvis-bridge',
)
