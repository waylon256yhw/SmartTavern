"""Hook 数据契约 — 每个 hook 点的输入/输出 TypedDict 定义。

仅用于文档 + 可选 dev-mode 运行时校验，不影响正常执行。
"""

from __future__ import annotations

from typing import Any, TypedDict


class NormalizeAssetsData(TypedDict, total=False):
    preset: dict[str, Any]
    world_books: list[dict[str, Any]]
    character: dict[str, Any]
    regex_files: list[dict[str, Any]]


class PostprocessData(TypedDict, total=False):
    messages: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    variables: dict[str, Any]


class BeforeLLMCallData(TypedDict, total=False):
    messages: list[dict[str, Any]]
    llm_params: dict[str, Any]


class AfterLLMCallData(TypedDict, total=False):
    content: str
    usage: dict[str, Any]
    finish_reason: str | None
    model_used: str | None


class StreamChunkData(TypedDict, total=False):
    content: str
    finish_reason: str | None
    usage: dict[str, Any]


class BeforeSaveResponseData(TypedDict, total=False):
    node_id: str | None
    content: str
    parent_id: str | None
    is_update: bool


class AfterSaveResponseData(TypedDict, total=False):
    node_id: str | None
    doc: dict[str, Any]
    usage: dict[str, Any]


# hook_name -> 期望的基础类型（TypedDict 子类 / list / dict）
HOOK_DATA_TYPES: dict[str, type] = {
    "beforeNormalizeAssets": NormalizeAssetsData,
    "afterNormalizeAssets": NormalizeAssetsData,
    "beforeRaw": list,
    "afterInsert": list,
    "afterRaw": list,
    "beforePostprocessUser": PostprocessData,
    "afterPostprocessUser": PostprocessData,
    "beforePostprocessAssistant": PostprocessData,
    "afterPostprocessAssistant": PostprocessData,
    "beforeVariablesSave": dict,
    "afterVariablesSave": dict,
    "beforeLLMCall": BeforeLLMCallData,
    "afterLLMCall": AfterLLMCallData,
    "beforeStreamChunk": StreamChunkData,
    "afterStreamChunk": StreamChunkData,
    "beforeSaveResponse": BeforeSaveResponseData,
    "afterSaveResponse": AfterSaveResponseData,
}
