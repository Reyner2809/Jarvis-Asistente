import base64
import json
import os
import urllib.request
import urllib.error
from .base import AIProvider
from config import Config


class OllamaProvider(AIProvider):
    """Proveedor local usando Ollama. Gratis, sin API key, sin limites.

    Si el modelo principal (OLLAMA_MODEL, ej gemma4:e4b) falla, cae
    automaticamente al modelo fallback (OLLAMA_FALLBACK_MODEL, ej llama3.2).
    """

    def __init__(self):
        self._base_url = "http://localhost:11434"
        self._active_model = None

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _get_models_to_try(self) -> list[str]:
        """Devuelve lista de modelos a intentar: principal + fallback."""
        models = [Config.OLLAMA_MODEL]
        fb = Config.OLLAMA_FALLBACK_MODEL
        if fb and fb != Config.OLLAMA_MODEL:
            models.append(fb)
        return models

    def _call_chat(self, messages: list, model: str, timeout: int = 120, stream_callback=None) -> str:
        """
        Llamada a Ollama /api/chat con retry automatico.
        Si Ollama da 500 (model swap), espera y reintenta una vez.
        """
        import time as _time
        use_stream = stream_callback is not None
        max_retries = 2

        for attempt in range(max_retries):
            payload = json.dumps({
                "model": model,
                "messages": messages,
                "stream": use_stream,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if not use_stream:
                        data = json.loads(resp.read().decode("utf-8"))
                        return data["message"]["content"]

                    full_response = []
                    for line in resp:
                        line = line.decode("utf-8").strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_response.append(token)
                            stream_callback(token)
                        if chunk.get("done", False):
                            break

                    return "".join(full_response)

            except urllib.error.HTTPError as e:
                if e.code == 500 and attempt < max_retries - 1:
                    _time.sleep(5)
                    continue
                raise

    def chat(self, messages: list, system_prompt: str, stream_callback=None) -> str:
        ollama_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        last_error = None
        for model in self._get_models_to_try():
            try:
                result = self._call_chat(ollama_messages, model, stream_callback=stream_callback)
                if self._active_model != model:
                    self._active_model = model
                return result
            except Exception as e:
                last_error = e
                from rich.console import Console
                Console().print(f"  [yellow]Ollama ({model}) fallo: {e}. Intentando siguiente...[/yellow]")
                continue

        raise last_error or ConnectionError("Ningun modelo de Ollama respondio")

    def agent_chat(
        self,
        messages: list,
        system_prompt: str,
        tools_schema: list[dict],
        execute_fn=None,
        max_steps: int = 5,
        on_tool_call=None,
        stream_callback=None,
    ) -> str:
        """
        Agent Loop estilo OpenClaw: el LLM puede llamar tools, recibir
        resultados, y seguir razonando hasta dar una respuesta final.

        Flujo:
          1. Enviar mensajes + tools a Ollama
          2. Si respuesta tiene tool_calls → ejecutar → agregar resultado → loop
          3. Si respuesta es solo texto → FIN
          4. Maximo max_steps iteraciones

        Args:
            messages: historial de conversacion
            system_prompt: system prompt
            tools_schema: lista de tools en formato Ollama JSON schema
            execute_fn: funcion(tool_name, arguments) -> dict con resultado
            max_steps: maximo de ciclos tool-call (proteccion anti-loop)
            on_tool_call: callback(step, tool_name, args) para mostrar progreso
            stream_callback: callback(token) para streaming en el paso final
        """
        from tools.executor import execute_tool_call

        if execute_fn is None:
            execute_fn = execute_tool_call

        ollama_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            ollama_messages.append({"role": msg["role"], "content": msg["content"]})

        last_error = None
        for model in self._get_models_to_try():
            try:
                return self._agent_loop(
                    ollama_messages, model, tools_schema,
                    execute_fn, max_steps, on_tool_call, stream_callback,
                )
            except Exception as e:
                last_error = e
                from rich.console import Console
                Console().print(f"  [yellow]Ollama ({model}) fallo: {e}. Intentando siguiente...[/yellow]")
                continue

        raise last_error or ConnectionError("Ningun modelo de Ollama respondio")

    def _agent_loop(
        self, messages, model, tools_schema, execute_fn, max_steps,
        on_tool_call, stream_callback,
    ) -> str:
        """Loop interno del agente."""

        for step in range(max_steps):
            is_last_possible_step = (step == max_steps - 1)

            # En el ultimo paso posible, no pasar tools para forzar respuesta texto
            current_tools = [] if is_last_possible_step else tools_schema

            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
            }
            if current_tools:
                payload["tools"] = current_tools

            raw = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=raw,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls")
            content = msg.get("content", "")

            # Si no hay tool_calls, es la respuesta final
            if not tool_calls:
                if self._active_model != model:
                    self._active_model = model
                return content

            # Ejecutar cada tool call
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                arguments = fn.get("arguments", {})

                if on_tool_call:
                    on_tool_call(step + 1, tool_name, arguments)

                result = execute_fn(tool_name, arguments)
                result_text = result.get("message", str(result))

                messages.append({
                    "role": "tool",
                    "content": result_text,
                })

        # Si llegamos aqui, se agotaron los pasos. Forzar respuesta final.
        if self._active_model != model:
            self._active_model = model
        return content or "Alcance el limite de pasos. Aqui esta lo que logre hasta ahora."

    def _unload_model(self, model: str):
        """Descarga un modelo de la RAM de Ollama para liberar memoria."""
        try:
            payload = json.dumps({
                "model": model,
                "keep_alive": 0,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self._base_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    def analyze_image(self, image_path: str, prompt: str = "") -> str:
        """
        Analiza una imagen usando el modelo de vision (OLLAMA_VISION_MODEL).
        Usa un modelo dedicado (gemma4:e4b) separado del modelo de chat
        (llama3.2) para no sacrificar velocidad en conversacion normal.
        """
        if not os.path.exists(image_path):
            return f"Archivo no encontrado: {image_path}"

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        if not prompt:
            prompt = (
                "Analyze this image carefully. "
                "If there is text in the image, read it EXACTLY as written (do NOT translate or change the language). "
                "If it's a screenshot of a chat, transcribe the messages exactly. "
                "If it's a receipt or document, extract the exact numbers and text. "
                "If it's a photo, describe what you see. "
                "IMPORTANT: Respond in Spanish (but keep any text from the image in its original language)."
            )

        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ]

        # Intentar con el modelo de vision primero, luego fallback
        vision_model = Config.OLLAMA_VISION_MODEL
        models_to_try = [vision_model]
        if Config.OLLAMA_MODEL != vision_model:
            models_to_try.append(Config.OLLAMA_MODEL)

        last_error = None
        used_model = None
        for model in models_to_try:
            try:
                used_model = model
                result = self._call_chat(messages, model, timeout=180)
                return result
            except Exception as e:
                last_error = e
                continue
            finally:
                if used_model:
                    self._unload_model(used_model)

        return f"No pude analizar la imagen: {last_error}"
