"""
Motor RAG (Retrieval-Augmented Generation) para Jarvis.

Usa ChromaDB como vector store con embeddings locales (all-MiniLM-L6-v2 via
ONNX, incluido con ChromaDB). No necesita APIs externas, GPU ni Ollama.
Toda la persistencia vive en data/knowledge/.
"""

import hashlib
import logging
import os
from pathlib import Path

log = logging.getLogger("jarvis.knowledge.rag")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "knowledge",
)

_COLLECTION_NAME = "jarvis_knowledge"


class RAGEngine:
    """Interfaz sobre ChromaDB para almacenar y consultar fragmentos de texto."""

    def __init__(self, persist_dir: str | None = None):
        self._persist_dir = persist_dir or _DATA_DIR
        self._client = None
        self._collection = None
        self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def initialize(self) -> bool:
        """Inicializa ChromaDB. Devuelve False si chromadb no esta instalado."""
        try:
            import chromadb
        except ImportError:
            log.debug("chromadb no instalado, RAG deshabilitado")
            return False

        os.makedirs(self._persist_dir, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            count = self._collection.count()
            log.info("RAG inicializado (%d fragmentos en knowledge base)", count)
            self._available = True
            return True
        except Exception as e:
            log.error("Error inicializando ChromaDB: %s", e)
            return False

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def add_chunks(
        self,
        chunks: list[str],
        source_name: str,
        metadata: dict | None = None,
    ) -> int:
        """
        Almacena una lista de fragmentos de texto asociados a un documento.
        Devuelve la cantidad de fragmentos nuevos almacenados.
        """
        if not self._available or not chunks:
            return 0

        base_meta = {"source": source_name}
        if metadata:
            base_meta.update(metadata)

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = self._make_id(source_name, i)
            meta = {**base_meta, "chunk_index": i}
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(meta)

        try:
            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            log.info("Almacenados %d fragmentos de '%s'", len(ids), source_name)
            return len(ids)
        except Exception as e:
            log.error("Error almacenando chunks: %s", e)
            return 0

    def remove_source(self, source_name: str) -> int:
        """Elimina todos los fragmentos de un documento por nombre."""
        if not self._available:
            return 0

        try:
            results = self._collection.get(
                where={"source": source_name},
            )
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                log.info("Eliminados %d fragmentos de '%s'", len(results["ids"]), source_name)
                return len(results["ids"])
            return 0
        except Exception as e:
            log.error("Error eliminando source '%s': %s", source_name, e)
            return 0

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def query(self, question: str, top_k: int = 5, min_score: float = 0.25) -> list[dict]:
        """
        Busca fragmentos relevantes para una pregunta.

        Devuelve lista de dicts con keys: text, source, score, chunk_index.
        Solo devuelve resultados con score >= min_score (cosine similarity).
        """
        if not self._available or not question.strip():
            return []

        if self._collection.count() == 0:
            return []

        effective_k = min(top_k, self._collection.count())

        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=effective_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            log.error("Error en query RAG: %s", e)
            return []

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB con cosine devuelve distancia (0 = identico, 2 = opuesto).
            # Convertimos a similaridad: 1 - dist/2
            score = 1.0 - (dist / 2.0)
            if score >= min_score:
                hits.append({
                    "text": doc,
                    "source": meta.get("source", "?"),
                    "score": round(score, 3),
                    "chunk_index": meta.get("chunk_index", -1),
                })

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def list_sources(self) -> list[dict]:
        """Lista todos los documentos en la knowledge base con sus conteos."""
        if not self._available or self._collection.count() == 0:
            return []

        try:
            all_data = self._collection.get(include=["metadatas"])
            sources = {}
            for meta in all_data["metadatas"]:
                src = meta.get("source", "?")
                sources[src] = sources.get(src, 0) + 1
            return [
                {"name": name, "chunks": count}
                for name, count in sorted(sources.items())
            ]
        except Exception as e:
            log.error("Error listando sources: %s", e)
            return []

    @property
    def total_chunks(self) -> int:
        if not self._available:
            return 0
        return self._collection.count()

    @staticmethod
    def _make_id(source: str, index: int) -> str:
        h = hashlib.md5(source.encode()).hexdigest()[:12]
        return f"{h}_{index}"
