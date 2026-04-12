#!/usr/bin/env python3
"""
JARVIS - Asistente de Inteligencia Artificial Personal
Inspirado en JARVIS de Iron Man.

Uso: python main.py
"""

import sys
import os
import threading
import queue

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner

import re

from config import Config
from ai_providers import ProviderManager
from voice import VoiceEngine, SpeechToText
from memory import ConversationMemory
from utils import CommandHandler
from tools import ToolExecutor, FastCommandDetector
from telegram_io import TelegramIO

# Patrones que indican que el usuario necesita informacion de internet
INTERNET_PATTERNS = [
    # Noticias
    r"noticia|noticias|que\s+(?:esta|está)\s+pasando|que\s+(?:ha|hay)\s+pasado",
    # Clima/tiempo
    r"clima|(?:que|cómo)\s+(?:tal\s+)?(?:el\s+)?(?:tiempo|temperatura)|va\s+a\s+llover|pronostico",
    # Precios/cotizaciones
    r"precio\s+de|cotizacion|(?:cuanto|cuánto)\s+(?:vale|cuesta)|dolar|bitcoin|bolsa",
    # Resultados deportivos
    r"resultado|marcador|(?:quien|quién)\s+(?:gano|ganó)|partido\s+de|score",
    # Eventos actuales
    r"hoy\s+(?:en|que)|esta\s+semana|actualmente|actual|reciente|ultimo|última|últim",
    # Búsqueda explícita de info
    r"(?:busca|buscame|dime)\s+(?:informacion|info)\s+(?:sobre|de|del)",
    r"(?:que|qué)\s+(?:sabes|hay)\s+(?:sobre|de|del|acerca)",
    r"(?:investiga|averigua|encuentra)\s+(?:sobre|de|del|acerca|info)",
    # "averigua/investiga/busca en internet X", "en google X", "en la web X"
    r"(?:investiga|averigua|encuentra|busca|buscame|dime|consulta)\s+(?:en\s+)?(?:internet|la\s+web|google|la\s+red)",
    # Personas/eventos/lugares actuales
    r"(?:quien|quién)\s+es\s+(?:el|la)\s+(?:presidente|primer\s+ministro)",
    r"(?:cuando|cuándo)\s+(?:es|sera|será)\s+(?:el|la|los|las)",
]

_internet_re = re.compile("|".join(INTERNET_PATTERNS), re.IGNORECASE)


def needs_internet(text: str) -> bool:
    """Detecta si la pregunta necesita informacion actualizada de internet."""
    return bool(_internet_re.search(text))

console = Console()

BANNER = r"""
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""


def display_banner():
    banner_text = Text(BANNER, style="bold cyan")
    panel = Panel(
        banner_text,
        subtitle="[dim]Escribe /ayuda para ver comandos | Habla en cualquier momento[/dim]",
        border_style="cyan",
    )
    console.print(panel)


def display_response(text: str, source: str = ""):
    title = f"[bold cyan]{Config.ASSISTANT_NAME}[/bold cyan]"
    if source:
        title += f" [dim]({source})[/dim]"
    panel = Panel(
        text,
        title=title,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def keyboard_input_thread(input_queue: queue.Queue, stop_event: threading.Event):
    """Hilo que lee input del teclado sin bloquear el hilo principal."""
    while not stop_event.is_set():
        try:
            text = input()
            if text is not None:
                # 4-tupla: (source, text, chat_id, is_voice). chat_id=None y
                # is_voice=False para teclado.
                input_queue.put(("keyboard", text.strip(), None, False))
        except EOFError:
            input_queue.put(("keyboard", "/salir", None, False))
            break
        except Exception:
            break


def main():
    display_banner()
    console.print("\n[bold cyan]Inicializando sistemas...[/bold cyan]")

    # Inicializar componentes
    provider_manager = ProviderManager()
    if not provider_manager.initialize():
        sys.exit(1)

    voice_engine = VoiceEngine()
    voice_engine.initialize()

    stt = SpeechToText()
    mic_available = stt.initialize()

    tool_executor = ToolExecutor()
    fast_cmd = FastCommandDetector()
    memory = ConversationMemory()
    cmd_handler = CommandHandler(provider_manager, voice_engine, memory, stt)
    system_prompt = Config.get_system_prompt()

    # Cola unificada para input (voz, teclado y telegram).
    # Formato: (source, text, chat_id)  -- chat_id es None salvo para Telegram.
    input_queue = queue.Queue()
    stop_event = threading.Event()

    # Iniciar escucha de voz continua
    if mic_available:
        stt.start_listening()

    # Iniciar hilo de teclado
    kb_thread = threading.Thread(
        target=keyboard_input_thread,
        args=(input_queue, stop_event),
        daemon=True,
    )
    kb_thread.start()

    # Inicializar integracion con Telegram (opcional). Le pasamos el voice_engine
    # para poder responder con audio cuando el usuario envia un audio por Telegram.
    telegram_io = TelegramIO(input_queue, voice_engine=voice_engine)
    telegram_active = telegram_io.initialize()
    if telegram_active:
        telegram_io.start()

    console.print("[bold green]\n  Sistemas en linea. Listo para servir, senor.[/bold green]")
    console.print("[dim]  Control del PC activado. Puedo abrir apps, buscar en la web, y mas.[/dim]")
    if mic_available:
        console.print(f'[dim]  Di "{Config.ASSISTANT_NAME}" + tu comando para activarme por voz.[/dim]')
        console.print("[dim]  Tambien puedes escribir directamente.[/dim]")
    else:
        console.print("[dim]  Microfono no disponible. Escribe tus comandos.[/dim]")
    if telegram_active:
        bot_username = telegram_io.bot_username
        if bot_username:
            console.print(f"[dim]  Telegram activo: @{bot_username}[/dim]")
        else:
            console.print("[dim]  Telegram activo[/dim]")

    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")

    # Helper para responder al usuario segun el origen del mensaje
    def reply(text: str, source: str, chat_id, *, header: str = "", as_voice: bool = False):
        """
        Envia la respuesta al canal correspondiente (consola+voz o Telegram).
        as_voice: si True y source=='telegram', responde con mensaje de voz en
        vez de texto. Ignorado para canales locales (siempre hablan si la voz
        esta activa).
        """
        if source == "telegram" and chat_id is not None:
            if as_voice:
                telegram_io.send_voice_reply(chat_id, text)
            else:
                telegram_io.send_reply(chat_id, text)
        else:
            display_response(text, header)
            if mic_available:
                stt.pause()
            voice_engine.speak(text)
            if mic_available:
                stt.resume()

    # Loop principal
    while not stop_event.is_set():
        try:
            user_input = None
            source = ""
            chat_id = None
            is_voice_input = False

            # Revisar si hay input de voz
            if mic_available:
                voice_text = stt.get_speech(timeout=0.05)
                if voice_text:
                    if voice_text == "__WAKE__":
                        # Solo dijo "Jarvis" sin comando -> activar escucha temporal
                        stt.activate_listening()
                        console.print(f"\n  [bold cyan]Digame, senor.[/bold cyan]")
                        stt.pause()
                        voice_engine.speak("Digame, senor.")
                        stt.resume()
                        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                        continue
                    # Desactivar escucha activa al recibir comando
                    stt.deactivate_listening()
                    user_input = voice_text
                    source = "voz"
                    console.print(f"\n  [green]Escuche:[/green] \"{user_input}\"")

            # Revisar si hay input de teclado o telegram
            if user_input is None:
                try:
                    item = input_queue.get(timeout=0.1)
                    # Formato: (source, text, chat_id, is_voice). Soporta tambien
                    # tuplas mas cortas por compatibilidad.
                    if len(item) == 4:
                        msg_type, text, chat_id, is_voice_input = item
                    elif len(item) == 3:
                        msg_type, text, chat_id = item
                    else:
                        msg_type, text = item
                        chat_id = None
                    if text:
                        user_input = text
                        if msg_type == "telegram":
                            source = "telegram"
                            tag = "voz" if is_voice_input else "texto"
                            console.print(
                                f"\n  [magenta]Telegram[/magenta] [{chat_id}] ({tag}): \"{user_input}\""
                            )
                        else:
                            source = "texto"
                except queue.Empty:
                    continue

            if not user_input:
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # Si el usuario escribio solo "Jarvis" por teclado, tratarlo como wake word.
            # Desde Telegram no tiene sentido (ya estas hablando con el bot), asi que se ignora.
            if SpeechToText.is_wake_word(user_input):
                if source == "telegram":
                    telegram_io.send_reply(chat_id, "Digame, senor.")
                    continue
                if mic_available:
                    stt.activate_listening()
                console.print(f"\n  [bold cyan]Digame, senor.[/bold cyan]")
                if mic_available:
                    stt.pause()
                voice_engine.speak("Digame, senor.")
                if mic_available:
                    stt.resume()
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # Manejar comandos del sistema (solo desde teclado/voz local;
            # comandos como /salir desde Telegram son peligrosos -> los ignoramos)
            if cmd_handler.is_command(user_input):
                if source == "telegram":
                    telegram_io.send_reply(
                        chat_id,
                        "Los comandos del sistema (/salir, /voz, etc.) solo "
                        "estan disponibles desde el PC, senor.",
                    )
                    continue
                should_continue = cmd_handler.handle(user_input)
                if not should_continue:
                    break
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # FAST PATH: Intentar ejecutar comando rapido sin IA
            handled, fast_response = fast_cmd.try_execute(user_input)
            if handled:
                memory.add_message("user", user_input)
                memory.add_message("assistant", fast_response)
                reply(fast_response, source, chat_id, as_voice=is_voice_input)
                if source != "telegram":
                    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # INTERNET PATH: Si necesita info actual, buscar en DuckDuckGo + resumir con IA
            if needs_internet(user_input):
                memory.add_message("user", user_input)

                console.print("")
                with Live(
                    Spinner("dots", text="[cyan] Buscando en internet...[/cyan]", style="cyan"),
                    console=console,
                    transient=True,
                ):
                    response = provider_manager.search_and_answer(user_input)

                if response:
                    clean_response, _ = tool_executor.process_response(response)
                    memory.add_message("assistant", clean_response)
                    reply(clean_response, source, chat_id, header="internet", as_voice=is_voice_input)
                    if source != "telegram":
                        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                    continue
                else:
                    # No se pudo buscar, avisar y dejar que Ollama intente solo
                    memory.messages.pop()
                    console.print(f"\n  [yellow]No pude buscar en internet. Intentare responder con lo que se.[/yellow]")

            # SLOW PATH: Enviar a la IA
            memory.add_message("user", user_input)

            console.print("")
            with Live(
                Spinner("dots", text="[cyan] Procesando...[/cyan]", style="cyan"),
                console=console,
                transient=True,
            ):
                try:
                    response = provider_manager.chat(
                        memory.get_context_messages(),
                        system_prompt,
                    )
                except ConnectionError as e:
                    console.print(f"[bold red]Error: {e}[/bold red]")
                    memory.messages.pop()
                    if source == "telegram":
                        telegram_io.send_reply(chat_id, f"Error: {e}")
                    else:
                        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                    continue
                except Exception as e:
                    console.print(f"[bold red]Error inesperado: {e}[/bold red]")
                    memory.messages.pop()
                    if source == "telegram":
                        telegram_io.send_reply(chat_id, f"Error inesperado: {e}")
                    else:
                        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                    continue

            # Ejecutar herramientas si la IA las solicito
            clean_response, tool_results = tool_executor.process_response(response)

            memory.add_message("assistant", clean_response)
            reply(clean_response, source, chat_id, header=provider_manager.current_provider_name, as_voice=is_voice_input)

            if source != "telegram":
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")

        except KeyboardInterrupt:
            break

    # Cleanup
    stop_event.set()
    if mic_available:
        stt.stop_listening()
    if telegram_active:
        telegram_io.stop()
    memory.save_session()
    console.print(f"\n[bold cyan]Hasta luego, senor. Estare aqui cuando me necesite.[/bold cyan]\n")


if __name__ == "__main__":
    main()
