"""SQLite storage backend."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .base import CatalogStore, ConversationStore

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"

# Top-level conversation doc keys that are stored relationally (not in metadata)
_CONVERSATION_STRUCTURAL_KEYS = {"roots", "nodes", "children", "active_path"}


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = _SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema)
    # Add metadata column if upgrading from older schema
    try:
        conn.execute("SELECT metadata FROM conversations LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE conversations ADD COLUMN metadata JSON")
    # Add sibling_order column if upgrading from older schema
    try:
        conn.execute("SELECT sibling_order FROM conversation_nodes LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE conversation_nodes ADD COLUMN sibling_order INTEGER NOT NULL DEFAULT 0")


class SqliteCatalogStore(CatalogStore):
    def __init__(self, db_path: Path | str, *, read_only: bool = False):
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        if read_only:
            self._conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True, check_same_thread=False)
        else:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if not read_only:
            _init_db(self._conn)

    def list_items(self, entity_type: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, data, icon_path FROM catalog_items WHERE entity_type = ? ORDER BY name",
                (entity_type,),
            ).fetchall()
        items = []
        for row in rows:
            doc = json.loads(row["data"])
            item: dict[str, Any] = {
                "name": doc.get("name", row["name"]),
                "folder_name": row["name"],
                "file": f"{entity_type}/{row['name']}",
            }
            if "description" in doc:
                item["description"] = doc["description"]
            if row["icon_path"]:
                item["icon_path"] = row["icon_path"]
            items.append(item)
        return items

    def get_item(self, entity_type: str, name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM catalog_items WHERE entity_type = ? AND name = ?",
                (entity_type, name),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["data"])

    def save_item(self, entity_type: str, name: str, data: dict[str, Any]) -> None:
        icon_path = data.get("icon_path")
        blob = json.dumps(data, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """INSERT INTO catalog_items (entity_type, name, data, icon_path, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(entity_type, name) DO UPDATE
                   SET data = excluded.data, icon_path = excluded.icon_path, updated_at = datetime('now')""",
                (entity_type, name, blob, icon_path),
            )
            self._conn.commit()

    def delete_item(self, entity_type: str, name: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM catalog_items WHERE entity_type = ? AND name = ?",
                (entity_type, name),
            )
            self._conn.commit()
        return cur.rowcount > 0


class SqliteConversationStore(ConversationStore):
    def __init__(self, db_path: Path | str, *, read_only: bool = False):
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        if read_only:
            self._conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True, check_same_thread=False)
        else:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if not read_only:
            _init_db(self._conn)

    def load_doc(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT roots, active_path, metadata FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                return None
            node_rows = self._conn.execute(
                "SELECT node_id, parent_id, role, content, metadata FROM conversation_nodes "
                "WHERE conversation_id = ? ORDER BY parent_id, sibling_order",
                (conversation_id,),
            ).fetchall()

        roots = json.loads(row["roots"])
        active_path = json.loads(row["active_path"])
        conv_meta = json.loads(row["metadata"]) if row["metadata"] else {}
        nodes: dict[str, dict[str, Any]] = {}
        children: dict[str, list[str]] = {}

        for nr in node_rows:
            nid = nr["node_id"]
            meta = json.loads(nr["metadata"]) if nr["metadata"] else {}
            node: dict[str, Any] = {
                "pid": nr["parent_id"],
                "role": nr["role"],
                "content": nr["content"],
            }
            node.update(meta)
            nodes[nid] = node
            pid = nr["parent_id"]
            if pid is not None:
                children.setdefault(pid, [])
                if nid not in children[pid]:
                    children[pid].append(nid)

        result: dict[str, Any] = {}
        result.update(conv_meta)
        result["roots"] = roots
        result["nodes"] = nodes
        result["children"] = children
        result["active_path"] = active_path
        return result

    def save_doc(self, conversation_id: str, doc: dict[str, Any]) -> None:
        roots = json.dumps(doc.get("roots") or [], ensure_ascii=False)
        active_path = json.dumps(doc.get("active_path") or [], ensure_ascii=False)
        nodes = doc.get("nodes", {})
        children_dict = doc.get("children", {})
        meta = {k: v for k, v in doc.items() if k not in _CONVERSATION_STRUCTURAL_KEYS}
        meta_json = json.dumps(meta, ensure_ascii=False) if meta else None

        # Pre-compute sibling ordering from children dict
        sibling_orders: dict[str, int] = {}
        for child_list in children_dict.values():
            for idx, child_id in enumerate(child_list):
                sibling_orders[child_id] = idx

        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """INSERT INTO conversations (id, roots, active_path, metadata, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'))
                       ON CONFLICT(id) DO UPDATE
                       SET roots = excluded.roots, active_path = excluded.active_path,
                           metadata = excluded.metadata, updated_at = datetime('now')""",
                    (conversation_id, roots, active_path, meta_json),
                )
                self._conn.execute(
                    "DELETE FROM conversation_nodes WHERE conversation_id = ?",
                    (conversation_id,),
                )
                for nid, node in nodes.items():
                    pid = node.get("pid")
                    role = node.get("role", "")
                    content = node.get("content", "")
                    node_meta = {k: v for k, v in node.items() if k not in ("pid", "role", "content")}
                    node_meta_json = json.dumps(node_meta, ensure_ascii=False) if node_meta else None
                    self._conn.execute(
                        """INSERT INTO conversation_nodes
                           (conversation_id, node_id, parent_id, role, content, metadata, sibling_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (conversation_id, nid, pid, role, content, node_meta_json, sibling_orders.get(nid, 0)),
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def load_settings(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM conversation_settings WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return {}
        return json.loads(row["data"])

    def save_settings(self, conversation_id: str, settings: dict[str, Any]) -> None:
        blob = json.dumps(settings, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """INSERT INTO conversations (id, roots, active_path)
                   VALUES (?, '[]', '[]')
                   ON CONFLICT(id) DO NOTHING""",
                (conversation_id,),
            )
            self._conn.execute(
                """INSERT INTO conversation_settings (conversation_id, data)
                   VALUES (?, ?)
                   ON CONFLICT(conversation_id) DO UPDATE SET data = excluded.data""",
                (conversation_id, blob),
            )
            self._conn.commit()

    def load_variables(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM conversation_variables WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return {}
        return json.loads(row["data"])

    def save_variables(self, conversation_id: str, variables: dict[str, Any]) -> None:
        blob = json.dumps(variables, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """INSERT INTO conversations (id, roots, active_path)
                   VALUES (?, '[]', '[]')
                   ON CONFLICT(id) DO NOTHING""",
                (conversation_id,),
            )
            self._conn.execute(
                """INSERT INTO conversation_variables (conversation_id, data)
                   VALUES (?, ?)
                   ON CONFLICT(conversation_id) DO UPDATE SET data = excluded.data""",
                (conversation_id, blob),
            )
            self._conn.commit()
