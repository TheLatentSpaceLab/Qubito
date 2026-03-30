from __future__ import annotations

import faiss
import numpy as np
import hashlib
import re
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from src.genai.client import AIClient
from src.genai.providers import Provider

if TYPE_CHECKING:
    from src.agents.agent import Agent

logger = getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    path: str
    chunk_id: int
    score: float
    text: str


class FaissDocumentStore:

    def __init__(
        self,
        embedding_model: str,
        embedding_provider: str,
        dim: int = 384,
        chunk_size_words: int = 220,
        chunk_overlap_words: int = 40,
        namespace: str | None = None,
    ):
        """
        Initialize the FAISS document store, optionally namespaced to disk.

        Parameters
        ----------
        embedding_model : str
            Embedding model identifier used by the selected provider. If empty,
            a provider-specific default is used.
        embedding_provider : str
            Embedding backend name (``ollama`` or ``gemini``).
        dim : int, optional
            Embedding dimension used for all vectors in the FAISS index.
            Default is ``384``.
        chunk_size_words : int, optional
            Maximum number of words per chunk when splitting document text.
            Default is ``220``.
        chunk_overlap_words : int, optional
            Number of overlapping words between consecutive chunks.
            Default is ``40``.
        namespace : str or None, optional
            If set, the index is persisted to ``~/.qubito/memory/{namespace}/``.
            When None, the store is purely in-memory.
        """

        self.embedding_model = embedding_model
        self.embedding_provider = embedding_provider
        if not self.embedding_model:
            self.embedding_model = self._default_embedding_model()

        self.dim = dim
        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words
        self._namespace = namespace
        self._store_dir: Path | None = None

        if namespace:
            self._store_dir = Path.home() / ".qubito" / "memory" / namespace
            self._store_dir.mkdir(parents=True, exist_ok=True)

        self.index = faiss.IndexFlatIP(dim)
        self._chunks: list[dict[str, str | int]] = []
        self._documents: dict[str, str] = {}

        self._load_from_disk()

        self.embedding_agent: AIClient = self._init_embedding_agent()
        self._embedding_warning_logged = False

    def _init_embedding_agent(self) -> AIClient:
        """
        Create the embedding client for the configured provider.

        Returns
        -------
        AIClient
            Provider-specific client implementing ``embed``.

        Raises
        ------
        ValueError
            If ``embedding_provider`` is unsupported.
        """
        if self.embedding_provider == Provider.OLLAMA:
            from src.genai.clients.ollama import get_ollama_client
            return get_ollama_client()
        if self.embedding_provider == Provider.GEMINI:
            from src.genai.clients.gemini import get_gemini_client
            return get_gemini_client()
        raise ValueError(
            f"Unsupported embedding provider: {self.embedding_provider}. "
            "Use 'ollama' or 'gemini'."
        )

    def _load_from_disk(self) -> None:
        """Load a previously persisted FAISS index and chunk metadata."""
        if not self._store_dir:
            return
        index_path = self._store_dir / "index.faiss"
        meta_path = self._store_dir / "chunks.json"
        if index_path.exists() and meta_path.exists():
            try:
                import json
                self.index = faiss.read_index(str(index_path))
                data = json.loads(meta_path.read_text())
                self._chunks = data.get("chunks", [])
                self._documents = data.get("documents", {})
                logger.info("Loaded FAISS index from %s (%d chunks)", self._store_dir, len(self._chunks))
            except Exception:
                logger.warning("Failed to load FAISS index from %s", self._store_dir, exc_info=True)

    def _save_to_disk(self) -> None:
        """Persist the FAISS index and chunk metadata to disk."""
        if not self._store_dir:
            return
        try:
            import json
            faiss.write_index(self.index, str(self._store_dir / "index.faiss"))
            (self._store_dir / "chunks.json").write_text(json.dumps({
                "chunks": self._chunks,
                "documents": self._documents,
            }))
        except Exception:
            logger.warning("Failed to save FAISS index to %s", self._store_dir, exc_info=True)

    def add_document(self, path: str | Path, content: str) -> tuple[str, int]:
        """
        Add a new document to the store and index its chunks.

        Parameters
        ----------
        path : str | Path
            Path to the source document. It is resolved to an absolute path.
        content : str
            Raw textual content to chunk and embed.

        Returns
        -------
        tuple[str, int]
            A tuple ``(doc_id, chunk_count)`` where ``doc_id`` is the generated
            UUID for the document and ``chunk_count`` is the number of chunks
            indexed in FAISS.
        """

        doc_id = str(uuid4())
        abs_path = str(Path(path).resolve())
        self._documents[doc_id] = abs_path

        chunk_texts = self._compute_document_chunks(
            content=content,
            doc_id=doc_id,
            doc_path=abs_path,
        )
        embeddings = self._embed_texts(texts=chunk_texts)
        self.index.add(embeddings)
        self._save_to_disk()

        return doc_id, len(chunk_texts)

    def _compute_document_chunks(self, content: str, doc_id: str, doc_path: str) -> list[str]:
        """
        Compute and register chunks for a document.

        Parameters
        ----------
        content : str
            Input document text to segment.
        doc_id : str
            Document identifier generated for the current document.
        doc_path : str
            Absolute path of the source document.

        Returns
        -------
        list[str]
            List of chunks. If no chunk is produced by normal chunking, returns
            a single-item list containing ``content.strip()``.
        """

        chunk_texts = self._chunk_text(content)
        if not chunk_texts:
            chunk_texts = [content.strip()]

        for idx, chunk_text in enumerate(chunk_texts):
            self._chunks.append(
                {
                    "doc_id": doc_id,
                    "path": doc_path,
                    "chunk_id": idx,
                    "text": chunk_text,
                }
            )

        return chunk_texts

    def search(
        self,
        query: str,
        k: int = 3,
        min_score: float = 0.01,
    ) -> list[RetrievedChunk]:
        """
        Search indexed chunks by semantic similarity to a query.

        Parameters
        ----------
        query : str
            Query text used to retrieve relevant chunks.
        k : int, optional
            Maximum number of results to return before score filtering.
            Default is ``3``.
        min_score : float, optional
            Minimum similarity score required for a chunk to be included.
            Default is ``0.01``.

        Returns
        -------
        list[RetrievedChunk]
            Ranked list of retrieved chunks. Each item includes source path,
            chunk id, score, and chunk text. Returns an empty list for blank
            queries or when the index has no vectors.
        """

        if not query.strip() or self.index.ntotal == 0:
            return []

        q = self._embed_texts(texts=[query])
        k_eff = min(k, self.index.ntotal)
        scores, indices = self.index.search(q, k_eff)

        results: list[RetrievedChunk] = []
        for raw_score, raw_idx in zip(scores[0], indices[0]):
            idx = int(raw_idx)
            if idx < 0:
                continue
            score = float(raw_score)
            if score < min_score:
                continue

            chunk = self._chunks[idx]
            results.append(
                RetrievedChunk(
                    path=str(chunk["path"]),
                    chunk_id=int(chunk["chunk_id"]),
                    score=score,
                    text=str(chunk["text"]),
                )
            )
        return results

    def get_context_view(self, max_chunks: int = 20, preview_chars: int = 280) -> list[dict[str, str | int]]:
        """
        Build a lightweight view of recently indexed chunks.

        Parameters
        ----------
        max_chunks : int, optional
            Maximum number of latest chunks to include. Default is ``20``.
        preview_chars : int, optional
            Maximum number of characters in each chunk preview. Default is
            ``280``.

        Returns
        -------
        list[dict[str, str | int]]
            List of dictionaries with keys ``path``, ``chunk_id``, and
            ``preview``.
        """

        if not self._chunks:
            return []

        selected = self._chunks[-max_chunks:]
        view = []
        for item in selected:
            text = str(item["text"]).strip().replace("\n", " ")
            view.append(
                {
                    "path": str(item["path"]),
                    "chunk_id": int(item["chunk_id"]),
                    "preview": text[:preview_chars],
                }
            )
        return view

    def stats(self) -> dict[str, int]:
        """
        Return aggregate counts of indexed content.

        Parameters
        ----------
        None
            This method does not receive arguments besides ``self``.

        Returns
        -------
        dict[str, int]
            Dictionary containing total ``documents`` and total ``chunks``.
        """

        return {
            "documents": len(self._documents),
            "chunks": len(self._chunks),
        }

    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks based on word count.

        Parameters
        ----------
        text : str
            Raw text to divide into chunks.

        Returns
        -------
        list[str]
            Ordered list of chunks with up to ``self.chunk_size_words`` words
            and overlap controlled by ``self.chunk_overlap_words``.
        """

        words = text.split()
        if not words:
            return []

        if len(words) <= self.chunk_size_words:
            return [" ".join(words)]

        step = max(1, self.chunk_size_words - self.chunk_overlap_words)
        chunks: list[str] = []
        for start in range(0, len(words), step):
            end = start + self.chunk_size_words
            chunk = " ".join(words[start:end]).strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(words):
                break
        return chunks

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings through the active agent AI client.

        Parameters
        ----------
        texts : list[str]
            Text strings to encode into vectors.

        Returns
        -------
        numpy.ndarray
            ``float32`` matrix with shape ``(len(texts), self.dim)``. Vectors
            are normalized and aligned to the index dimension. If client-side
            embedding fails, hash-based embeddings are used as fallback.
        """

        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        try:
            matrix = self.embedding_agent.embed(
                model=self.embedding_model,
                texts=texts,
            )
            return self._prepare_embedding_matrix(matrix)
        except Exception:
            self._log_embedding_fallback()
            return self._embed_texts_hash(texts)

    def _prepare_embedding_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """
        Normalize and align embedding matrix to FAISS index dimension.

        Parameters
        ----------
        matrix : numpy.ndarray
            Raw embedding matrix returned by the provider client.

        Returns
        -------
        numpy.ndarray
            ``float32`` matrix with shape ``(n, self.dim)`` and L2-normalized
            rows.

        Raises
        ------
        ValueError
            If input matrix is not two-dimensional.
        """
        if matrix.ndim != 2:
            raise ValueError("Expected a 2D embedding matrix")

        current_dim = matrix.shape[1]
        if current_dim > self.dim:
            matrix = matrix[:, : self.dim]
        elif current_dim < self.dim:
            padding = np.zeros((matrix.shape[0], self.dim - current_dim), dtype=np.float32)
            matrix = np.concatenate([matrix, padding], axis=1)

        matrix = matrix.astype(np.float32, copy=False)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _embed_texts_hash(self, texts: list[str]) -> np.ndarray:
        """
        Build deterministic hash embeddings as local fallback.

        Parameters
        ----------
        texts : list[str]
            Input texts to embed.

        Returns
        -------
        numpy.ndarray
            ``float32`` normalized matrix with shape ``(len(texts), self.dim)``.
        """
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)

        for row_idx, text in enumerate(texts):
            tokens = re.findall(r"\w+", text.lower())
            if not tokens:
                continue

            for token in tokens:
                token_bytes = token.encode("utf-8")
                digest = hashlib.blake2b(token_bytes, digest_size=8).digest()
                raw = int.from_bytes(digest, "big", signed=False)
                dim_idx = raw % self.dim
                sign = -1.0 if ((raw >> 1) & 1) else 1.0
                matrix[row_idx, dim_idx] += sign

            norm = np.linalg.norm(matrix[row_idx])
            if norm > 0:
                matrix[row_idx] /= norm

        return matrix

    def _default_embedding_model(self) -> str:
        """
        Return default embedding model for current provider.

        Returns
        -------
        str
            Provider-specific default embedding model name.
        """
        if self.embedding_provider == Provider.OLLAMA:
            return "nomic-embed-text"
        if self.embedding_provider == Provider.GEMINI:
            return "text-embedding-004"
        return ""

    def _log_embedding_fallback(self) -> None:
        """
        Log fallback warning once when provider embedding fails.

        Returns
        -------
        None
            Writes a warning log once per store instance.
        """
        if self._embedding_warning_logged:
            return
        logger.warning(
            "Embedding provider '%s' failed. Falling back to local hash embeddings.",
            self.embedding_provider,
        )
        self._embedding_warning_logged = True
