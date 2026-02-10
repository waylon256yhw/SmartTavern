#!/usr/bin/env python3
"""
SmartTavern plugin scaffolding tool.

Usage:
    python scripts/create_plugin.py <plugin_name> [--frontend]

Creates a new plugin skeleton under backend_projects/SmartTavern/plugins/<plugin_name>/
with manifest.json, hooks.py, and optionally plugin.js.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "backend_projects" / "SmartTavern" / "plugins"


MANIFEST_TEMPLATE = """\
{{
  "name": "{name}",
  "description": "{name} plugin",
  "entries": [{frontend_entry}],
  "backend_entries": []
}}
"""

HOOKS_TEMPLATE = '''\
"""
{name} - backend hooks
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def before_raw_hook(data: Any, ctx: dict[str, Any]) -> Any | None:
    """beforeRaw hook - runs before RAW prompt assembly."""
    return None


def register_hooks(hook_manager: Any) -> list[str]:
    """Called automatically when the plugin is loaded."""
    strategy_id = "{name}"
    hook_manager.register_strategy(
        strategy_id=strategy_id,
        hooks_dict={{
            "beforeRaw": before_raw_hook,
        }},
        order=50,
    )
    logger.info(f"{name}: hooks registered")
    return [strategy_id]


def unregister_hooks(hook_manager: Any) -> None:
    """Called when the plugin is unloaded / reloaded."""
    hook_manager.unregister_strategy("{name}")
'''

FRONTEND_TEMPLATE = """\
// {name} - frontend plugin
(function () {{
  console.log("[{name}] loaded");
}})();
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new SmartTavern plugin")
    parser.add_argument("name", help="Plugin name (kebab-case recommended, e.g. my-plugin)")
    parser.add_argument("--frontend", action="store_true", help="Also generate a plugin.js template")
    args = parser.parse_args()

    name: str = args.name.strip()
    if not name:
        print("Error: plugin name must not be empty", file=sys.stderr)
        sys.exit(1)
    import re

    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", name):
        print(
            "Error: plugin name must be alphanumeric (with hyphens/underscores/dots), no path separators",
            file=sys.stderr,
        )
        sys.exit(1)

    plugin_dir = PLUGINS_DIR / name
    if plugin_dir.resolve().parent != PLUGINS_DIR.resolve():
        print("Error: invalid plugin name (path traversal)", file=sys.stderr)
        sys.exit(1)
    if plugin_dir.exists():
        print(f"Error: {plugin_dir} already exists", file=sys.stderr)
        sys.exit(1)

    plugin_dir.mkdir(parents=True)

    frontend_entry = '\n    "plugin.js"\n  ' if args.frontend else ""
    (plugin_dir / "manifest.json").write_text(
        MANIFEST_TEMPLATE.format(name=name, frontend_entry=frontend_entry),
        encoding="utf-8",
    )

    (plugin_dir / "hooks.py").write_text(
        HOOKS_TEMPLATE.format(name=name),
        encoding="utf-8",
    )

    if args.frontend:
        (plugin_dir / "plugin.js").write_text(
            FRONTEND_TEMPLATE.format(name=name),
            encoding="utf-8",
        )

    # Add to plugins_switch.json enabled list
    switch_path = PLUGINS_DIR / "plugins_switch.json"
    if switch_path.exists():
        switch = json.loads(switch_path.read_text(encoding="utf-8"))
        enabled = switch.get("enabled", [])
        if name not in enabled:
            enabled.append(name)
            switch["enabled"] = enabled
            switch_path.write_text(
                json.dumps(switch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Added '{name}' to plugins_switch.json")

    files = [str(p.relative_to(REPO_ROOT)) for p in sorted(plugin_dir.iterdir())]
    print(f"Created plugin '{name}' at {plugin_dir.relative_to(REPO_ROOT)}/")
    for f in files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
