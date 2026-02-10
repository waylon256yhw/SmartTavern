"""Abstract store interfaces for catalog entities and conversations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CatalogStore(ABC):
    """Thin adapter for catalog entity CRUD (presets, characters, personas, etc.)."""

    @abstractmethod
    def list_items(self, entity_type: str) -> list[dict[str, Any]]:
        """Return list of item summaries for *entity_type*.

        Each dict contains at minimum: ``name``, ``folder_name``,
        ``file`` (``{entity_type}/{folder_name}``),
        and optionally ``description``, ``icon_path``.
        """

    @abstractmethod
    def get_item(self, entity_type: str, name: str) -> dict[str, Any] | None:
        """Return full item data or ``None`` if not found."""

    @abstractmethod
    def save_item(self, entity_type: str, name: str, data: dict[str, Any]) -> None:
        """Create or overwrite an item."""

    @abstractmethod
    def delete_item(self, entity_type: str, name: str) -> bool:
        """Delete an item. Return ``True`` if it existed."""


class ConversationStore(ABC):
    """Thin adapter for conversation tree + per-conversation settings/variables."""

    @abstractmethod
    def load_doc(self, conversation_id: str) -> dict[str, Any] | None:
        """Load the full conversation document (roots, nodes, children, active_path).

        Return ``None`` if conversation doesn't exist.
        """

    @abstractmethod
    def save_doc(self, conversation_id: str, doc: dict[str, Any]) -> None:
        """Persist the full conversation document."""

    @abstractmethod
    def load_settings(self, conversation_id: str) -> dict[str, Any]:
        """Load per-conversation settings. Return empty dict if none."""

    @abstractmethod
    def save_settings(self, conversation_id: str, settings: dict[str, Any]) -> None:
        """Persist per-conversation settings."""

    @abstractmethod
    def load_variables(self, conversation_id: str) -> dict[str, Any]:
        """Load per-conversation context variables. Return empty dict if none."""

    @abstractmethod
    def save_variables(self, conversation_id: str, variables: dict[str, Any]) -> None:
        """Persist per-conversation context variables."""
