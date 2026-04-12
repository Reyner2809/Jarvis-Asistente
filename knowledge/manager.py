"""
KnowledgeManager: API de alto nivel para el sistema RAG de Jarvis.

Junta document_loader (extraccion + chunking) con rag_engine (ChromaDB).
Es el punto de entrada que usan main.py, telegram_io, y el executor.
"""

import logging
import os
from pathlib import Path

from . import document_loader
from .rag_engine import RAGEngine

log = logging.getLogger("jarvis.knowledge.manager")


class KnowledgeManager:

    def __init__(self):
        self._engine = RAGEngine()
        self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def initialize(self) -> bool:
        """Intenta inicializar el RAG engine. False si chromadb no esta instalado."""
        ok = self._engine.initialize()
        self._available = ok
        return ok

    # ------------------------------------------------------------------
    # Gestion de documentos
    # ------------------------------------------------------------------

    def add_document(self, file_path: str, chunk_size: int = 500, overlap: int = 50) -> dict:
        """
        Carga un documento al knowledge base.
        Devuelve {"success": bool, "message": str, "chunks": int}.
        """
        if not self._available:
            return {"success": False, "message": "RAG no disponible. Instala chromadb: pip install chromadb", "chunks": 0}

        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            return {"success": False, "message": f"Archivo no encontrado: {file_path}", "chunks": 0}

        if not document_loader.is_supported(file_path):
            ext = Path(file_path).suffix
            return {"success": False, "message": f"Formato '{ext}' no soportado. Formatos validos: PDF, DOCX, TXT, CSV, MD, y archivos de codigo.", "chunks": 0}

        source_name = Path(file_path).name

        try:
            chunks = document_loader.load_and_chunk(file_path, chunk_size, overlap)
        except ImportError as e:
            return {"success": False, "message": str(e), "chunks": 0}
        except Exception as e:
            return {"success": False, "message": f"Error leyendo el archivo: {e}", "chunks": 0}

        if not chunks:
            return {"success": False, "message": "El archivo esta vacio o no se pudo extraer texto.", "chunks": 0}

        # Si ya existia, reemplazar
        self._engine.remove_source(source_name)

        stored = self._engine.add_chunks(
            chunks,
            source_name=source_name,
            metadata={"file_path": file_path},
        )

        return {
            "success": True,
            "message": f"'{source_name}' procesado: {stored} fragmentos almacenados.",
            "chunks": stored,
        }

    def add_text(self, text: str, source_name: str, chunk_size: int = 500, overlap: int = 50) -> dict:
        """Carga texto libre (no desde archivo) al knowledge base."""
        if not self._available:
            return {"success": False, "message": "RAG no disponible.", "chunks": 0}

        chunks = document_loader.chunk_text(text, chunk_size, overlap)
        if not chunks:
            return {"success": False, "message": "Texto vacio.", "chunks": 0}

        self._engine.remove_source(source_name)
        stored = self._engine.add_chunks(chunks, source_name=source_name)

        return {
            "success": True,
            "message": f"'{source_name}' almacenado: {stored} fragmentos.",
            "chunks": stored,
        }

    def remove_document(self, source_name: str) -> dict:
        """Elimina un documento de la knowledge base por nombre."""
        if not self._available:
            return {"success": False, "message": "RAG no disponible."}

        removed = self._engine.remove_source(source_name)
        if removed > 0:
            return {"success": True, "message": f"'{source_name}' eliminado ({removed} fragmentos)."}
        return {"success": False, "message": f"No encontre '{source_name}' en la base de conocimiento."}

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """
        Busca fragmentos relevantes. Devuelve lista de hits con text, source, score.
        """
        if not self._available:
            return []
        return self._engine.query(question, top_k=top_k)

    def build_context(self, question: str, top_k: int = 5) -> str | None:
        """
        Busca y formatea fragmentos como contexto inyectable en el prompt de la IA.
        Devuelve None si no hay resultados relevantes.
        """
        hits = self.query(question, top_k=top_k)
        if not hits:
            return None

        lines = ["CONTEXTO DE TU BASE DE CONOCIMIENTO (usa esta informacion para responder):"]
        seen_sources = set()
        for h in hits:
            src = h["source"]
            if src not in seen_sources:
                lines.append(f"\n--- Fuente: {src} (relevancia: {h['score']:.0%}) ---")
                seen_sources.add(src)
            lines.append(h["text"])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Listado
    # ------------------------------------------------------------------

    def get_all_content(self, source_name: str | None = None, max_chunks: int = 20) -> str | None:
        """
        Devuelve todo el contenido de un documento (o del mas reciente si
        source_name es None). Util para meta-queries tipo 'resumeme el documento'.
        """
        if not self._available:
            return None

        docs = self.list_documents()
        if not docs:
            return None

        target = source_name
        if target is None:
            target = docs[-1]["name"]

        try:
            results = self._engine._collection.get(
                where={"source": target},
                include=["documents", "metadatas"],
            )
        except Exception:
            return None

        if not results["documents"]:
            return None

        # Ordenar por chunk_index
        pairs = sorted(
            zip(results["documents"], results["metadatas"]),
            key=lambda p: p[1].get("chunk_index", 0),
        )

        chunks = [doc for doc, _ in pairs[:max_chunks]]
        if not chunks:
            return None

        return (
            f"CONTENIDO DEL DOCUMENTO '{target}':\n\n"
            + "\n\n".join(chunks)
        )

    def list_documents(self) -> list[dict]:
        """Lista todos los documentos almacenados con conteos."""
        if not self._available:
            return []
        return self._engine.list_sources()

    @property
    def total_chunks(self) -> int:
        if not self._available:
            return 0
        return self._engine.total_chunks
