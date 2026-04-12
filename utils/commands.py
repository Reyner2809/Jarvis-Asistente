from rich.console import Console
from rich.table import Table

console = Console()


class CommandHandler:
    """Maneja comandos especiales del usuario (empiezan con /)."""

    def __init__(self, provider_manager, voice_engine, memory, stt=None, knowledge=None, user_memory=None):
        self._provider = provider_manager
        self._voice = voice_engine
        self._memory = memory
        self._stt = stt
        self._knowledge = knowledge
        self._user_memory = user_memory
        self._image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

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
            "/mic": self._cmd_mic_toggle,
            "/microfono": self._cmd_mic_toggle,
            "/provider": self._cmd_switch_provider,
            "/proveedor": self._cmd_switch_provider,
            "/clear": self._cmd_clear,
            "/limpiar": self._cmd_clear,
            "/status": self._cmd_status,
            "/estado": self._cmd_status,
            "/help": self._cmd_help,
            "/ayuda": self._cmd_help,
            "/cargar": self._cmd_load_knowledge,
            "/load": self._cmd_load_knowledge,
            "/conocimiento": self._cmd_list_knowledge,
            "/knowledge": self._cmd_list_knowledge,
            "/olvidar": self._cmd_forget_knowledge,
            "/forget": self._cmd_forget_knowledge,
            "/analizar": self._cmd_analyze_image,
            "/analyze": self._cmd_analyze_image,
            "/memoria": self._cmd_list_memory,
            "/memory": self._cmd_list_memory,
            "/olvidar_memoria": self._cmd_forget_memory,
            "/recordatorios": self._cmd_list_reminders,
            "/reminders": self._cmd_list_reminders,
            "/cancelar_recordatorio": self._cmd_cancel_reminder,
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

    def _cmd_mic_toggle(self, args: str) -> bool:
        if self._stt is None:
            console.print("[red]El reconocimiento de voz no esta disponible.[/red]")
            return True
        if self._stt.is_enabled:
            self._stt.stop_listening()
            console.print("[cyan]Microfono desactivado.[/cyan]")
        else:
            self._stt.start_listening()
        return True

    def _cmd_switch_provider(self, args: str) -> bool:
        if not args:
            console.print(f"[cyan]Proveedor actual: {self._provider.current_provider_name.upper()}[/cyan]")
            console.print("[dim]Uso: /proveedor <claude|openai|gemini|ollama>[/dim]")
        else:
            self._provider.switch_provider(args.strip())
        return True

    def _cmd_clear(self, args: str) -> bool:
        self._memory.clear()
        console.print("[green]Conversacion limpiada.[/green]")
        return True

    def _cmd_status(self, args: str) -> bool:
        stats = self._memory.get_stats()
        mic_status = "No disponible"
        if self._stt and self._stt.is_available:
            mic_status = "Escuchando" if self._stt.is_enabled else "Desactivado"

        table = Table(title="Estado de JARVIS", show_header=False, border_style="cyan")
        table.add_column("Campo", style="bold cyan")
        table.add_column("Valor", style="white")
        table.add_row("Proveedor IA", self._provider.current_provider_name.upper())
        table.add_row("Voz (respuesta)", "Activada" if self._voice.is_enabled else "Desactivada")
        table.add_row("Microfono", mic_status)
        table.add_row("Mensajes (sesion)", str(stats["total"]))
        table.add_row("Tuyos", str(stats["user"]))
        table.add_row("Mios", str(stats["assistant"]))
        table.add_row("Sesion iniciada", stats["session_start"][:19])
        console.print(table)
        return True

    # ------------------------------------------------------------------
    # Recordatorios (scheduler)
    # ------------------------------------------------------------------

    def _cmd_list_reminders(self, args: str) -> bool:
        if not hasattr(self, '_scheduler') or not self._scheduler:
            console.print("[yellow]Scheduler no disponible.[/yellow]")
            return True

        tasks = self._scheduler.list_tasks()
        if not tasks:
            console.print("[dim]No hay recordatorios pendientes.[/dim]")
            return True

        table = Table(title="Recordatorios Programados", border_style="cyan")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Proxima", style="cyan", width=18)
        table.add_column("Mensaje", style="white")
        table.add_column("Tipo", style="dim", width=12)
        for t in tasks:
            repeat = t.get("repeat")
            tipo = "una vez"
            if repeat:
                tipo = {
                    "daily": "diario",
                    "weekly": "semanal",
                    "hourly": "cada hora",
                    "every": f"cada {repeat.get('minutes','')}min",
                }.get(repeat.get("type", ""), "recurrente")
            table.add_row(t["id"], t["run_at"][:16], t["message"], tipo)
        console.print(table)
        return True

    def _cmd_cancel_reminder(self, args: str) -> bool:
        if not hasattr(self, '_scheduler') or not self._scheduler:
            console.print("[yellow]Scheduler no disponible.[/yellow]")
            return True
        if not args:
            console.print("[yellow]Uso: /cancelar_recordatorio <ID>[/yellow]")
            console.print("[dim]Usa /recordatorios para ver los IDs.[/dim]")
            return True

        if self._scheduler.remove_task(args.strip()):
            console.print(f"[green]Recordatorio '{args.strip()}' cancelado.[/green]")
        else:
            console.print(f"[red]No encontre recordatorio con ID '{args.strip()}'.[/red]")
        return True

    # ------------------------------------------------------------------
    # Memoria del usuario (largo plazo)
    # ------------------------------------------------------------------

    def _cmd_list_memory(self, args: str) -> bool:
        if not self._user_memory:
            console.print("[yellow]Memoria de usuario no disponible.[/yellow]")
            return True

        facts = self._user_memory.recall_all()
        if not facts:
            console.print("[dim]No tengo recuerdos guardados todavia. Dime cosas sobre ti.[/dim]")
            return True

        table = Table(title="Memoria del Usuario", border_style="cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Recuerdo", style="white")
        table.add_column("Tipo", style="cyan", width=12)
        table.add_column("Fecha", style="dim", width=12)
        for i, fact in enumerate(facts):
            table.add_row(str(i), fact["text"], fact.get("category", ""), fact.get("date", ""))
        console.print(table)
        console.print(f"[dim]Total: {len(facts)} recuerdos. Usa /olvidar_memoria <texto> para eliminar.[/dim]")
        return True

    def _cmd_forget_memory(self, args: str) -> bool:
        if not self._user_memory:
            console.print("[yellow]Memoria de usuario no disponible.[/yellow]")
            return True
        if not args:
            console.print("[yellow]Uso: /olvidar_memoria <texto a buscar>[/yellow]")
            return True

        removed = self._user_memory.forget_by_text(args.strip())
        if removed > 0:
            console.print(f"[green]Eliminados {removed} recuerdo(s) que contenian '{args.strip()}'.[/green]")
        else:
            console.print(f"[red]No encontre recuerdos con '{args.strip()}'.[/red]")
        return True

    # ------------------------------------------------------------------
    # Vision (analisis de imagenes)
    # ------------------------------------------------------------------

    def _cmd_analyze_image(self, args: str) -> bool:
        if not args:
            console.print("[yellow]Uso: /analizar <ruta_a_la_imagen> [pregunta opcional][/yellow]")
            console.print("[dim]Formatos: JPG, PNG, GIF, BMP, WEBP[/dim]")
            return True

        import os
        from pathlib import Path

        parts = args.strip().split(maxsplit=1)
        file_path = parts[0].strip('"').strip("'")
        prompt = parts[1] if len(parts) > 1 else ""

        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            console.print(f"[red]Archivo no encontrado: {file_path}[/red]")
            return True

        ext = Path(file_path).suffix.lower()
        if ext not in self._image_extensions:
            console.print(f"[red]Formato '{ext}' no soportado para analisis visual.[/red]")
            return True

        if self._provider is None:
            console.print("[red]No hay proveedor de IA disponible.[/red]")
            return True

        console.print(f"[cyan]Analizando imagen '{Path(file_path).name}'...[/cyan]")
        result = self._provider.analyze_image(file_path, prompt)
        if result:
            from rich.panel import Panel
            console.print(Panel(result, title="[bold cyan]Analisis de imagen[/bold cyan]", border_style="cyan"))
        else:
            console.print("[red]No pude analizar la imagen. Verifica que el modelo soporta vision (gemma4, llava).[/red]")
        return True

    # ------------------------------------------------------------------
    # Knowledge (RAG)
    # ------------------------------------------------------------------

    def _cmd_load_knowledge(self, args: str) -> bool:
        if not self._knowledge or not self._knowledge.is_available:
            console.print("[yellow]RAG no disponible. Instala chromadb: pip install chromadb[/yellow]")
            return True
        if not args:
            console.print("[yellow]Uso: /cargar <ruta_al_archivo>[/yellow]")
            console.print("[dim]Formatos: PDF, DOCX, TXT, CSV, MD, archivos de codigo[/dim]")
            return True

        import os
        file_path = args.strip().strip('"').strip("'")
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        console.print(f"[cyan]Procesando '{os.path.basename(file_path)}'...[/cyan]")
        result = self._knowledge.add_document(file_path)
        if result["success"]:
            console.print(f"[green]{result['message']}[/green]")
        else:
            console.print(f"[red]{result['message']}[/red]")
        return True

    def _cmd_list_knowledge(self, args: str) -> bool:
        if not self._knowledge or not self._knowledge.is_available:
            console.print("[yellow]RAG no disponible. Instala chromadb: pip install chromadb[/yellow]")
            return True

        docs = self._knowledge.list_documents()
        if not docs:
            console.print("[dim]La base de conocimiento esta vacia. Usa /cargar <archivo> para agregar documentos.[/dim]")
            return True

        table = Table(title="Base de Conocimiento", border_style="cyan")
        table.add_column("Documento", style="bold green")
        table.add_column("Fragmentos", style="white", justify="right")
        for doc in docs:
            table.add_row(doc["name"], str(doc["chunks"]))
        table.add_row("", "")
        table.add_row("[bold]Total[/bold]", f"[bold]{self._knowledge.total_chunks}[/bold]")
        console.print(table)
        return True

    def _cmd_forget_knowledge(self, args: str) -> bool:
        if not self._knowledge or not self._knowledge.is_available:
            console.print("[yellow]RAG no disponible.[/yellow]")
            return True
        if not args:
            console.print("[yellow]Uso: /olvidar <nombre_del_documento>[/yellow]")
            console.print("[dim]Usa /conocimiento para ver los documentos cargados.[/dim]")
            return True

        result = self._knowledge.remove_document(args.strip())
        if result["success"]:
            console.print(f"[green]{result['message']}[/green]")
        else:
            console.print(f"[red]{result['message']}[/red]")
        return True

    def _cmd_help(self, args: str) -> bool:
        table = Table(title="Comandos disponibles", border_style="cyan")
        table.add_column("Comando", style="bold green")
        table.add_column("Descripcion", style="white")
        table.add_row("/ayuda, /help", "Muestra esta ayuda")
        table.add_row("/mic, /microfono", "Activa/desactiva el microfono")
        table.add_row("/voz, /voice", "Activa/desactiva la voz de respuesta")
        table.add_row("/proveedor <nombre>", "Cambia el proveedor de IA (claude, openai, gemini, ollama)")
        table.add_row("/estado, /status", "Muestra el estado actual")
        table.add_row("/limpiar, /clear", "Limpia la conversacion")
        table.add_row("/recordatorios", "Muestra recordatorios programados")
        table.add_row("/cancelar_recordatorio <ID>", "Cancela un recordatorio por ID")
        table.add_row("/memoria", "Muestra los recuerdos guardados sobre ti")
        table.add_row("/olvidar_memoria <texto>", "Elimina recuerdos que contengan ese texto")
        table.add_row("/analizar <imagen>", "Analiza una imagen con IA vision (JPG, PNG, etc.)")
        table.add_row("/cargar <archivo>", "Carga un documento a la base de conocimiento (RAG)")
        table.add_row("/conocimiento", "Lista los documentos en la base de conocimiento")
        table.add_row("/olvidar <nombre>", "Elimina un documento de la base de conocimiento")
        table.add_row("/salir, /exit", "Sale del programa")
        console.print(table)
        console.print("\n[dim]Con el mic activo: presiona Enter sin texto para que escuche tu voz.[/dim]")
        return True
