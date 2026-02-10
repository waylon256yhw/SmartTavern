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


def _bootstrap_gateway(config_file=None):
    """加载所有 API 模块、插件，创建并配置网关实例。

    启动顺序：
    0. validate storage backend config
    1. load_project_modules — 导入 api/ 下所有 .py，触发 @register_api
    2. load_backend_plugin_apis — 按 manifest 导入插件 API 模块
    3. initialize_plugins — 运行时 hook 注册（HookManager）
    """
    # 0) Storage backend validation
    from shared.storage import get_storage_backend

    backend = get_storage_backend()
    if backend not in ("json", "sqlite"):
        print(f"[FATAL] Unknown STORAGE_BACKEND={backend!r}. Expected 'json' or 'sqlite'.")
        sys.exit(1)
    print(f"[INFO] Storage backend: {backend}")

    from core.services import service_manager

    # 1) API 模块发现与注册
    imported = service_manager.load_project_modules()
    print(f"[INFO] Imported {imported} backend modules under 'api/'.")

    # 2) 插件 manifest → API 模块导入
    try:
        from core.plugins_backend_loader import load_backend_plugin_apis

        plug_res = load_backend_plugin_apis(manifest_only=True, project="SmartTavern")
        print(
            f"[INFO] Plugin backend loader: manifests={plug_res.manifests_read}, imported={len(plug_res.imported_modules)}, skipped={len(plug_res.skipped_entries)}"
        )
    except Exception as e:
        print(f"[WARN] Plugin backend loader failed: {type(e).__name__}: {e}")

    # 3) 运行时 hook 初始化
    plugins_count = service_manager.initialize_plugins()
    print(f"[INFO] Plugin hooks initialized: {plugins_count} plugin(s) loaded.")

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
