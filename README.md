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

**Asistente de IA personal con control de PC, voz, busqueda web, Telegram y personalidad estilo JARVIS de Iron Man.**

Inspirado en JARVIS de Tony Stark.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
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
- [Control de PC](#control-de-pc)
- [Busqueda en Internet](#busqueda-en-internet)
- [Comandos Disponibles](#comandos-disponibles)
- [Proveedores de IA](#proveedores-de-ia)
- [Sistema de Voz](#sistema-de-voz)
- [Control remoto por Telegram](#control-remoto-por-telegram)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Solucion de Problemas](#solucion-de-problemas)

---

## Caracteristicas

- **Multi-Proveedor de IA** - Claude (Anthropic), OpenAI GPT, Google Gemini y Ollama (local/gratuito) con fallback automatico.
- **Personalidad JARVIS** - Humor seco, sarcasmo ocasional estilo mayordomo britanico de Tony Stark. Profesional pero con caracter.
- **Control completo del PC** - Abre/cierra apps, controla volumen, captura pantalla, graba video, bloquea/apaga/reinicia el equipo y mas.
- **Envio de mensajes por WhatsApp** - Automatiza el envio de mensajes a contactos por nombre desde WhatsApp Desktop.
- **Busqueda en Internet** - DuckDuckGo integrado (gratis, sin API key). Detecta preguntas que necesitan info actual y busca automaticamente.
- **Reconocimiento de Voz** - Wake word "Jarvis" + dictado continuo con SpeechRecognition y PyAudio.
- **Sintesis de Voz** - Respuestas habladas con Edge-TTS (alta calidad) o pyttsx3 (offline).
- **Control remoto por Telegram** - Bot de Telegram integrado: enviale texto o audio desde el celular y Jarvis ejecuta en el PC. Responde con audio cuando le mandas voz.
- **Spotify integrado** - Busca y reproduce canciones, albums o artistas usando automatizacion del Quick Search de Spotify.
- **Comandos rapidos** - Detector de comandos que ejecuta acciones instantaneas sin pasar por la IA (abrir apps, hora, volumen, etc.).
- **Memoria Conversacional** - Mantiene contexto de hasta 50 mensajes y guarda historial en JSON.
- **Creacion de documentos** - Crea archivos Word, Excel y texto desde comandos de voz o texto.
- **Interfaz Rica en Terminal** - UI estilizada con colores, paneles y spinners usando Rich.
- **Deteccion inteligente de placeholders** - Si dejas API keys de ejemplo en el `.env`, Jarvis las ignora y no pierde tiempo en autenticaciones fallidas.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                       main.py                           │
│                  (Loop principal)                        │
│          Voz / Teclado / Telegram -> Cola unificada     │
├──────────┬───────────┬───────────┬──────────────────────┤
│    AI    │   Voice   │  Memory   │       Tools          │
│ Providers│  Engine   │  System   │   (Herramientas)     │
├──────────┤           │           │                      │
│  Claude  │ Edge-TTS  │   JSON    │  pc_control          │
│  OpenAI  │ pyttsx3   │  History  │  automation          │
│  Gemini  │ STT (mic) │           │  web_search (DDG)    │
│  Ollama  │           │           │  fast_commands       │
├──────────┤           │           │  code_executor       │
│ Fallback │           │           │  whatsapp_send       │
│ auto     │           │           │                      │
├──────────┴───────────┴───────────┼──────────────────────┤
│          telegram_io             │       Utils          │
│  Bot Telegram (texto + voz)      │  /ayuda /voz /estado │
│  Respuestas en audio (OGG/Opus)  │  /proveedor /salir   │
└──────────────────────────────────┴──────────────────────┘
```

---

## Requisitos Previos

| Requisito | Version | Notas |
|-----------|---------|-------|
| **Python** | 3.10 o superior | [Descargar Python](https://www.python.org/downloads/) |
| **pip** | Incluido con Python | Gestor de paquetes |
| **FFmpeg** | Recomendado | Necesario para voz en Telegram y reproduccion de audio. [ffmpeg.org](https://ffmpeg.org/download.html) o `scoop install ffmpeg` en Windows |
| **Ollama** | Opcional | Para IA local y gratuita. [ollama.ai](https://ollama.ai) |

> **Nota:** Con Ollama no necesitas ninguna API key. Jarvis puede funcionar 100% local y gratuito.

---

## Instalacion

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/Reyner2809/Jarvis-Asistente.git
cd Jarvis-Asistente
```

### Paso 2: Crear y activar un entorno virtual

```bash
python -m venv venv

# Windows (CMD)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate
```

### Paso 3: Instalar dependencias

```bash
pip install -r requirements.txt
```

Dependencias principales:

| Paquete | Proposito |
|---------|-----------|
| `anthropic` | Cliente API de Claude (Anthropic) |
| `openai` | Cliente API de OpenAI (GPT) |
| `google-genai` | Cliente API de Google Gemini |
| `edge-tts` | Sintesis de voz de alta calidad |
| `pyttsx3` | Sintesis de voz offline (fallback) |
| `SpeechRecognition` | Reconocimiento de voz (microfono) |
| `PyAudio` | Captura de audio del microfono |
| `pyautogui` | Automatizacion de teclado/mouse (control de PC) |
| `ddgs` | Busqueda web con DuckDuckGo (gratis, sin API key) |
| `pyTelegramBotAPI` | Bot de Telegram para control remoto |
| `python-dotenv` | Carga de variables de entorno |
| `rich` | Interfaz de terminal con estilos |

### Paso 4: Instalar FFmpeg (recomendado)

```bash
# Windows (con scoop)
scoop install ffmpeg

# Linux
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

---

## Configuracion

### Paso 5: Configurar las variables de entorno

```bash
# Linux / macOS
cp .env.example .env

# Windows (CMD)
copy .env.example .env
```

Edita `.env` con tus valores:

```env
# ============================================
# API Keys (configura al menos UNA, o usa Ollama sin key)
# ============================================
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# ============================================
# Configuracion General
# ============================================
AI_PROVIDER=ollama
ASSISTANT_NAME=Jarvis
VOICE_LANGUAGE=es
VOICE_SPEED=180

# ============================================
# Modelos por proveedor
# ============================================
CLAUDE_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
GEMINI_MODEL=gemini-2.0-flash
OLLAMA_MODEL=llama3.2

# ============================================
# Telegram (opcional - control remoto)
# ============================================
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USERS=
TELEGRAM_ENABLE_VOICE=true
```

### Donde obtener las API Keys

| Proveedor | Enlace | Costo |
|-----------|--------|-------|
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Pago por uso |
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com/) | Pago por uso |
| **Google Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Tier gratuito |
| **Ollama** | [ollama.ai](https://ollama.ai) | Gratuito (local) |

> **Importante:** Si dejas keys de ejemplo como `sk-tu-key-aqui`, Jarvis las detecta como placeholders y las ignora automaticamente.

---

## Configuracion con Ollama (Opcion Gratuita)

```bash
# 1. Instalar Ollama desde ollama.ai
# 2. Descargar un modelo
ollama pull llama3.2

# 3. Verificar que esta corriendo
ollama serve

# 4. En .env:
# AI_PROVIDER=ollama
# OLLAMA_MODEL=llama3.2
```

> Ollama corre en `http://localhost:11434`. JARVIS lo detecta automaticamente.

---

## Uso

```bash
python main.py
```

```
  Inicializando sistemas...
    Proveedor activo: OLLAMA (llama3.2)
    Motor de voz: Edge TTS (alta calidad)
    Telegram activo: @tu_bot

  Sistemas en linea. Listo para servir, senor.
  Di "Jarvis" + tu comando para activarme por voz.

  Jarvis > _
```

Puedes interactuar con Jarvis de tres formas:
- **Teclado**: escribe directamente en la terminal.
- **Voz**: di "Jarvis" seguido de tu comando (wake word + dictado).
- **Telegram**: enviale un mensaje de texto o audio a tu bot desde el celular.

---

## Control de PC

Jarvis puede controlar tu PC con comandos naturales:

| Accion | Ejemplos |
|--------|----------|
| **Abrir apps** | "abre chrome", "abre la calculadora", "ingresa a spotify" |
| **Cerrar apps** | "cierra chrome", "mata notepad" |
| **Buscar en web** | "busca recetas de pasta", "googlea el clima" |
| **Spotify** | "pon Bohemian Rhapsody en spotify", "reproduce musica de Bad Bunny" |
| **Volumen** | "sube el volumen", "volumen a 50", "silencia" |
| **Media** | "siguiente cancion", "pausa", "anterior" |
| **Hora** | "que hora es" |
| **Captura** | "captura de pantalla", "graba la pantalla 30 segundos" |
| **Sistema** | "bloquea el pc", "apaga el pc", "reinicia", "suspender" |
| **Documentos** | "crea un documento word sobre mi proyecto", "crea un excel" |
| **WhatsApp** | "manda un mensaje en whatsapp a Juan diciendo hola" |
| **Escribir texto** | "escribe 'hola mundo'" (escribe donde este el cursor) |

Jarvis normaliza nombres automaticamente: "abre **la** calculadora", "ingresa **a** chrome", "abre **el** bloc de notas" funcionan igual que "abre calculadora".

---

## Busqueda en Internet

Jarvis detecta automaticamente preguntas que necesitan informacion actual y busca en **DuckDuckGo** (gratis, sin API key):

```
Jarvis > que noticias hay hoy
 Buscando en internet...
 [Resultado resumido por la IA]

Jarvis > cual es el precio del dolar
Jarvis > averigua en internet quien gano la Champions
Jarvis > investiga sobre inteligencia artificial
```

Patrones que activan la busqueda automatica:
- Noticias, clima, precios, cotizaciones
- "busca/investiga/averigua en internet..."
- Resultados deportivos, eventos actuales
- Preguntas sobre personas o eventos recientes

---

## Comandos Disponibles

| Comando | Alias | Descripcion |
|---------|-------|-------------|
| `/ayuda` | `/help` | Muestra la lista de comandos |
| `/voz` | `/voice` | Activa/desactiva la sintesis de voz |
| `/proveedor <nombre>` | `/provider <name>` | Cambia el proveedor de IA |
| `/estado` | `/status` | Estadisticas de la sesion |
| `/limpiar` | `/clear` | Limpia el historial de conversacion |
| `/salir` | `/exit`, `/quit` | Guarda la sesion y cierra JARVIS |

---

## Proveedores de IA

| Proveedor | Modelo por defecto | API Key | Internet |
|-----------|--------------------|---------|----------|
| **Claude** | `claude-sonnet-4-20250514` | Si | Si |
| **OpenAI** | `gpt-4o` | Si | Si |
| **Gemini** | `gemini-2.0-flash` | Si | Si |
| **Ollama** | `llama3.2` | No | No |

### Fallback automatico

```
Proveedor Principal -> Fallback 1 -> Fallback 2 -> Fallback 3
     CLAUDE       ->   OPENAI   ->   GEMINI   ->   OLLAMA
```

Si el proveedor preferido falla, Jarvis cambia al siguiente disponible automaticamente.

---

## Sistema de Voz

### Sintesis (TTS)

| Motor | Calidad | Requiere Internet |
|-------|---------|-------------------|
| **Edge-TTS** (principal) | Alta (voces neuronales) | Si |
| **pyttsx3** (fallback) | Basica | No |

Voces: `es-VE-SebastianNeural` (espanol), `en-US-GuyNeural` (ingles).

### Reconocimiento (STT)

- **Wake word**: di "Jarvis" para activar la escucha.
- **Google Web Speech API** para transcripcion (requiere internet).
- Soporte de microfono via PyAudio.

### Reproduccion

Requiere FFmpeg (`ffplay`) o PowerShell MediaPlayer (Windows, fallback automatico).

---

## Control remoto por Telegram

Jarvis incluye un bot de Telegram integrado para controlarlo desde el celular sin depender del microfono del PC.

### Configuracion

1. **Crear el bot**: Telegram -> `@BotFather` -> `/newbot` -> copia el token.
2. **Obtener tu user ID**: habla con `@userinfobot` -> copia tu ID numerico.
3. **Editar `.env`**:

    ```env
    TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
    TELEGRAM_ALLOWED_USERS=987654321
    TELEGRAM_ENABLE_VOICE=true
    ```

4. **Reiniciar Jarvis**. Veras `Telegram activo: @tu_bot` en el arranque.

### Uso

| Tipo de mensaje | Comportamiento |
|-----------------|----------------|
| **Texto** | Se procesa igual que un comando de teclado/voz |
| **Audio** | Se transcribe con Google STT y se procesa. Jarvis responde con mensaje de voz (OGG/Opus via Edge-TTS) |
| **`/start`, `/help`** | Muestra ayuda |
| **`/whoami`** | Devuelve tu user ID (util para el primer setup) |

### Respuestas de voz

Cuando envias un audio por Telegram, Jarvis:
1. Transcribe tu audio (FFmpeg + Google STT).
2. Procesa la peticion.
3. Genera audio de respuesta con Edge-TTS.
4. Convierte a OGG/Opus y lo envia como mensaje de voz en Telegram.

Si envias texto, responde con texto.

### Seguridad

- Sin `TELEGRAM_ALLOWED_USERS` configurado, el bot **NO** se activa.
- Solo los user IDs autorizados pueden interactuar. El resto es rechazado.
- Comandos del sistema (`/salir`, `/voz`, etc.) estan bloqueados desde Telegram.

---

## Estructura del Proyecto

```
Jarvis-Asistente/
├── main.py                     # Punto de entrada y loop principal
├── config.py                   # Configuracion (.env) y system prompt
├── requirements.txt            # Dependencias de Python
├── .env.example                # Plantilla de configuracion
├── .gitignore                  # Archivos ignorados por Git
├── README.md                   # Este archivo
│
├── ai_providers/               # Proveedores de Inteligencia Artificial
│   ├── __init__.py
│   ├── base.py                 # Clase abstracta base (AIProvider)
│   ├── manager.py              # Gestor con fallback automatico
│   ├── claude_provider.py      # Claude (Anthropic)
│   ├── openai_provider.py      # OpenAI (GPT)
│   ├── gemini_provider.py      # Google Gemini
│   └── ollama_provider.py      # Ollama (local)
│
├── tools/                      # Herramientas de accion
│   ├── __init__.py
│   ├── executor.py             # Ejecutor de tools (parsea [TOOL:...] de la IA)
│   ├── fast_commands.py        # Comandos rapidos sin IA (regex)
│   ├── pc_control.py           # Control del PC (apps, volumen, sistema, WhatsApp)
│   ├── automation.py           # Automatizacion UI (pyautogui)
│   ├── code_executor.py        # Ejecutor de codigo Python
│   └── web_search.py           # Busqueda web con DuckDuckGo
│
├── voice/                      # Motor de voz
│   ├── __init__.py
│   ├── tts.py                  # Sintesis (Edge-TTS + pyttsx3)
│   └── stt.py                  # Reconocimiento (SpeechRecognition)
│
├── memory/                     # Memoria conversacional
│   ├── __init__.py
│   └── conversation.py         # Historial JSON persistente
│
├── telegram_io/                # Bot de Telegram (control remoto)
│   ├── __init__.py
│   └── bot.py                  # Adaptador (texto + voz, respuestas audio)
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
- Verifica que al menos una API key este configurada en `.env` (o que Ollama este corriendo).
- Si usas Ollama: `ollama serve`

### La voz no funciona
- Instala FFmpeg: `scoop install ffmpeg` (Windows) o `apt install ffmpeg` (Linux).
- Edge-TTS requiere internet. Sin conexion, se usa pyttsx3 automaticamente.

### El bot de Telegram no arranca
- Verifica que `TELEGRAM_BOT_TOKEN` y `TELEGRAM_ALLOWED_USERS` esten definidos en `.env`.
- Sin `TELEGRAM_ALLOWED_USERS`, el bot no se activa por seguridad.
- Habla con `@userinfobot` para obtener tu ID.

### Audio de Telegram no se transcribe
- Requiere FFmpeg instalado y en el PATH.
- Windows: `scoop install ffmpeg` o descarga de [ffmpeg.org](https://ffmpeg.org/download.html).

### Jarvis tarda en responder
- Si tienes API keys de ejemplo/placeholder, Jarvis las ignora automaticamente. Pero si pusiste keys invalidas (no placeholder), intentara autenticarse y fallara antes de pasar al siguiente proveedor. Limpia las keys que no uses.
- Para maxima velocidad: `AI_PROVIDER=ollama` y sin keys remotas.

### "abre X" no funciona
- Jarvis busca la app en: apps conocidas, accesos directos del Menu Inicio, escritorio y PowerShell Get-StartApps.
- Articulos como "la", "el", "a" se limpian automaticamente.
- Si la app no aparece en ninguna de esas fuentes, Jarvis reporta el error sin mostrar dialogos de Windows.

### Error al instalar dependencias
- Python 3.10 o superior requerido: `python --version`
- Actualiza pip: `pip install --upgrade pip`
- En Windows, si PyAudio da error: `pip install pipwin && pipwin install pyaudio`

---

## Licencia

Este proyecto esta bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para mas detalles.
