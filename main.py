#!/usr/bin/env python3
"""
JARVIS - Asistente de Inteligencia Artificial Personal
Inspirado en JARVIS de Iron Man.

Uso: python main.py
"""

import sys
import os

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from config import Config
from ai_providers import ProviderManager
from voice import VoiceEngine, SpeechToText
from memory import ConversationMemory
from utils import CommandHandler

console = Console()

PROMPT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", ".prompt_history")

BANNER = r"""
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""

PROMPT_STYLE = Style.from_dict({
    "prompt": "#00d4ff bold",
})


def display_banner():
    banner_text = Text(BANNER, style="bold cyan")
    panel = Panel(
        banner_text,
        subtitle="[dim]Escribe /ayuda para ver comandos[/dim]",
        border_style="cyan",
    )
    console.print(panel)


def display_init_status():
    console.print("\n[bold cyan]Inicializando sistemas...[/bold cyan]")


def get_user_input(stt: SpeechToText) -> str:
    os.makedirs(os.path.dirname(PROMPT_HISTORY_FILE), exist_ok=True)

    try:
        # Si el modo escucha esta activo, mostrar indicador
        if stt.is_enabled:
            user_input = prompt(
                [("class:prompt", f"\n  {Config.ASSISTANT_NAME} [MIC] > ")],
                style=PROMPT_STYLE,
                history=FileHistory(PROMPT_HISTORY_FILE),
            )
            user_input = user_input.strip()

            # Si presiona Enter sin escribir nada, escuchar microfono
            if not user_input:
                heard = stt.listen()
                if heard:
                    return heard
                return ""

            return user_input
        else:
            user_input = prompt(
                [("class:prompt", f"\n  {Config.ASSISTANT_NAME} > ")],
                style=PROMPT_STYLE,
                history=FileHistory(PROMPT_HISTORY_FILE),
            )
            return user_input.strip()

    except (EOFError, KeyboardInterrupt):
        return "/salir"


def display_thinking():
    return Live(
        Spinner("dots", text="[cyan] Procesando...[/cyan]", style="cyan"),
        console=console,
        transient=True,
    )


def display_response(text: str, provider_name: str):
    panel = Panel(
        text,
        title=f"[bold cyan]{Config.ASSISTANT_NAME}[/bold cyan] [dim]({provider_name})[/dim]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def main():
    display_banner()
    display_init_status()

    # Inicializar componentes
    provider_manager = ProviderManager()
    if not provider_manager.initialize():
        sys.exit(1)

    voice_engine = VoiceEngine()
    voice_engine.initialize()

    stt = SpeechToText()
    mic_available = stt.initialize()

    memory = ConversationMemory()
    cmd_handler = CommandHandler(provider_manager, voice_engine, memory, stt)

    console.print("[bold green]\n  Sistemas en linea. Listo para servir, senor.[/bold green]")

    if mic_available:
        console.print("[dim]  Escribe /mic para activar el microfono[/dim]\n")
    else:
        console.print("[dim]  Microfono no disponible. Modo solo texto.\n[/dim]")

    # Loop principal
    while True:
        try:
            user_input = get_user_input(stt)

            if not user_input:
                continue

            # Manejar comandos
            if cmd_handler.is_command(user_input):
                should_continue = cmd_handler.handle(user_input)
                if not should_continue:
                    break
                continue

            # Agregar mensaje del usuario a memoria
            memory.add_message("user", user_input)

            # Obtener respuesta de la IA
            with display_thinking():
                try:
                    response = provider_manager.chat(
                        memory.get_context_messages(),
                        Config.SYSTEM_PROMPT,
                    )
                except ConnectionError as e:
                    console.print(f"\n[bold red]Error: {e}[/bold red]")
                    console.print("[yellow]Verifica tu conexion a internet y las API keys.[/yellow]")
                    memory.messages.pop()
                    continue
                except Exception as e:
                    console.print(f"\n[bold red]Error inesperado: {e}[/bold red]")
                    memory.messages.pop()
                    continue

            # Guardar respuesta en memoria
            memory.add_message("assistant", response)

            # Mostrar respuesta
            display_response(response, provider_manager.current_provider_name)

            # Hablar la respuesta
            voice_engine.speak(response)

        except KeyboardInterrupt:
            console.print("\n")
            memory.save_session()
            console.print(f"\n[bold cyan]Sesion interrumpida. Hasta pronto, senor.[/bold cyan]\n")
            break

    memory.save_session()


if __name__ == "__main__":
    main()
