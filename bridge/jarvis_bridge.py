"""
Entry point para PyInstaller.
Arranca el bridge FastAPI como ejecutable standalone.

Uso: jarvis-bridge.exe --port 17891
"""
import sys
import os

# Asegurar que el directorio del exe este en el path para imports
if getattr(sys, 'frozen', False):
    # Corriendo como PyInstaller bundle
    base_dir = sys._MEIPASS
    os.chdir(os.path.dirname(sys.executable))
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.join(base_dir, '..'))

sys.path.insert(0, base_dir)
sys.path.insert(0, os.getcwd())

# Parsear --port
port = 17891
for i, arg in enumerate(sys.argv):
    if arg == '--port' and i + 1 < len(sys.argv):
        port = int(sys.argv[i + 1])

# Arrancar uvicorn con la app FastAPI
import uvicorn
from bridge.server import app

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='info')
