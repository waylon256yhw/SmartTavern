"""
SmartTavern AI 对话补全工作流 - API 封装层

提供统一的AI对话补全能力：
- 读取对话文件获取messages
- 使用LLM配置调用AI
- 保存响应到对话文件
"""

from typing import Any

import core

from .impl import (
    chat_completion_non_streaming as _chat_completion_non_streaming,
)
from .impl import (
    chat_completion_streaming as _chat_completion_streaming,
)
from .impl import (
    chat_with_config_non_streaming as _chat_with_config_non_streaming,
)
from .impl import (
    chat_with_config_streaming as _chat_with_config_streaming,
)
from .impl import (
    process_messages_view_impl as _process_messages_view_impl,
)


@core.register_api(
    path="smarttavern/chat_completion/complete",
    name="AI对话补全（非流式）",
    description="读取对话文件，调用AI生成响应，保存到对话文件。若不提供llm_config_file则从对话的settings.json自动读取",
    input_schema={
        "type": "object",
        "properties": {
            "conversation_file": {"type": "string"},
            "llm_config_file": {"type": ["string", "null"]},
        },
        "required": ["conversation_file"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "node_id": {"type": "string"},
            "content": {"type": "string"},
            "usage": {"type": "object", "additionalProperties": True},
            "response_time": {"type": "number"},
            "model_used": {"type": "string"},
            "doc": {"type": "object", "additionalProperties": True},
            "error": {"type": "string"},
        },
        "required": ["success"],
        "additionalProperties": True,
    },
)
def complete(
    conversation_file: str,
    llm_config_file: str | None = None,
) -> dict[str, Any]:
    return _chat_completion_non_streaming(
        conversation_file=conversation_file,
        llm_config_file=llm_config_file,
    )


@core.register_api(
    path="smarttavern/chat_completion/process_messages_view",
    name="处理对话消息的指定视图（含规则合并 + RAW 装配 + 输出模式）",
    description="完整流程：1) 从settings获取资产并合并规则 2) 获取原始messages 2.5) 调用 prompt_raw/assemble_full 进行 RAW 装配 3) 从文件读取variables 4) 应用规则和view处理 5) 保存variables；支持 output='full' 或 'history' 仅返回历史楼层消息。",
    input_schema={
        "type": "object",
        "properties": {
            "conversation_file": {"type": "string"},
            "view": {"type": "string", "enum": ["user_view", "assistant_view"]},
            "output": {"type": "string", "enum": ["full", "history"], "default": "full"},
        },
        "required": ["conversation_file", "view"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "messages": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "variables": {"type": "object", "additionalProperties": True},
            "error": {"type": "string"},
        },
        "required": ["success"],
        "additionalProperties": True,
    },
)
def process_messages_view(
    conversation_file: str,
    view: str,
    output: str = "full",
) -> dict[str, Any]:
    """
    处理对话消息的指定视图（一体化）

    自动完成完整流程，并支持输出模式：
    1. 从 settings.json 读取 preset、character、regex_rules
    2. 调用 assets_normalizer 合并为统一 regex_rules
    3. 获取原始 messages
    4. 从 variables.json 自动读取 variables
    5. 调用 prompt_postprocess 处理指定视图
    6. 保存更新后的 variables 到文件
    7. output='history' 时，仅返回历史楼层消息；'full' 返回完整处理结果

    参数：
    - conversation_file: 对话文件路径
    - view: "user_view"（前端显示用） 或 "assistant_view"（发送给AI用）
    - output: "full" | "history"

    返回：
    - messages: 处理后的消息数组（根据 output 策略）
    - variables: 更新后的变量字典
    """
    return _process_messages_view_impl(conversation_file, view, variables=None, output=output)


@core.register_api(
    path="smarttavern/chat_completion/chat_with_config",
    name="使用当前对话配置进行AI调用（自定义messages）",
    description="使用当前对话的LLM配置，但使用自定义的messages数组进行AI调用。支持可选的预设/世界书/正则处理。",
    input_schema={
        "type": "object",
        "properties": {
            "conversation_file": {"type": "string"},
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
            "stream": {"type": "boolean", "default": False},
            "custom_params": {"type": "object"},
            "apply_preset": {"type": "boolean", "default": True},
            "apply_world_book": {"type": "boolean", "default": True},
            "apply_regex": {"type": "boolean", "default": True},
            "save_result": {"type": "boolean", "default": False},
            "view": {"type": "string", "enum": ["user_view", "assistant_view"], "default": "assistant_view"},
            "variables": {"type": "object"},
        },
        "required": ["conversation_file", "messages"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "content": {"type": "string"},
            "usage": {"type": "object", "additionalProperties": True},
            "response_time": {"type": "number"},
            "model_used": {"type": "string"},
            "finish_reason": {"type": "string"},
            "error": {"type": "string"},
        },
        "required": ["success"],
        "additionalProperties": True,
    },
)
def chat_with_config(
    conversation_file: str,
    messages: list[dict[str, str]],
    stream: bool | None = None,
    custom_params: dict[str, Any] | None = None,
    apply_preset: bool = True,
    apply_world_book: bool = True,
    apply_regex: bool = True,
    save_result: bool = False,
    view: str = "assistant_view",
    variables: dict[str, Any] | None = None,
) -> Any:
    """
    使用当前对话配置进行AI调用

    从对话的settings.json读取llm_config和资产配置，支持可选的消息处理流程。

    参数：
    - conversation_file: 对话文件路径（用于读取llm_config和资产）
    - messages: 自定义的消息数组 [{"role": "user", "content": "..."}]
    - stream: 可选，是否流式返回。如果不提供则使用配置文件的值
    - custom_params: 可选，自定义参数，会覆盖配置文件中的 custom_params
    - apply_preset: 是否应用预设（默认 True）
    - apply_world_book: 是否应用世界书（默认 True）
    - apply_regex: 是否应用正则规则（默认 True）
    - save_result: 是否保存结果到消息树（默认 False）
    - view: 视图类型 "user_view" | "assistant_view"（默认 "assistant_view"）
    - variables: 变量字典（可选，默认从 variables.json 读取）

    返回：
    - 非流式：JSON对象包含content, usage等
    - 流式：SSE事件流
    """
    use_stream = stream if stream is not None else False

    if not use_stream:
        return _chat_with_config_non_streaming(
            conversation_file=conversation_file,
            messages=messages,
            stream_override=stream,
            custom_params_override=custom_params,
            apply_preset=apply_preset,
            apply_world_book=apply_world_book,
            apply_regex=apply_regex,
            save_result=save_result,
            view=view,
            variables=variables,
        )

    # 流式SSE
    try:
        from fastapi.responses import StreamingResponse
    except Exception as e:
        return {"success": False, "error": f"SSE不可用（依赖fastapi未就绪）: {e!s}"}

    import json

    def _sse_line(obj: dict[str, Any]) -> str:
        return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

    def _make_sse_generator():
        try:
            for event in _chat_with_config_streaming(
                conversation_file=conversation_file,
                messages=messages,
                stream_override=stream,
                custom_params_override=custom_params,
                apply_preset=apply_preset,
                apply_world_book=apply_world_book,
                apply_regex=apply_regex,
                save_result=save_result,
                view=view,
                variables=variables,
            ):
                yield _sse_line(event)
        except Exception as e:
            yield _sse_line({"type": "error", "message": str(e)})
            yield _sse_line({"type": "end"})

    return StreamingResponse(
        _make_sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@core.register_api(
    path="smarttavern/chat_completion/complete_stream",
    name="AI对话补全（流式）",
    description="读取对话文件，调用AI流式生成响应，逐块返回并最终保存到对话文件。若不提供llm_config_file则从对话的settings.json自动读取。返回SSE事件流",
    input_schema={
        "type": "object",
        "properties": {
            "conversation_file": {"type": "string"},
            "llm_config_file": {"type": ["string", "null"]},
        },
        "required": ["conversation_file"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "description": "SSE流，事件类型：chunk/finish/usage/saved/error/end",
        "additionalProperties": True,
    },
)
def complete_stream(
    conversation_file: str,
    llm_config_file: str | None = None,
) -> Any:
    """
    流式补全：返回SSE
    事件格式：
    - data: {"type": "chunk", "content": "..."}
    - data: {"type": "finish", "finish_reason": "..."}
    - data: {"type": "usage", "usage": {...}}
    - data: {"type": "saved", "node_id": "...", "doc": {...}}
    - data: {"type": "error", "message": "..."}
    - data: {"type": "end"}
    """
    try:
        from fastapi.responses import StreamingResponse
    except Exception as e:
        return {"success": False, "error": f"SSE不可用（依赖fastapi未就绪）: {e!s}"}

    import json

    def _sse_line(obj: dict[str, Any]) -> str:
        return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

    def _make_sse_generator():
        try:
            for event in _chat_completion_streaming(
                conversation_file=conversation_file,
                llm_config_file=llm_config_file,
            ):
                yield _sse_line(event)
        except Exception as e:
            yield _sse_line({"type": "error", "message": str(e)})
            yield _sse_line({"type": "end"})

    return StreamingResponse(
        _make_sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
