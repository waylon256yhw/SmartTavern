"""Hook 自省 API — 查询注册的 hook、策略和执行指标。"""

from typing import Any

import core


@core.register_api(
    path="smarttavern/hooks/introspection",
    methods=["GET"],
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema={"type": "object", "additionalProperties": True},
    description="查询已注册 hook、策略和执行指标",
)
def hooks_introspection() -> dict[str, Any]:
    from api.plugins.SmartTavern.hook_manager import get_hook_manager

    return get_hook_manager().get_introspection()
