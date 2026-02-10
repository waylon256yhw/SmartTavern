"""Storage abstraction layer — thin adapters over file/database backends."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import CatalogStore, ConversationStore

_BACKEND = os.environ.get("STORAGE_BACKEND", "json")

_catalog_store: CatalogStore | None = None
_conversation_store: ConversationStore | None = None


def get_catalog_store(data_root: Path | str | None = None) -> CatalogStore:
    """Get or create the global CatalogStore singleton."""
    global _catalog_store
    if _catalog_store is not None:
        return _catalog_store
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "backend_projects" / "SmartTavern" / "data"
    _catalog_store = _make_catalog_store(data_root)
    return _catalog_store


def get_conversation_store(data_root: Path | str | None = None) -> ConversationStore:
    """Get or create the global ConversationStore singleton."""
    global _conversation_store
    if _conversation_store is not None:
        return _conversation_store
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "backend_projects" / "SmartTavern" / "data"
    _conversation_store = _make_conversation_store(data_root)
    return _conversation_store


def _make_catalog_store(data_root: Path | str) -> CatalogStore:
    if _BACKEND == "sqlite":
        from .sqlite_backend import SqliteCatalogStore

        db_path = Path(data_root) / "smarttavern.db"
        return SqliteCatalogStore(db_path)
    if _BACKEND == "json":
        from .json_backend import JsonCatalogStore

        return JsonCatalogStore(data_root)
    raise ValueError(f"Unknown STORAGE_BACKEND: {_BACKEND!r} (expected 'json' or 'sqlite')")


def _make_conversation_store(data_root: Path | str) -> ConversationStore:
    if _BACKEND == "sqlite":
        from .sqlite_backend import SqliteConversationStore

        db_path = Path(data_root) / "smarttavern.db"
        return SqliteConversationStore(db_path)
    if _BACKEND == "json":
        from .json_backend import JsonConversationStore

        return JsonConversationStore(data_root)
    raise ValueError(f"Unknown STORAGE_BACKEND: {_BACKEND!r} (expected 'json' or 'sqlite')")


def get_storage_backend() -> str:
    return _BACKEND


__all__ = [
    "CatalogStore",
    "ConversationStore",
    "get_catalog_store",
    "get_conversation_store",
    "get_storage_backend",
]
