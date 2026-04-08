"""
Ejecutor de codigo Python dinamico para Jarvis.
Permite a la IA ejecutar cualquier tarea en el PC generando codigo Python.
Incluye reglas de seguridad para proteger el sistema.
"""

import re
import subprocess
import sys
import os
import tempfile
from rich.console import Console

console = Console()

# =============================================================================
# REGLAS DE SEGURIDAD - Operaciones PROHIBIDAS
# =============================================================================

# Patrones prohibidos en el codigo (case insensitive)
FORBIDDEN_PATTERNS = [
    # Formateo de disco / destruccion masiva
    r"format\s+[a-z]:",
    r"diskpart",
    r"clean\s+all",
    r"format\(",
    # Borrar sistema operativo / archivos criticos
    r"rmdir\s+/s.*windows",
    r"rmdir\s+/s.*system32",
    r"rmdir\s+/s.*program\s*files",
    r"del\s+/[sfq].*windows",
    r"del\s+/[sfq].*system32",
    r"remove.*system32",
    r"rmtree.*system32",
    r"rmtree.*windows",
    r"rmtree.*program.files",
    r"shutil\.rmtree\s*\(\s*['\"]c:\\\\",
    r"shutil\.rmtree\s*\(\s*['\"]c:/",
    # Borrar disco entero
    r"rmtree\s*\(\s*['\"][a-z]:\\\\?['\"]",
    r"rmtree\s*\(\s*['\"][a-z]:/?['\"]",
    # Registro de Windows - destruccion
    r"reg\s+delete.*hklm",
    r"reg\s+delete.*hkey_local_machine",
    # Desactivar seguridad
    r"disable.*firewall",
    r"disable.*defender",
    r"disable.*antivirus",
    r"stop.*windefend",
    # Crypto / ransomware
    r"fernet.*encrypt",
    r"\.encrypt\(.*walk",
    # Fork bomb / consumir recursos
    r"while\s+true.*fork",
    r"os\.fork\s*\(",
    r"while\s+true.*popen",
    # Modificar bootloader / MBR
    r"mbr",
    r"bootrec",
    r"bcdedit.*delete",
    # Borrar usuarios del sistema
    r"net\s+user.*\/delete",
    r"net\s+user.*\/del",
]

# Rutas protegidas - no se pueden borrar ni modificar masivamente
PROTECTED_PATHS = [
    r"c:\\windows",
    r"c:/windows",
    r"c:\\program files",
    r"c:/program files",
    r"c:\\program files (x86)",
    r"c:/program files (x86)",
    r"system32",
]

_forbidden_re = re.compile("|".join(FORBIDDEN_PATTERNS), re.IGNORECASE)
_protected_re = re.compile("|".join(PROTECTED_PATHS), re.IGNORECASE)


def validate_code(code: str) -> tuple[bool, str]:
    """Valida que el codigo no contenga operaciones peligrosas."""
    # Buscar patrones prohibidos
    match = _forbidden_re.search(code)
    if match:
        return False, f"Operacion prohibida detectada: '{match.group()}'. No puedo ejecutar codigo que dane el sistema."

    # Verificar si intenta borrar rutas protegidas
    if ("rmtree" in code or "rmdir" in code or "remove" in code) and _protected_re.search(code):
        return False, "No puedo borrar archivos del sistema operativo ni carpetas protegidas."

    return True, ""


def execute_code(code: str) -> dict:
    """
    Ejecuta codigo Python de forma segura.
    El codigo se ejecuta como un script independiente con timeout.
    Retorna stdout + stderr como resultado.
    """
    # 1. Validar seguridad
    is_safe, reason = validate_code(code)
    if not is_safe:
        return {"success": False, "message": reason}

    # 2. Escribir el codigo en un archivo temporal
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp_path = tmp.name
            # Agregar encoding y imports basicos al inicio
            header = "# -*- coding: utf-8 -*-\nimport sys\nsys.stdout.reconfigure(encoding='utf-8')\nsys.stderr.reconfigure(encoding='utf-8')\n\n"
            tmp.write(header + code)

        # 3. Ejecutar el script con timeout
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.expanduser("~\\Desktop"),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            encoding="utf-8",
            errors="replace",
        )

        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""

        if result.returncode == 0:
            output = stdout or "Codigo ejecutado correctamente (sin output)."
            return {"success": True, "message": output[:1000]}
        else:
            error_msg = stderr or stdout or "Error desconocido"
            return {"success": False, "message": f"Error: {error_msg[:1000]}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "El codigo tardo mas de 60 segundos y fue detenido."}
    except Exception as e:
        return {"success": False, "message": f"Error ejecutando codigo: {str(e)[:500]}"}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
