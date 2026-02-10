"""
统一服务管理系统 (Unified Service Management System)

提供框架级别的服务定位、动态模块发现与加载，以及共享资源访问的基础能力。
本版本采用纯“API 封装层自动发现”模式：
- 启动时仅扫描框架根目录下的 api/* 子包并导入其实现文件，从而触发封装层内的 @register_api 装饰器注册。
- 不再维护项目列表/当前项目/项目配置的读写，相关接口已删除。
"""

import importlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ServiceRegistry:
    """服务注册表"""

    globals_services: dict[str, Any] = field(default_factory=dict)
    module_services: dict[str, Any] = field(default_factory=dict)
    function_services: dict[str, Callable] = field(default_factory=dict)
    workflow_services: dict[str, Callable] = field(default_factory=dict)


class UnifiedServiceManager:
    """
    统一服务管理器（无项目配置文件版）

    负责：
    1. 动态模块发现和加载（仅扫描 modules/*）
    2. 服务注册与定位
    3. 共享资源的统一访问（如有需要可扩展）

    说明：
    - 已移除对 backend_projects/backend-projects.json 的读取与保存逻辑
    - 已删除项目级接口（注册项目、切换项目、获取当前项目等）
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.services = ServiceRegistry()
        self._base_path = Path.cwd()
        self._verbose = False
        self._plugins_initialized = False

    # ========== 动态模块发现与加载 ==========

    def discover_modules(self) -> list[str]:
        """
        扫描 api/ 下所有 .py 模块，返回可导入路径。

        规则：
        - 遍历 api/modules、api/workflow、api/plugins 三个目录
        - 收集所有 .py 文件（跳过 __*.py、test*/example* 目录）
        - 先确保父包已在 sys.modules 中（导入其 __init__.py）
        """
        module_paths: list[str] = []
        seen: set[str] = set()

        api_dirs = [
            self._base_path / "api" / "modules",
            self._base_path / "api" / "workflow",
            self._base_path / "api" / "plugins",
        ]

        for base_dir in api_dirs:
            if not base_dir.exists():
                continue
            for p in base_dir.rglob("*.py"):
                if p.name.startswith("__"):
                    continue
                if any(part in ("test", "tests", "example", "examples") for part in p.parts):
                    continue
                rel = p.relative_to(self._base_path).with_suffix("")
                mod = ".".join(rel.parts)
                if mod not in seen:
                    seen.add(mod)
                    module_paths.append(mod)

        return module_paths

    def load_project_modules(self) -> int:
        """
        加载所有模块（扫描 api/modules、api/workflow、api/plugins）。
        通过 import 导入实现文件以触发模块内的函数/工作流注册。
        """
        # 先确保顶层包可导入
        for pkg in ("api", "api.modules", "api.workflow", "api.plugins"):
            try:
                importlib.import_module(pkg)
            except Exception:
                pass

        total_loaded_count = 0
        discovered = self.discover_modules()

        for module_path in discovered:
            try:
                module = importlib.import_module(module_path)
                total_loaded_count += 1
                parts = module_path.split(".")
                module_name = parts[-2] if len(parts) >= 2 else parts[-1]
                service_key = f"core.{module_name}"
                self.services.module_services[service_key] = module
                if self._verbose:
                    print(f"  ✓ 加载模块: {service_key} ({module_path})")
            except Exception as e:
                print(f"  ✗ 模块加载失败 {module_path}: {type(e).__name__}: {e}")

        return total_loaded_count

    def initialize_plugins(self) -> int:
        """
        初始化后端插件系统（幂等：多次调用只执行一次）

        自动加载所有启用的插件及其 Hook

        返回：
            成功加载的插件数量
        """
        if self._plugins_initialized:
            return 0

        try:
            from api.plugins.SmartTavern import initialize_plugins

            loader = initialize_plugins(auto_load=True)
            loaded_plugins = loader.get_loaded_plugins()

            successful_count = sum(1 for info in loaded_plugins.values() if info.loaded)

            if self._verbose:
                print(f"  ✓ 插件系统初始化完成: {successful_count}/{len(loaded_plugins)} 个插件成功加载")

            self._plugins_initialized = True
            return successful_count

        except Exception as e:
            print(f"  ✗ 插件系统初始化失败: {e}")
            return 0

    # ========== 共享资源访问（占位，可扩展） ==========

    def get_globals(self) -> Any | None:
        """
        获取全局共享的 globals 模块（如有需要可扩展动态发现逻辑）。
        当前返回 None；保留接口以兼容调用方。
        """
        return None

    # ========== 服务定位接口 ==========

    def register_service(self, name: str, service: Any, service_type: str = "general"):
        """注册服务到统一注册表"""
        if service_type == "function":
            self.services.function_services[name] = service
        elif service_type == "workflow":
            self.services.workflow_services[name] = service
        elif service_type == "module":
            self.services.module_services[name] = service
        elif service_type == "globals":
            self.services.globals_services[name] = service

    def get_service(self, name: str, service_type: str | None = None) -> Any | None:
        """按类型与名称获取服务"""
        if (service_type == "function" or service_type is None) and name in self.services.function_services:
            return self.services.function_services[name]

        if (service_type == "workflow" or service_type is None) and name in self.services.workflow_services:
            return self.services.workflow_services[name]

        if (service_type == "module" or service_type is None) and name in self.services.module_services:
            return self.services.module_services[name]

        if (service_type == "globals" or service_type is None) and name in self.services.globals_services:
            return self.services.globals_services[name]

        return None

    def list_services(self, service_type: str | None = None) -> dict[str, list[str]]:
        """列出所有已注册服务"""
        if service_type:
            if service_type == "function":
                return {service_type: list(self.services.function_services.keys())}
            elif service_type == "workflow":
                return {service_type: list(self.services.workflow_services.keys())}
            elif service_type == "module":
                return {service_type: list(self.services.module_services.keys())}
            elif service_type == "globals":
                return {service_type: list(self.services.globals_services.keys())}

        return {
            "function": list(self.services.function_services.keys()),
            "workflow": list(self.services.workflow_services.keys()),
            "module": list(self.services.module_services.keys()),
            "globals": list(self.services.globals_services.keys()),
        }

    # ========== 便捷访问接口 ==========

    def g(self):
        """便捷的 globals 访问接口（当前返回 None）"""
        return self.get_globals()

    def current_g(self):
        """同 g()，保留兼容接口"""
        return self.get_globals()

    def set_verbose(self, verbose: bool = True):
        """设置详细输出模式"""
        self._verbose = verbose


# ========== 全局服务管理器实例与便捷函数 ==========

service_manager = UnifiedServiceManager()


def get_service_manager() -> UnifiedServiceManager:
    """获取全局服务管理器"""
    return service_manager


def get_current_globals():
    """获取当前全局 globals（当前返回 None）"""
    return service_manager.current_g()


# 向后兼容的 globals 访问（用于渐进式迁移）
def get_legacy_globals():
    """
    向后兼容的 globals 访问。若当前不可用，则尝试导入历史路径。
    """
    try:
        g = service_manager.current_g()
        if g is not None:
            return g

        # 历史后备方案（如不存在将捕获 ImportError）
        from shared.SmartTavern import globals as legacy_g  # type: ignore

        return legacy_g
    except ImportError:
        print("⚠️ 无法访问globals模块")
        return None
