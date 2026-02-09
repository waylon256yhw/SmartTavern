#!/usr/bin/env python3
"""
Start all backend APIs for ModularFlow-Framework.

This script:
 - Dynamically imports all modules under api/modules and api/workflow to register APIs
 - Starts the unified API Gateway (FastAPI + Uvicorn)

Usage:
  uv run smarttavern [--host 0.0.0.0] [--port 8050] [--background] [--config api-config.json] [--reload]

Notes:
 - Requires fastapi and uvicorn installed.
 - Auto-discovery relies on each module calling core.register_api at import time.
 - --reload 使用 Uvicorn factory 模式，满足“必须以导入字符串传入应用”的要求，避免警告。
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

FRONTEND_DIR = REPO_ROOT / "frontend_projects" / "SmartTavern"
FRONTEND_DIST = FRONTEND_DIR / "dist"


def _build_frontend() -> None:
    """Auto-detect bun/npm and build frontend for production."""
    runner = None
    for cmd in ("bun", "npm"):
        if shutil.which(cmd):
            runner = cmd
            break
    if not runner:
        print("[ERROR] Neither bun nor npm found. Install one to build frontend.")
        sys.exit(1)

    print(f"[INFO] Building frontend with {runner} ...")
    subprocess.run([runner, "install"], cwd=str(FRONTEND_DIR), check=True)
    subprocess.run([runner, "run", "build"], cwd=str(FRONTEND_DIR), check=True)

    if not FRONTEND_DIST.exists():
        print("[ERROR] Frontend build produced no output.")
        sys.exit(1)
    print(f"[INFO] Frontend built -> {FRONTEND_DIST}")


def _enable_inproc_defaults() -> None:
    """默认开启 core 进程内直调（所有命名空间）。
    - 外部已显式设置时不覆盖（setdefault）。
    """
    try:
        os.environ.setdefault("MF_INPROC", "1")
        os.environ.setdefault("MF_INPROC_NS", "modules,workflow,plugins")
    except Exception:
        pass


def _iter_py_modules(base_dir: Path, base_pkg: str):
    """
    遍历 base_dir 下所有 .py 模块，生成完整模块名（跳过 __* 与 test*/example*）
    """
    for p in base_dir.rglob("*.py"):
        if p.name.startswith("__"):
            continue
        # 过滤测试与示例
        if "test" in p.parts or "tests" in p.parts or "example" in p.parts or "examples" in p.parts:
            continue
        rel = p.relative_to(REPO_ROOT).with_suffix("")
        parts = list(rel.parts)
        if parts[: len(base_pkg.split("."))] != base_pkg.split("."):
            continue
        mod = ".".join(parts)
        yield mod


def _import_all_under(base_dir: Path, base_pkg: str) -> int:
    """导入 base_pkg 下所有模块，返回成功数量"""
    count = 0
    for mod in _iter_py_modules(base_dir, base_pkg):
        try:
            importlib.import_module(mod)
            count += 1
        except Exception as e:
            print(f"[WARN] Failed to import {mod}: {type(e).__name__}: {e}")
    return count


def load_all_api_modules() -> int:
    """
    触发 api/modules 与 api/workflow 下所有模块的注册（@register_api）
    返回导入模块总数
    """
    total = 0
    api_modules_dir = REPO_ROOT / "api" / "modules"
    api_workflow_dir = REPO_ROOT / "api" / "workflow"
    api_plugins_dir = REPO_ROOT / "api" / "plugins"
    if api_modules_dir.exists():
        try:
            importlib.import_module("api.modules")
        except Exception:
            pass
        total += _import_all_under(api_modules_dir, "api.modules")
    if api_workflow_dir.exists():
        try:
            importlib.import_module("api.workflow")
        except Exception:
            pass
        total += _import_all_under(api_workflow_dir, "api.workflow")
    if api_plugins_dir.exists():
        try:
            importlib.import_module("api.plugins")
        except Exception:
            pass
        total += _import_all_under(api_plugins_dir, "api.plugins")
    return total


def _bootstrap_gateway(config_file=None):
    """加载所有 API 模块、插件，创建并配置网关实例。"""
    imported = load_all_api_modules()
    print(f"[INFO] Imported {imported} backend modules under 'api.modules' and 'api.workflow'.")
    try:
        from core.plugins_backend_loader import load_backend_plugin_apis

        plug_res = load_backend_plugin_apis(manifest_only=True, project="SmartTavern")
        print(
            f"[INFO] Plugin backend loader: manifests={plug_res.manifests_read}, imported={len(plug_res.imported_modules)}, skipped={len(plug_res.skipped_entries)}"
        )
    except Exception as e:
        print(f"[WARN] Plugin backend loader failed: {type(e).__name__}: {e}")

    import core

    reg = core.get_registry()
    print(f"[INFO] Registered API functions: {len(reg.list_functions())}")

    from core.api_gateway import get_api_gateway

    gateway = get_api_gateway(config_file=config_file)
    return gateway


def create_app():
    """
    Uvicorn factory 模式入口。用于 --reload 时满足"以导入字符串传入应用"的要求。
    返回 FastAPI app 实例。
    """
    _enable_inproc_defaults()
    gateway = _bootstrap_gateway()

    gateway.discover_and_register_functions()
    gateway.setup_websocket()
    gateway.setup_static_files()
    gateway._register_endpoints_to_fastapi()
    gateway.setup_spa_fallback()

    return gateway.app


def main():
    _enable_inproc_defaults()
    parser = argparse.ArgumentParser(description="Start all backend APIs (API Gateway)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8050, help="Bind port (default: 8050)")
    parser.add_argument("--background", action="store_true", help="Run in background thread (non-blocking)")
    parser.add_argument("--config", default=None, help="Optional api-config.json path")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload (development)")
    parser.add_argument(
        "--serve", action="store_true", help="Build frontend and serve everything on one port (production mode)"
    )
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild frontend (use with --serve)")
    args = parser.parse_args()

    if args.serve:
        if args.rebuild or not FRONTEND_DIST.exists():
            _build_frontend()
        else:
            print(f"[INFO] Frontend dist exists: {FRONTEND_DIST} (add --rebuild to force)")

    if args.reload:
        # 使用导入字符串 + factory 模式，避免 uvicorn 的 reload 警告
        try:
            import uvicorn
        except ImportError:
            print("❌ Missing dependency: uvicorn. Please `pip install uvicorn fastapi`")
            sys.exit(1)

        target = "start_all_apis:create_app"
        print(f"[INFO] Starting API Gateway with reload on http://{args.host}:{args.port}")
        uvicorn.run(
            target, host=args.host, port=args.port, log_level="info", reload=True, factory=True, access_log=True
        )
        return

    # 非 reload 情况：直接通过网关对象启动（无警告）
    gateway = _bootstrap_gateway(config_file=args.config)
    gateway.config.host = args.host
    gateway.config.port = args.port
    gateway.config.debug = False

    if args.serve:
        gateway.config.static_files_enabled = True
        gateway.config.static_directory = str(FRONTEND_DIST)
        gateway.config.static_url_prefix = "/"

    print(f"[INFO] Starting API Gateway on http://{args.host}:{args.port} (background={args.background}) ...")
    gateway.start_server(background=args.background)

    if args.background:
        print("[INFO] API server started in background. Press Ctrl+C to exit this launcher.")
        try:
            import time

            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[INFO] Stop signal received. Shutting down gateway ...")
            gateway.stop_server()
    else:
        # 前台模式：uvicorn 在 start_server 中阻塞运行
        pass


if __name__ == "__main__":
    main()
