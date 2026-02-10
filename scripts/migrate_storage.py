#!/usr/bin/env python3
"""Migrate SmartTavern data between JSON file storage and SQLite.

Usage:
    python scripts/migrate_storage.py --direction json-to-sqlite [--dry-run] [--verify]
    python scripts/migrate_storage.py --direction sqlite-to-json [--dry-run] [--verify]

Options:
    --direction     Migration direction: 'json-to-sqlite' or 'sqlite-to-json'
    --dry-run       Preview what would be migrated without writing
    --verify        After migration, verify data integrity by loading and comparing
    --data-root     Custom data directory (default: backend_projects/SmartTavern/data)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from shared.storage.json_backend import JsonCatalogStore, JsonConversationStore
from shared.storage.sqlite_backend import SqliteCatalogStore, SqliteConversationStore

ENTITY_TYPES = ["presets", "world_books", "characters", "personas", "regex_rules", "llm_configs"]


def migrate_catalog(src_catalog, dst_catalog, *, dry_run: bool = False) -> dict[str, int]:
    stats: dict[str, int] = {}
    for et in ENTITY_TYPES:
        items = src_catalog.list_items(et)
        count = 0
        for item in items:
            folder_name = item.get("folder_name", item["name"])
            data = src_catalog.get_item(et, folder_name)
            if data is None:
                continue
            if item.get("icon_path") and "icon_path" not in data:
                data["icon_path"] = item["icon_path"]
            if not dry_run:
                dst_catalog.save_item(et, folder_name, data)
            count += 1
        stats[et] = count
        print(f"  {et}: {count} items {'(dry-run)' if dry_run else 'migrated'}")
    return stats


def migrate_conversations(src_conv, dst_conv, *, conv_ids: list[str], dry_run: bool = False) -> int:
    count = 0
    for cid in conv_ids:
        doc = src_conv.load_doc(cid)
        settings = src_conv.load_settings(cid)
        variables = src_conv.load_variables(cid)

        if doc is None and not settings and not variables:
            continue

        if not dry_run:
            if doc is not None:
                dst_conv.save_doc(cid, doc)
            if settings:
                dst_conv.save_settings(cid, settings)
            if variables:
                dst_conv.save_variables(cid, variables)
        count += 1
    print(f"  conversations: {count} {'(dry-run)' if dry_run else 'migrated'}")
    return count


def list_conversation_ids_from_json(data_root: Path) -> list[str]:
    conv_dir = data_root / "conversations"
    if not conv_dir.is_dir():
        return []
    marker_files = {"conversation.json", "settings.json", "variables.json"}
    ids = []
    for sub in sorted(conv_dir.iterdir()):
        if sub.is_dir() and any((sub / f).exists() for f in marker_files):
            ids.append(sub.name)
    return ids


def list_conversation_ids_from_sqlite(db_path: Path) -> list[str]:
    import sqlite3

    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT id FROM conversations ORDER BY id").fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def verify_catalog(src_catalog, dst_catalog) -> list[str]:
    errors = []
    for et in ENTITY_TYPES:
        src_items = {i.get("folder_name", i["name"]) for i in src_catalog.list_items(et)}
        dst_items = {i.get("folder_name", i["name"]) for i in dst_catalog.list_items(et)}
        missing = src_items - dst_items
        if missing:
            errors.append(f"{et}: missing in destination: {missing}")
        for name in src_items & dst_items:
            src_data = src_catalog.get_item(et, name)
            dst_data = dst_catalog.get_item(et, name)
            if src_data != dst_data:
                errors.append(f"{et}/{name}: data mismatch")
    return errors


def verify_conversations(src_conv, dst_conv, conv_ids: list[str]) -> list[str]:
    errors = []
    for cid in conv_ids:
        src_doc = src_conv.load_doc(cid)
        dst_doc = dst_conv.load_doc(cid)
        if src_doc is not None and dst_doc is None:
            errors.append(f"conversation {cid}: missing in destination")
            continue
        if src_doc is not None:
            src_roots = src_doc.get("roots") or []
            dst_roots = dst_doc.get("roots") or []
            if src_roots != dst_roots:
                errors.append(f"conversation {cid}: roots mismatch")
            src_ap = src_doc.get("active_path") or []
            dst_ap = dst_doc.get("active_path") or []
            if src_ap != dst_ap:
                errors.append(f"conversation {cid}: active_path mismatch")

            # Verify metadata fields
            for field in ("name", "description", "updated_at"):
                sv = src_doc.get(field)
                dv = dst_doc.get(field)
                if sv != dv:
                    errors.append(f"conversation {cid}: {field} mismatch (src={sv!r}, dst={dv!r})")

            # Verify node keys
            src_nodes = src_doc.get("nodes") or {}
            dst_nodes = dst_doc.get("nodes") or {}
            if set(src_nodes.keys()) != set(dst_nodes.keys()):
                errors.append(f"conversation {cid}: node keys mismatch (src={len(src_nodes)}, dst={len(dst_nodes)})")
            else:
                # Verify each node's content, role, pid, and metadata
                for nid in src_nodes:
                    sn = src_nodes[nid]
                    dn = dst_nodes[nid]
                    for field in ("pid", "role", "content"):
                        if sn.get(field) != dn.get(field):
                            errors.append(f"conversation {cid}/node {nid}: {field} mismatch")
                    # Compare remaining fields (node metadata)
                    s_extra = {k: v for k, v in sn.items() if k not in ("pid", "role", "content")}
                    d_extra = {k: v for k, v in dn.items() if k not in ("pid", "role", "content")}
                    if s_extra != d_extra:
                        errors.append(f"conversation {cid}/node {nid}: metadata mismatch")

            # Verify children structure and ordering
            src_children = src_doc.get("children") or {}
            dst_children = dst_doc.get("children") or {}
            if set(src_children.keys()) != set(dst_children.keys()):
                errors.append(f"conversation {cid}: children keys mismatch")
            else:
                for pid in src_children:
                    if src_children[pid] != dst_children[pid]:
                        errors.append(
                            f"conversation {cid}: children[{pid}] order mismatch "
                            f"(src={src_children[pid]}, dst={dst_children[pid]})"
                        )

        src_settings = src_conv.load_settings(cid)
        dst_settings = dst_conv.load_settings(cid)
        if src_settings != dst_settings:
            errors.append(f"conversation {cid}: settings mismatch")

        src_vars = src_conv.load_variables(cid)
        dst_vars = dst_conv.load_variables(cid)
        if src_vars != dst_vars:
            errors.append(f"conversation {cid}: variables mismatch")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Migrate SmartTavern storage between JSON and SQLite")
    parser.add_argument("--direction", required=True, choices=["json-to-sqlite", "sqlite-to-json"])
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verify", action="store_true", help="Verify data after migration")
    parser.add_argument(
        "--data-root", type=str, default=None, help="Custom data directory (default: backend_projects/SmartTavern/data)"
    )
    args = parser.parse_args()

    data_root = Path(args.data_root) if args.data_root else _project_root / "backend_projects" / "SmartTavern" / "data"
    db_path = data_root / "smarttavern.db"

    print(f"Data root: {data_root}")
    print(f"SQLite DB: {db_path}")
    print(f"Direction: {args.direction}")
    if args.dry_run:
        print("Mode: DRY RUN")
    print()

    json_catalog = JsonCatalogStore(data_root)
    json_conv = JsonConversationStore(data_root)

    if args.direction == "json-to-sqlite":
        conv_ids = list_conversation_ids_from_json(data_root)

        if args.dry_run:
            print("Catalog entities (dry-run):")
            migrate_catalog(json_catalog, None, dry_run=True)
            print(f"\nConversations ({len(conv_ids)} found, dry-run):")
            migrate_conversations(json_conv, None, conv_ids=conv_ids, dry_run=True)
        else:
            sqlite_catalog = SqliteCatalogStore(db_path)
            sqlite_conv = SqliteConversationStore(db_path)

            print("Migrating catalog entities...")
            migrate_catalog(json_catalog, sqlite_catalog, dry_run=False)

            print(f"\nMigrating conversations ({len(conv_ids)} found)...")
            migrate_conversations(json_conv, sqlite_conv, conv_ids=conv_ids, dry_run=False)

            if args.verify:
                print("\nVerifying...")
                errors = verify_catalog(json_catalog, sqlite_catalog)
                errors += verify_conversations(json_conv, sqlite_conv, conv_ids)
                if errors:
                    print(f"VERIFICATION FAILED ({len(errors)} errors):")
                    for e in errors:
                        print(f"  - {e}")
                    sys.exit(1)
                else:
                    print("Verification passed.")

    elif args.direction == "sqlite-to-json":
        if not db_path.exists():
            print(f"ERROR: SQLite database not found: {db_path}")
            sys.exit(1)

        read_only = args.dry_run
        sqlite_catalog = SqliteCatalogStore(db_path, read_only=read_only)
        sqlite_conv = SqliteConversationStore(db_path, read_only=read_only)
        conv_ids = list_conversation_ids_from_sqlite(db_path)

        if args.dry_run:
            print("Catalog entities (dry-run):")
            migrate_catalog(sqlite_catalog, None, dry_run=True)
            print(f"\nConversations ({len(conv_ids)} found, dry-run):")
            migrate_conversations(sqlite_conv, None, conv_ids=conv_ids, dry_run=True)
        else:
            print("Migrating catalog entities...")
            migrate_catalog(sqlite_catalog, json_catalog, dry_run=False)

            print(f"\nMigrating conversations ({len(conv_ids)} found)...")
            migrate_conversations(sqlite_conv, json_conv, conv_ids=conv_ids, dry_run=False)

            if args.verify:
                print("\nVerifying...")
                errors = verify_catalog(sqlite_catalog, json_catalog)
                errors += verify_conversations(sqlite_conv, json_conv, conv_ids)
                if errors:
                    print(f"VERIFICATION FAILED ({len(errors)} errors):")
                    for e in errors:
                        print(f"  - {e}")
                    sys.exit(1)
                else:
                    print("Verification passed.")

    print("\nDone.")


if __name__ == "__main__":
    main()
