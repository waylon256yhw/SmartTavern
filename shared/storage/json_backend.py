"""JSON file-system backend — wraps existing directory-per-entity layout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.atomic_write import atomic_write_json

from .base import CatalogStore, ConversationStore

# entity_type → JSON filename inside each entity subfolder
_ENTITY_JSON: dict[str, str] = {
    "presets": "preset.json",
    "world_books": "worldbook.json",
    "characters": "character.json",
    "personas": "persona.json",
    "regex_rules": "regex_rule.json",
    "llm_configs": "llm_config.json",
}


def _safe_read_json(p: Path) -> dict[str, Any] | None:
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class JsonCatalogStore(CatalogStore):
    """File-system catalog store — one directory per entity, JSON file inside."""

    def __init__(self, data_root: Path | str):
        self._root = Path(data_root)

    def _entity_dir(self, entity_type: str) -> Path:
        return self._root / entity_type

    def _json_filename(self, entity_type: str) -> str:
        return _ENTITY_JSON.get(entity_type, f"{entity_type.rstrip('s')}.json")

    def list_items(self, entity_type: str) -> list[dict[str, Any]]:
        folder = self._entity_dir(entity_type)
        if not folder.is_dir():
            return []
        json_name = self._json_filename(entity_type)
        items: list[dict[str, Any]] = []
        for sub in sorted(folder.iterdir()):
            if not sub.is_dir():
                continue
            p = sub / json_name
            if not p.exists():
                continue
            doc = _safe_read_json(p)
            if doc is None:
                continue
            item: dict[str, Any] = {
                "name": doc.get("name", sub.name),
                "folder_name": sub.name,
                "file": f"{entity_type}/{sub.name}",
            }
            if "description" in doc:
                item["description"] = doc["description"]
            icon = sub / "icon.png"
            if icon.exists():
                item["icon_path"] = icon.relative_to(self._root.parent.parent).as_posix()
            items.append(item)
        return items

    def get_item(self, entity_type: str, name: str) -> dict[str, Any] | None:
        folder = self._entity_dir(entity_type) / name
        p = folder / self._json_filename(entity_type)
        return _safe_read_json(p)

    def save_item(self, entity_type: str, name: str, data: dict[str, Any]) -> None:
        folder = self._entity_dir(entity_type) / name
        folder.mkdir(parents=True, exist_ok=True)
        p = folder / self._json_filename(entity_type)
        atomic_write_json(p, data)

    def delete_item(self, entity_type: str, name: str) -> bool:
        import shutil

        folder = self._entity_dir(entity_type) / name
        if not folder.is_dir():
            return False
        shutil.rmtree(folder)
        return True


class JsonConversationStore(ConversationStore):
    """File-system conversation store — one directory per conversation."""

    def __init__(self, data_root: Path | str):
        self._root = Path(data_root) / "conversations"

    def _conv_dir(self, conversation_id: str) -> Path:
        return self._root / conversation_id

    def load_doc(self, conversation_id: str) -> dict[str, Any] | None:
        p = self._conv_dir(conversation_id) / "conversation.json"
        return _safe_read_json(p)

    def save_doc(self, conversation_id: str, doc: dict[str, Any]) -> None:
        d = self._conv_dir(conversation_id)
        d.mkdir(parents=True, exist_ok=True)
        atomic_write_json(d / "conversation.json", doc)

    def load_settings(self, conversation_id: str) -> dict[str, Any]:
        p = self._conv_dir(conversation_id) / "settings.json"
        return _safe_read_json(p) or {}

    def save_settings(self, conversation_id: str, settings: dict[str, Any]) -> None:
        d = self._conv_dir(conversation_id)
        d.mkdir(parents=True, exist_ok=True)
        atomic_write_json(d / "settings.json", settings)

    def load_variables(self, conversation_id: str) -> dict[str, Any]:
        p = self._conv_dir(conversation_id) / "variables.json"
        return _safe_read_json(p) or {}

    def save_variables(self, conversation_id: str, variables: dict[str, Any]) -> None:
        d = self._conv_dir(conversation_id)
        d.mkdir(parents=True, exist_ok=True)
        atomic_write_json(d / "variables.json", variables)
