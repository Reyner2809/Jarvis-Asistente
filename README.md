# JARVIS - Asistente de Inteligencia Artificial Personal

<div align="center">

```
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
```

**Asistente de IA conversacional con soporte multi-proveedor, voz y memoria persistente.**

Inspirado en JARVIS de Iron Man.

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## Tabla de Contenidos

- [Caracteristicas](#caracteristicas)
- [Arquitectura](#arquitectura)
- [Requisitos Previos](#requisitos-previos)
- [Instalacion](#instalacion)
- [Configuracion](#configuracion)
- [Uso](#uso)
- [Comandos Disponibles](#comandos-disponibles)
- [Proveedores de IA](#proveedores-de-ia)
- [Sistema de Voz](#sistema-de-voz)
- [Estructura del Proyecto](#estructura-del-proyecto)

---

## Caracteristicas

- **Multi-Proveedor de IA** - Soporte para Claude (Anthropic), OpenAI GPT, Google Gemini y Ollama (local/gratuito).
- **Fallback Automatico** - Si un proveedor falla, cambia automaticamente al siguiente disponible.
- **Sintesis de Voz** - Respuestas habladas con Edge-TTS (alta calidad) o pyttsx3 (offline).
- **Memoria Conversacional** - Mantiene contexto de hasta 50 mensajes y guarda historial en JSON.
- **Interfaz Rica en Terminal** - UI estilizada con colores, paneles y spinners usando Rich.
- **Historial de Prompts** - Navegacion con flechas arriba/abajo entre entradas anteriores.
- **Comandos Interactivos** - Sistema de comandos con `/` para controlar el asistente.
- **Idioma Espanol** - Personalidad en espanol con soporte para otros idiomas.

---

## Arquitectura

```
┌─────────────────────────────────────────────────┐
│                   main.py                       │
│              (Loop principal)                   │
├────────┬──────────┬──────────┬──────────────────┤
│  AI    │  Voice   │  Memory  │     Utils        │
│Providers│ Engine  │  System  │   (Commands)     │
├────────┤          │          │                  │
│ Claude │          │          │                  │
│ OpenAI │ Edge-TTS │  JSON    │  /ayuda /voz     │
│ Gemini │ pyttsx3  │  History │  /proveedor      │
│ Ollama │          │          │  /estado /salir  │
└────────┴──────────┴──────────┴──────────────────┘
```

---

## Requisitos Previos

| Requisito | Version | Notas |
|-----------|---------|-------|
| **Python** | 3.7 o superior | [Descargar Python](https://www.python.org/downloads/) |
| **pip** | Incluido con Python | Gestor de paquetes |
| **API Key** | Al menos una | Ver seccion [Configuracion](#configuracion) |

> **Nota:** Si prefieres usar Ollama (gratuito y local), no necesitas ninguna API key. Solo necesitas tener [Ollama](https://ollama.ai) instalado y corriendo.

---

## Instalacion

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/jarvis.git
cd jarvis
```

### Paso 2: Crear un entorno virtual

Es recomendable usar un entorno virtual para aislar las dependencias del proyecto.

```bash
# Crear el entorno virtual
python -m venv venv
```

### Paso 3: Activar el entorno virtual

```bash
# Windows (CMD)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate
```

> Una vez activado, veras `(venv)` al inicio de tu terminal.

### Paso 4: Instalar dependencias

```bash
pip install -r requirements.txt
```

Esto instalara las siguientes librerias:

| Paquete | Proposito |
|---------|-----------|
| `anthropic` | Cliente API de Claude (Anthropic) |
| `openai` | Cliente API de OpenAI (GPT) |
| `google-genai` | Cliente API de Google Gemini |
| `edge-tts` | Sintesis de voz de alta calidad (requiere internet) |
| `pyttsx3` | Sintesis de voz offline (fallback) |
| `python-dotenv` | Carga de variables de entorno desde `.env` |
| `rich` | Interfaz de terminal con estilos y colores |
| `prompt-toolkit` | Entrada interactiva con historial |

---

## Configuracion

### Paso 5: Configurar las variables de entorno

Copia el archivo de ejemplo y editalo con tus API keys:

```bash
# Linux / macOS
cp .env.example .env

# Windows (CMD)
copy .env.example .env
```

Abre el archivo `.env` con tu editor preferido y configura lo siguiente:

```env
# ============================================
# API Keys (configura al menos UNA)
# ============================================

# OpenAI - https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-tu-key-aqui

# Anthropic (Claude) - https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-tu-key-aqui

# Google Gemini - https://aistudio.google.com/apikey
GEMINI_API_KEY=tu-key-aqui

# ============================================
# Configuracion General
# ============================================

# Proveedor preferido: claude | openai | gemini | ollama
AI_PROVIDER=claude

# Nombre del asistente
ASSISTANT_NAME=Jarvis

# Idioma de voz: es (espanol) | en (ingles)
VOICE_LANGUAGE=es

# Velocidad de voz (palabras por minuto)
VOICE_SPEED=180

# ============================================
# Modelos por proveedor
# ============================================
CLAUDE_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
GEMINI_MODEL=gemini-2.0-flash
OLLAMA_MODEL=llama3.2
```

### Donde obtener las API Keys

| Proveedor | Enlace | Costo |
|-----------|--------|-------|
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Pago por uso |
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com/) | Pago por uso |
| **Google Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Tier gratuito disponible |
| **Ollama** | [ollama.ai](https://ollama.ai) | Gratuito (local) |

---

## Configuracion con Ollama (Opcion Gratuita)

Si prefieres no usar API keys de pago, puedes usar Ollama para ejecutar modelos de IA localmente:

### 1. Instalar Ollama

Descarga e instala desde [ollama.ai](https://ollama.ai).

### 2. Descargar un modelo

```bash
ollama pull llama3.2
```

### 3. Verificar que Ollama esta corriendo

```bash
ollama serve
```

> Ollama corre por defecto en `http://localhost:11434`. JARVIS lo detecta automaticamente.

### 4. Configurar `.env`

```env
AI_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

---

## Uso

### Paso 6: Ejecutar JARVIS

```bash
python main.py
```

Veras el banner de bienvenida y JARVIS se inicializara:

```
  ┌──────────────────────────────────────────┐
  │       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗  │
  │  ...                                         │
  │       Escribe /ayuda para ver comandos        │
  └──────────────────────────────────────────┘

  Inicializando sistemas...
    Proveedor activo: CLAUDE
    Fallback: CLAUDE -> GEMINI -> OLLAMA
    Motor de voz: Edge TTS (alta calidad)

  Sistemas en linea. Listo para servir, senor.

  Jarvis > _
```

Escribe tu mensaje y presiona **Enter** para interactuar con JARVIS.

---

## Comandos Disponibles

Todos los comandos comienzan con `/` y estan disponibles en espanol e ingles:

| Comando | Alias | Descripcion |
|---------|-------|-------------|
| `/ayuda` | `/help` | Muestra la lista de comandos disponibles |
| `/voz` | `/voice` | Activa o desactiva la sintesis de voz |
| `/proveedor <nombre>` | `/provider <name>` | Cambia el proveedor de IA activo |
| `/estado` | `/status` | Muestra estadisticas de la sesion actual |
| `/limpiar` | `/clear` | Limpia el historial de la conversacion actual |
| `/salir` | `/exit`, `/quit` | Guarda la sesion y cierra JARVIS |

### Ejemplos de uso

```bash
# Cambiar a OpenAI
Jarvis > /proveedor openai

# Ver el estado actual
Jarvis > /estado

# Desactivar la voz
Jarvis > /voz
```

---

## Proveedores de IA

JARVIS soporta multiples proveedores con fallback automatico:

| Proveedor | Modelo por defecto | Requiere API Key | Requiere Internet |
|-----------|--------------------|-------------------|-------------------|
| **Claude** | `claude-sonnet-4-20250514` | Si | Si |
| **OpenAI** | `gpt-4o` | Si | Si |
| **Gemini** | `gemini-2.0-flash` | Si | Si |
| **Ollama** | `llama3.2` | No | No |

### Sistema de Fallback

Si el proveedor principal falla, JARVIS intenta automaticamente con el siguiente proveedor disponible en la cadena configurada:

```
Proveedor Principal -> Fallback 1 -> Fallback 2 -> Fallback 3
     CLAUDE       ->   OPENAI   ->   GEMINI   ->   OLLAMA
```

---

## Sistema de Voz

JARVIS puede hablar las respuestas usando dos motores de voz:

### Edge-TTS (Principal)
- Voces neuronales de alta calidad
- Requiere conexion a internet
- Voz en espanol: `es-VE-SebastianNeural`
- Voz en ingles: `en-US-GuyNeural`

### pyttsx3 (Fallback)
- Funciona sin conexion a internet
- Calidad de voz inferior
- Se activa automaticamente si Edge-TTS no esta disponible

### Reproduccion de Audio

| Plataforma | Reproductores soportados |
|------------|-------------------------|
| **Windows** | ffplay, PowerShell MediaPlayer |
| **Linux** | ffplay, mpv, aplay |
| **macOS** | ffplay, mpv, afplay |

> **Recomendacion:** Instala [FFmpeg](https://ffmpeg.org/download.html) para la mejor experiencia de audio.

---

## Estructura del Proyecto

```
jarvis/
├── main.py                     # Punto de entrada de la aplicacion
├── config.py                   # Gestion de configuracion (.env)
├── requirements.txt            # Dependencias de Python
├── .env.example                # Plantilla de configuracion
├── .gitignore                  # Archivos ignorados por Git
├── README.md                   # Este archivo
│
├── ai_providers/               # Proveedores de Inteligencia Artificial
│   ├── __init__.py             # Exportaciones del modulo
│   ├── base.py                 # Clase abstracta base (AIProvider)
│   ├── manager.py              # Gestor de proveedores con fallback
│   ├── claude_provider.py      # Implementacion de Claude (Anthropic)
│   ├── openai_provider.py      # Implementacion de OpenAI (GPT)
│   ├── gemini_provider.py      # Implementacion de Google Gemini
│   └── ollama_provider.py      # Implementacion de Ollama (local)
│
├── memory/                     # Sistema de memoria conversacional
│   ├── __init__.py
│   └── conversation.py         # Historial JSON persistente
│
├── voice/                      # Motor de sintesis de voz
│   ├── __init__.py
│   └── tts.py                  # Edge-TTS y pyttsx3
│
├── utils/                      # Utilidades
│   ├── __init__.py
│   └── commands.py             # Manejador de comandos (/)
│
└── data/                       # Datos de ejecucion (gitignored)
    └── conversation_history.json
```

---

## Solucion de Problemas

### "No hay proveedores disponibles"
- Verifica que al menos una API key este configurada en `.env`
- Si usas Ollama, asegurate de que este corriendo (`ollama serve`)

### La voz no funciona
- Verifica tu conexion a internet (Edge-TTS lo requiere)
- Instala FFmpeg para mejor compatibilidad de audio: [ffmpeg.org](https://ffmpeg.org/download.html)
- Si estas en Windows, PowerShell se usa como fallback automatico

### Error de conexion con un proveedor
- Verifica que tu API key sea valida y tenga credito disponible
- JARVIS intentara automaticamente con el siguiente proveedor disponible

### Error al instalar dependencias
- Asegurate de usar Python 3.7 o superior: `python --version`
- Actualiza pip: `pip install --upgrade pip`
- En Windows, si `pyttsx3` da error, instala Visual C++ Build Tools

---

## Licencia

Este proyecto esta bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para mas detalles.
