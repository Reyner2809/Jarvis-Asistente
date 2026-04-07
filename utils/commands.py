from rich.console import Console
from rich.table import Table

console = Console()


class CommandHandler:
    """Maneja comandos especiales del usuario (empiezan con /)."""

    def __init__(self, provider_manager, voice_engine, memory):
        self._provider = provider_manager
        self._voice = voice_engine
        self._memory = memory

    def is_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    def handle(self, text: str) -> bool:
        """Procesa un comando. Retorna False si debe salir del programa."""
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        commands = {
            "/salir": self._cmd_exit,
            "/exit": self._cmd_exit,
            "/quit": self._cmd_exit,
            "/voz": self._cmd_voice_toggle,
            "/voice": self._cmd_voice_toggle,
            "/provider": self._cmd_switch_provider,
            "/proveedor": self._cmd_switch_provider,
            "/clear": self._cmd_clear,
            "/limpiar": self._cmd_clear,
            "/status": self._cmd_status,
            "/estado": self._cmd_status,
            "/help": self._cmd_help,
            "/ayuda": self._cmd_help,
        }

        handler = commands.get(cmd)
        if handler:
            return handler(args)

        console.print(f"[yellow]Comando desconocido: {cmd}. Escribe /ayuda para ver comandos.[/yellow]")
        return True

    def _cmd_exit(self, args: str) -> bool:
        self._memory.save_session()
        console.print(f"\n[bold cyan]Hasta luego, senor. Estare aqui cuando me necesite.[/bold cyan]\n")
        return False

    def _cmd_voice_toggle(self, args: str) -> bool:
        self._voice.toggle()
        return True

    def _cmd_switch_provider(self, args: str) -> bool:
        if not args:
            console.print(f"[cyan]Proveedor actual: {self._provider.current_provider_name.upper()}[/cyan]")
            console.print("[dim]Uso: /proveedor <claude|openai|gemini>[/dim]")
        else:
            self._provider.switch_provider(args.strip())
        return True

    def _cmd_clear(self, args: str) -> bool:
        self._memory.clear()
        console.print("[green]Conversacion limpiada.[/green]")
        return True

    def _cmd_status(self, args: str) -> bool:
        stats = self._memory.get_stats()

        table = Table(title="Estado de JARVIS", show_header=False, border_style="cyan")
        table.add_column("Campo", style="bold cyan")
        table.add_column("Valor", style="white")
        table.add_row("Proveedor IA", self._provider.current_provider_name.upper())
        table.add_row("Voz", "Activada" if self._voice.is_enabled else "Desactivada")
        table.add_row("Mensajes (sesion)", str(stats["total"]))
        table.add_row("Tuyos", str(stats["user"]))
        table.add_row("Mios", str(stats["assistant"]))
        table.add_row("Sesion iniciada", stats["session_start"][:19])
        console.print(table)
        return True

    def _cmd_help(self, args: str) -> bool:
        table = Table(title="Comandos disponibles", border_style="cyan")
        table.add_column("Comando", style="bold green")
        table.add_column("Descripcion", style="white")
        table.add_row("/ayuda, /help", "Muestra esta ayuda")
        table.add_row("/voz, /voice", "Activa/desactiva la voz")
        table.add_row("/proveedor <nombre>", "Cambia el proveedor de IA (claude, openai, gemini)")
        table.add_row("/estado, /status", "Muestra el estado actual")
        table.add_row("/limpiar, /clear", "Limpia la conversacion")
        table.add_row("/salir, /exit", "Sale del programa")
        console.print(table)
        return True
