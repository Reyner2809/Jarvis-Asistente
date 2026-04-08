"""Busqueda web usando DuckDuckGo (gratis, sin API key, sin limites)."""

import re
from ddgs import DDGS

# Patrones que indican que el usuario quiere noticias
_NEWS_RE = re.compile(
    r"noticia|noticias|que\s+(?:esta|está)\s+pasando|"
    r"que\s+(?:ha|hay)\s+pasado|actualidad|ultima\s+hora|últim",
    re.IGNORECASE,
)


def search_internet(query: str, max_results: int = 5) -> str | None:
    """Busca en internet y devuelve los resultados como texto para la IA."""
    try:
        ddgs = DDGS()

        # Si parece que busca noticias, usar el endpoint de noticias
        if _NEWS_RE.search(query):
            results = list(ddgs.news(query, region="es-es", max_results=max_results))
            lines = []
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                body = r.get("body", "")
                date = r.get("date", "")
                source = r.get("source", "")
                lines.append(f"{i}. [{source}] {title}: {body} ({date})")
        else:
            results = list(ddgs.text(query, region="es-es", max_results=max_results))
            lines = []
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                body = r.get("body", "")
                lines.append(f"{i}. {title}: {body}")

        if not results:
            return None

        return "\n".join(lines)

    except Exception:
        return None
