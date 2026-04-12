"""
Memoria de largo plazo del usuario — persistente en JSON.

Almacena hechos personales (nombre, gustos, contactos, datos importantes)
que sobreviven entre sesiones y reinicios del PC. Inspirado en el sistema
de memoria de OpenClaw (archivos persistentes + busqueda).

Archivo: data/user_memory.json
"""

import json
import logging
import os
import re
from datetime import datetime

log = logging.getLogger("jarvis.memory.user")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)
_MEMORY_FILE = os.path.join(_DATA_DIR, "user_memory.json")


# ---------------------------------------------------------------------------
# Patrones para extraccion automatica de hechos
# ---------------------------------------------------------------------------

_EXTRACTION_PATTERNS = [
    # Nombre
    (r"(?:me\s+llamo|mi\s+nombre\s+es|soy)\s+([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)*)", "personal",
     lambda m: f"El nombre del usuario es {m.group(1)}"),

    # Cumpleaños
    (r"(?:mi\s+cumplea[ñn]os?\s+es|cumplo\s+a[ñn]os?)\s+(?:el\s+)?(.+?)(?:\.|$)",
     "personal", lambda m: f"El cumpleaños del usuario es el {m.group(1).strip()}"),

    # Edad
    (r"(?:tengo|mi\s+edad\s+es)\s+(\d+)\s+(?:años|anos)", "personal",
     lambda m: f"El usuario tiene {m.group(1)} años"),

    # Profesion / trabajo
    (r"(?:trabajo\s+(?:como|de|en)\s+|soy\s+(?:un\s+|una\s+)?)((?:desarrollador|ingenier|programador|diseñador|profesor|estudiante|medic|abogad|contador|architect|gerente|analista|vendedor)\w*(?:\s+\w+){0,3})",
     "profesion", lambda m: f"El usuario trabaja como {m.group(1).strip()}"),

    # Ubicacion
    (r"(?:vivo\s+en|soy\s+de|estoy\s+en)\s+([A-Z][a-záéíóúñ]+(?:\s+[A-Za-záéíóúñ]+)*)",
     "ubicacion", lambda m: f"El usuario vive en {m.group(1)}"),

    # Favoritos genericos
    (r"mi\s+(?:cancion|canción)\s+favorita\s+(?:es|se\s+llama)\s+(.+?)(?:\.|$)",
     "preferencia", lambda m: f"La canción favorita del usuario es {m.group(1).strip()}"),
    (r"mi\s+(?:artista|cantante|banda|grupo)\s+favorit[oa]\s+(?:es|se\s+llama)\s+(.+?)(?:\.|$)",
     "preferencia", lambda m: f"El artista favorito del usuario es {m.group(1).strip()}"),
    (r"mi\s+(?:pelicula|película|serie|show)\s+favorit[oa]\s+(?:es|se\s+llama)\s+(.+?)(?:\.|$)",
     "preferencia", lambda m: f"La película/serie favorita del usuario es {m.group(1).strip()}"),
    (r"mi\s+(?:comida|plato)\s+favorit[oa]\s+(?:es|se\s+llama)\s+(.+?)(?:\.|$)",
     "preferencia", lambda m: f"La comida favorita del usuario es {m.group(1).strip()}"),
    (r"mi\s+color\s+favorito\s+es\s+(?:el\s+)?(\w+)",
     "preferencia", lambda m: f"El color favorito del usuario es {m.group(1)}"),

    # Generico: "mi X favorito es Y"
    (r"mi\s+(\w+)\s+favorit[oa]\s+(?:es|se\s+llama)\s+(.+?)(?:\.|$)",
     "preferencia", lambda m: f"El/La {m.group(1)} favorito/a del usuario es {m.group(2).strip()}"),

    # Recuerda que... (explicito)
    (r"(?:recuerda\s+que|acuerdate\s+(?:de\s+)?que|no\s+olvides\s+que|ten\s+en\s+cuenta\s+que)\s+(.+?)(?:\.|$)",
     "nota", lambda m: m.group(1).strip()),

    # Contactos: "X es mi amigo/hermano/jefe"
    (r"([A-Z][a-záéíóúñ]+)\s+es\s+mi\s+(amig[oa]|herman[oa]|mam[aá]|pap[aá]|padre|madre|novi[oa]|espos[oa]|jefe|compañer[oa]|socio)",
     "contacto", lambda m: f"{m.group(1)} es {m.group(2)} del usuario"),

    # Email
    (r"mi\s+(?:correo|email|mail)\s+es\s+([\w.+-]+@[\w-]+\.[\w.]+)",
     "personal", lambda m: f"El correo/email del usuario es {m.group(1)}"),

    # Telefono
    (r"mi\s+(?:numero|número|telefono|teléfono|cel|celular)\s+es\s+([\d\s+-]+)",
     "personal", lambda m: f"El teléfono del usuario es {m.group(1).strip()}"),
]

_compiled_patterns = [
    (re.compile(p, re.IGNORECASE), cat, fn)
    for p, cat, fn in _EXTRACTION_PATTERNS
]


class UserMemory:
    """Memoria persistente del usuario en JSON."""

    def __init__(self, memory_file: str | None = None):
        self._file = memory_file or _MEMORY_FILE
        self._facts: list[dict] = []
        self._loaded = False

    def initialize(self) -> bool:
        os.makedirs(os.path.dirname(self._file), exist_ok=True)
        self._load()
        self._loaded = True
        log.info("Memoria del usuario: %d recuerdos cargados", len(self._facts))
        return True

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def remember(self, fact: str, category: str = "general") -> bool:
        """Guarda un hecho. Evita duplicados por texto similar."""
        fact = fact.strip()
        if not fact:
            return False

        # Evitar duplicados: si ya existe un hecho muy similar, actualizarlo
        fact_lower = fact.lower()
        for existing in self._facts:
            if self._similar(existing["text"].lower(), fact_lower):
                existing["text"] = fact
                existing["date"] = datetime.now().isoformat()[:10]
                existing["category"] = category
                self._save()
                return True

        self._facts.append({
            "text": fact,
            "category": category,
            "date": datetime.now().isoformat()[:10],
        })
        self._save()
        return True

    def recall(self, query: str, top_k: int = 10) -> list[dict]:
        """Busca recuerdos relevantes por keywords."""
        if not self._facts:
            return []

        query_words = set(query.lower().split())
        scored = []
        for fact in self._facts:
            fact_words = set(fact["text"].lower().split())
            overlap = len(query_words & fact_words)
            if overlap > 0:
                scored.append((overlap, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:top_k]]

    def recall_all(self) -> list[dict]:
        """Devuelve todos los recuerdos."""
        return list(self._facts)

    def forget(self, index: int) -> bool:
        """Elimina un recuerdo por indice (0-based)."""
        if 0 <= index < len(self._facts):
            self._facts.pop(index)
            self._save()
            return True
        return False

    def forget_by_text(self, search: str) -> int:
        """Elimina recuerdos que contengan el texto dado. Devuelve cantidad eliminada."""
        search_lower = search.lower()
        before = len(self._facts)
        self._facts = [f for f in self._facts if search_lower not in f["text"].lower()]
        removed = before - len(self._facts)
        if removed > 0:
            self._save()
        return removed

    @property
    def count(self) -> int:
        return len(self._facts)

    # ------------------------------------------------------------------
    # Extraccion automatica de hechos
    # ------------------------------------------------------------------

    def extract_facts(self, user_input: str) -> list[str]:
        """
        Analiza el input del usuario y extrae hechos personales automaticamente.
        Devuelve lista de hechos extraidos (ya guardados).
        Evita duplicados: si un patron especifico ya capturo un substring,
        el generico no lo repite.
        """
        extracted = []
        matched_spans = set()
        for pattern, category, fact_fn in _compiled_patterns:
            match = pattern.search(user_input)
            if match:
                span = (match.start(), match.end())
                # Evitar que el generico repita lo que un especifico ya capturo
                if any(s[0] <= span[0] and s[1] >= span[1] for s in matched_spans):
                    continue
                if any(span[0] <= s[0] and span[1] >= s[1] for s in matched_spans):
                    continue
                fact_text = fact_fn(match)
                if fact_text and len(fact_text) > 5:
                    self.remember(fact_text, category)
                    extracted.append(fact_text)
                    matched_spans.add(span)
        return extracted

    # ------------------------------------------------------------------
    # Contexto para la IA
    # ------------------------------------------------------------------

    def build_context(self, query: str = "") -> str | None:
        """
        Construye bloque de texto con los recuerdos del usuario para inyectar
        en el prompt de la IA.
        """
        if not self._facts:
            return None

        # Siempre incluir todos los hechos (son pocos, <5KB)
        lines = ["MEMORIA DEL USUARIO (hechos que ya conoces sobre el):"]
        for f in self._facts:
            lines.append(f"- {f['text']}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._facts = data.get("facts", [])
            except (json.JSONDecodeError, KeyError):
                self._facts = []
        else:
            self._facts = []

    def _save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump({"facts": self._facts}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _similar(a: str, b: str) -> bool:
        """Detecta si dos hechos son esencialmente el mismo (para evitar duplicados)."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b)
        min_len = min(len(words_a), len(words_b))
        return overlap / min_len > 0.7
