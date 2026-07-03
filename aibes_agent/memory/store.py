"""Memory storage abstraction for long-term agent memory."""

from __future__ import annotations

import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class MemoryStore(ABC):
    """Abstract long-term memory store."""

    @abstractmethod
    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a memory and return its id."""
        ...

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """Search memories matching *query*."""
        ...

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Delete a memory by id. Return True if it existed."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Delete all memories."""
        ...


class InMemoryMemoryStore(MemoryStore):
    """Simple in-memory memory store using keyword overlap scoring.

    This implementation has no external dependencies and is suitable for
    testing and small-scale use. For semantic search, use ``ChromaMemoryStore``.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, MemoryEntry] = {}

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"\b\w+\b", text.lower()))

    @staticmethod
    def _score(query: str, text: str) -> float:
        query_tokens = InMemoryMemoryStore._tokens(query)
        text_tokens = InMemoryMemoryStore._tokens(text)
        if not query_tokens:
            return 0.0
        overlap = len(query_tokens & text_tokens)
        return overlap / len(query_tokens)

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry_id = str(uuid.uuid4())
        self._entries[entry_id] = MemoryEntry(
            id=entry_id,
            text=text,
            metadata=metadata or {},
        )
        return entry_id

    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        scored = []
        for entry in self._entries.values():
            score = self._score(query, entry.text)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def delete(self, entry_id: str) -> bool:
        if entry_id not in self._entries:
            return False
        del self._entries[entry_id]
        return True

    def clear(self) -> None:
        self._entries.clear()


class ChromaMemoryStore(MemoryStore):
    """ChromaDB-backed vector memory store (requires ``chromadb``)."""

    def __init__(
        self,
        collection_name: str = "aibes_memory",
        persist_directory: Optional[str] = None,
        embedding_function: Optional[Any] = None,
    ) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "ChromaMemoryStore requires 'chromadb'. Install with: pip install aibes-agent[chroma]"
            ) from exc

        self._client = (
            chromadb.PersistentClient(path=persist_directory)
            if persist_directory
            else chromadb.Client()
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
        )

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry_id = str(uuid.uuid4())
        self._collection.add(
            ids=[entry_id],
            documents=[text],
            metadatas=[metadata or {}],
        )
        return entry_id

    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        results = self._collection.query(query_texts=[query], n_results=top_k)
        entries: List[MemoryEntry] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for i, entry_id in enumerate(ids):
            entries.append(
                MemoryEntry(
                    id=entry_id,
                    text=documents[i] if i < len(documents) else "",
                    metadata=metadatas[i] if i < len(metadatas) else {},
                )
            )
        return entries

    def delete(self, entry_id: str) -> bool:
        try:
            self._collection.delete(ids=[entry_id])
            return True
        except Exception:
            return False

    def clear(self) -> None:
        self._collection.delete(where={"$ne": {"id": ""}})
