"""Parametric contract tests — any CatalogStore / ConversationStore backend must pass."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.storage.base import CatalogStore, ConversationStore
from shared.storage.json_backend import JsonCatalogStore, JsonConversationStore
from shared.storage.sqlite_backend import SqliteCatalogStore, SqliteConversationStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(params=["json", "sqlite"])
def catalog_store(request, tmp_path: Path) -> CatalogStore:
    data_root = tmp_path / "data"
    data_root.mkdir()
    if request.param == "json":
        return JsonCatalogStore(data_root)
    if request.param == "sqlite":
        return SqliteCatalogStore(tmp_path / "test.db")
    raise ValueError(f"Unknown backend: {request.param}")


@pytest.fixture(params=["json", "sqlite"])
def conversation_store(request, tmp_path: Path) -> ConversationStore:
    data_root = tmp_path / "data"
    data_root.mkdir()
    if request.param == "json":
        return JsonConversationStore(data_root)
    if request.param == "sqlite":
        return SqliteConversationStore(tmp_path / "test.db")
    raise ValueError(f"Unknown backend: {request.param}")


# ---------------------------------------------------------------------------
# CatalogStore contracts
# ---------------------------------------------------------------------------


class TestCatalogStoreContract:
    def test_list_empty(self, catalog_store: CatalogStore):
        assert catalog_store.list_items("presets") == []

    def test_save_and_get(self, catalog_store: CatalogStore):
        data = {"name": "TestPreset", "description": "A test", "content": {"key": "val"}}
        catalog_store.save_item("presets", "TestPreset", data)
        got = catalog_store.get_item("presets", "TestPreset")
        assert got is not None
        assert got["name"] == "TestPreset"
        assert got["content"] == {"key": "val"}

    def test_save_list_roundtrip(self, catalog_store: CatalogStore):
        catalog_store.save_item("presets", "A", {"name": "A"})
        catalog_store.save_item("presets", "B", {"name": "B"})
        items = catalog_store.list_items("presets")
        names = sorted(i["name"] for i in items)
        assert names == ["A", "B"]

    def test_delete(self, catalog_store: CatalogStore):
        catalog_store.save_item("presets", "ToDelete", {"name": "ToDelete"})
        assert catalog_store.delete_item("presets", "ToDelete") is True
        assert catalog_store.get_item("presets", "ToDelete") is None

    def test_delete_nonexistent(self, catalog_store: CatalogStore):
        assert catalog_store.delete_item("presets", "Ghost") is False

    def test_get_nonexistent(self, catalog_store: CatalogStore):
        assert catalog_store.get_item("presets", "Ghost") is None

    def test_overwrite(self, catalog_store: CatalogStore):
        catalog_store.save_item("presets", "X", {"name": "X", "v": 1})
        catalog_store.save_item("presets", "X", {"name": "X", "v": 2})
        got = catalog_store.get_item("presets", "X")
        assert got is not None
        assert got["v"] == 2

    def test_multiple_entity_types(self, catalog_store: CatalogStore):
        catalog_store.save_item("presets", "A", {"name": "A"})
        catalog_store.save_item("characters", "B", {"name": "B"})
        assert len(catalog_store.list_items("presets")) == 1
        assert len(catalog_store.list_items("characters")) == 1


# ---------------------------------------------------------------------------
# ConversationStore contracts
# ---------------------------------------------------------------------------


class TestConversationStoreContract:
    SAMPLE_DOC = {
        "name": "Test Conversation",
        "description": "A test",
        "updated_at": "2026-01-01T00:00:00+08:00",
        "roots": ["n1"],
        "nodes": {
            "n1": {"pid": None, "role": "system", "content": "hello"},
            "n2": {"pid": "n1", "role": "user", "content": "hi"},
        },
        "children": {"n1": ["n2"]},
        "active_path": ["n1", "n2"],
    }

    def test_load_nonexistent(self, conversation_store: ConversationStore):
        assert conversation_store.load_doc("ghost") is None

    def test_save_load_doc(self, conversation_store: ConversationStore):
        conversation_store.save_doc("conv1", self.SAMPLE_DOC)
        got = conversation_store.load_doc("conv1")
        assert got is not None
        assert got["roots"] == ["n1"]
        assert "n2" in got["nodes"]

    def test_settings_roundtrip(self, conversation_store: ConversationStore):
        assert conversation_store.load_settings("conv1") == {}
        settings = {"character_file": "chars/Foo/character.json", "preset": "default"}
        conversation_store.save_settings("conv1", settings)
        got = conversation_store.load_settings("conv1")
        assert got["character_file"] == "chars/Foo/character.json"

    def test_variables_roundtrip(self, conversation_store: ConversationStore):
        assert conversation_store.load_variables("conv1") == {}
        variables = {"score": 42, "nested": {"a": 1}}
        conversation_store.save_variables("conv1", variables)
        got = conversation_store.load_variables("conv1")
        assert got["score"] == 42
        assert got["nested"]["a"] == 1

    def test_overwrite_doc(self, conversation_store: ConversationStore):
        conversation_store.save_doc("conv1", {"roots": ["a"], "nodes": {}, "children": {}, "active_path": []})
        conversation_store.save_doc("conv1", self.SAMPLE_DOC)
        got = conversation_store.load_doc("conv1")
        assert got is not None
        assert got["roots"] == ["n1"]

    def test_independent_conversations(self, conversation_store: ConversationStore):
        conversation_store.save_settings("c1", {"k": 1})
        conversation_store.save_settings("c2", {"k": 2})
        assert conversation_store.load_settings("c1")["k"] == 1
        assert conversation_store.load_settings("c2")["k"] == 2

    def test_metadata_preserved(self, conversation_store: ConversationStore):
        conversation_store.save_doc("conv_meta", self.SAMPLE_DOC)
        got = conversation_store.load_doc("conv_meta")
        assert got is not None
        assert got["name"] == "Test Conversation"
        assert got["description"] == "A test"
        assert got["updated_at"] == "2026-01-01T00:00:00+08:00"
        assert got["roots"] == ["n1"]
        assert got["nodes"]["n2"]["content"] == "hi"

    def test_children_order_preserved(self, conversation_store: ConversationStore):
        doc = {
            "roots": ["n1"],
            "nodes": {
                "n1": {"pid": None, "role": "system", "content": "root"},
                "n2": {"pid": "n1", "role": "user", "content": "second"},
                "n3": {"pid": "n1", "role": "user", "content": "first"},
                "n4": {"pid": "n1", "role": "user", "content": "third"},
            },
            "children": {"n1": ["n3", "n2", "n4"]},
            "active_path": ["n1", "n3"],
        }
        conversation_store.save_doc("conv_order", doc)
        got = conversation_store.load_doc("conv_order")
        assert got is not None
        assert got["children"]["n1"] == ["n3", "n2", "n4"]
