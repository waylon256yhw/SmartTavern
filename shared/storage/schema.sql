-- SmartTavern storage schema (SQLite)

CREATE TABLE IF NOT EXISTS catalog_items (
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    data JSON NOT NULL,
    icon_path TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (entity_type, name)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    roots JSON NOT NULL,
    active_path JSON NOT NULL,
    metadata JSON,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_nodes (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    parent_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    metadata JSON,
    sibling_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (conversation_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_parent ON conversation_nodes(conversation_id, parent_id);

CREATE TABLE IF NOT EXISTS conversation_settings (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    data JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_variables (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    data JSON NOT NULL
);
