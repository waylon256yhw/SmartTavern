"""
函数/能力注册与编排系统（API Registry）

规范：
- 统一使用 @register_api(path, input_schema, output_schema, name?, description?, methods?)
- 路径为斜杠风格（不包含传输层前缀），命名空间根据函数文件位置自动解析：
  • api/modules/* => modules
  • api/workflow/* => workflow
  • api/plugins/* => plugins
- 内部 key 为 (namespace, path) 元组，支持同名 path 在不同命名空间共存
- path-only 查找仅在唯一匹配时返回，多匹配时抛出 ValueError
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FunctionSpec:
    """函数规范 — 以 JSON Schema 与斜杠路径为核心"""

    name: str
    description: str
    path: str
    namespace: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    methods: list[str] = field(default_factory=lambda: ["GET", "POST"])

    def __repr__(self):
        return f"{self.namespace}:{self.path} [{self.name}]"


class FunctionRegistry:
    """函数与工作流注册中心"""

    def __init__(self):
        self.functions: dict[tuple[str, str], Callable] = {}
        self.specs: dict[tuple[str, str], FunctionSpec] = {}
        # path -> list of (ns, path) keys — 用于 path-only 兼容查找
        self._path_index: dict[str, list[tuple[str, str]]] = {}
        self.workflows: dict[str, Callable] = {}

    def _derive_namespace(self, func: Callable) -> str:
        mod = getattr(func, "__module__", "") or ""
        if mod.startswith("api.modules"):
            return "modules"
        if mod.startswith("api.workflow"):
            return "workflow"
        if mod.startswith("api.plugins"):
            return "plugins"
        raise ValueError(f"无法解析命名空间（函数不在 api/modules 或 api/workflow 或 api/plugins 下）：module={mod}")

    def register(
        self,
        path: str,
        func: Callable,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        name: str | None = None,
        description: str = "",
        methods: list[str] | None = None,
    ) -> None:
        if not isinstance(path, str) or not path:
            raise ValueError("path 必须为非空字符串")
        path = path.lstrip("/")

        ns = self._derive_namespace(func)
        key = (ns, path)

        if key in self.functions:
            raise ValueError(f"API key 冲突: ({ns}, {path}) 已被注册。已有: {self.specs[key]}")

        if not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
            raise ValueError("input_schema / output_schema 必须为字典(JSON Schema)")

        func_name = name or func.__name__
        spec = FunctionSpec(
            name=func_name,
            description=description or "",
            path=path,
            namespace=ns,
            input_schema=input_schema,
            output_schema=output_schema,
            methods=[m.upper() for m in (methods or ["GET", "POST"])],
        )

        self.functions[key] = func
        self.specs[key] = spec
        self._path_index.setdefault(path, []).append(key)

        try:
            print(f"✓ 已注册API: {spec}")
        except UnicodeEncodeError:
            print(f"[OK] 已注册API: {spec}")

    def _resolve_key(self, path: str, namespace: str | None) -> tuple[str, str] | None:
        if namespace:
            key = (namespace, path)
            return key if key in self.functions else None
        keys = self._path_index.get(path, [])
        if not keys:
            return None
        if len(keys) > 1:
            raise ValueError(f"路径 '{path}' 匹配到 {len(keys)} 个注册项 {keys}，请使用 namespace 参数精确指定。")
        return keys[0]

    def get_spec(self, path: str, namespace: str | None = None) -> FunctionSpec | None:
        key = self._resolve_key(path, namespace)
        return self.specs.get(key) if key else None

    def get_function(self, path: str, namespace: str | None = None) -> Callable | None:
        key = self._resolve_key(path, namespace)
        return self.functions.get(key) if key else None

    def call(self, path: str, namespace: str | None = None, **kwargs) -> Any:
        func = self.get_function(path, namespace)
        if func is None:
            raise ValueError(f"函数未注册: ns={namespace}, path={path}")
        return func(**kwargs) if kwargs else func()

    def list_functions(self) -> list[tuple[str, str]]:
        return list(self.functions.keys())

    # 兼容保留：工作流注册
    def register_workflow(self, name: str, workflow: Callable):
        if name in self.workflows:
            try:
                print(f"警告: 工作流 '{name}' 已被覆盖。")
            except UnicodeEncodeError:
                print(f"[WARNING] 工作流 '{name}' 已被覆盖。")
        self.workflows[name] = workflow
        try:
            print(f"✓ 已注册工作流: {name}")
        except UnicodeEncodeError:
            print(f"[OK] 已注册工作流: {name}")

    def get_workflow(self, name: str) -> Callable | None:
        return self.workflows.get(name)

    def list_workflows(self) -> list[str]:
        return list(self.workflows.keys())


# 全局注册器
_registry = FunctionRegistry()


def get_registry() -> FunctionRegistry:
    return _registry


def register_workflow(name: str):
    """装饰器：注册工作流（兼容保留）"""

    def decorator(func):
        _registry.register_workflow(name, func)
        return func

    return decorator


def register_api(
    path: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    name: str | None = None,
    description: str = "",
    methods: list[str] | None = None,
):
    """
    装饰器：注册API
    使用方法:
        @register_api(
            path="web_server/restart_project",
            input_schema={...},
            output_schema={...},
            description="重启前端项目"
        )
        def restart_frontend_project(...):
            ...
    """

    def decorator(func):
        _registry.register(
            path,
            func,
            input_schema,
            output_schema,
            name=name,
            description=description,
            methods=methods,
        )
        return func

    return decorator


def get_registered_api(path: str, namespace: str | None = None) -> Callable:
    func = _registry.get_function(path, namespace)
    if func is None:
        raise KeyError(f"API 未注册: ns={namespace}, path={path}")
    return func
