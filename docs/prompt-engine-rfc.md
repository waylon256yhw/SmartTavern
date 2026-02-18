---
created: 2026-02-18
updated: 2026-02-18
baseline: 9e4f154
status: draft
---

# RFC: Prompt Engine — 统一提示词组装合约

## 动机

SmartTavern 需要一个**统一的提示词组装引擎**，同时服务：

- **Threaded Chat**（传统聊天）— 平台控制 UI，消息流式推送
- **Sandbox Card**（沙盒卡）— 卡的 HTML 接管渲染，通过 Bridge API 调用引擎

当前后端已有一套 prompt pipeline（分散在 6 个 api/modules + 3 个 api/workflow 中），但缺少统一的输入/输出合约和多阶段调试输出。本 RFC 定义这个合约。

### 参考

- [fast-tavern](https://github.com/Lianues/fast-tavern) — 框架无关的提示词组装引擎，提供 4 阶段调试输出
- `docs/sandbox-card-design.md` — 沙盒卡 Bridge API 设计

## 设计原则

1. **执行权威在后端** — 引擎在 Python 侧运行，前端只消费结果
2. **前端可预览** — 返回多阶段调试数据，前端渲染 stage inspector
3. **hook 兼容** — 现有的 17 个 hook point 全部保留，新端点与 `prompt_router` 共享同一套 hook 执行路径
4. **输入统一** — threaded 和 sandbox 使用相同的 `BuildParams`，通过 adapter 转换

## 合约定义

### 输入：BuildParams

```python
class BuildParams:
    # === 资产引用（文件路径） ===
    conversation_file: str | None   # 对话文件路径（threaded 模式必填，sandbox 模式可省略）
    character_file: str | None      # 角色卡文件
    preset_file: str | None         # 预设文件
    persona_file: str | None        # 用户人设文件
    llm_config_file: str | None     # LLM 配置文件
    worldbook_files: list[str]      # 世界书文件列表
    regex_files: list[str]          # 正则规则文件列表

    # === 直传消息（sandbox 模式） ===
    messages: list[Message] | None  # sandbox 直接传入的消息，跳过 conversation_file
    extra_system: str | None        # sandbox 作者的运行时补充指令

    # === 控制参数 ===
    view: Literal["user_view", "assistant_view"] = "assistant_view"
    output: Literal["full", "history", "delta"] = "full"
    target_node_id: str | None = None  # complete 模式：指定 AI 响应写入的节点（并发/切分支安全）

    # === delta 模式参数 ===
    fingerprints: dict[str, str] | None = None
    variables_hash: str | None = None
    variables_fingerprints: dict[str, str] | None = None

    # === 变量 ===
    variables: dict | None          # 局部变量初始值
    global_variables: dict | None   # 全局变量初始值
    macros: dict[str, str] | None   # 额外宏变量

    # === 调试 ===
    include_stages: bool = False    # 是否返回多阶段调试数据
    include_per_item: bool = False  # 是否返回逐条调试快照
    dry_run: bool = False           # build 模式：true 时不持久化变量（纯预览）
```

### 输出：BuildResult

```python
class BuildResult:
    # === 最终输出（始终返回） ===
    messages: list[Message]         # 最终组装的消息列表，可直接发送 LLM
    variables: VariableState        # 变量最终状态

    # === 元信息 ===
    active_worldbook_entries: list[ActivatedEntry]  # 被激活的世界书条目（需新增产出逻辑）
    merged_regex: MergedRegex                       # 合并后的正则脚本（对齐 normalizer 输出结构）

    # === 调试（include_stages=True 时） ===
    stages: Stages | None

    # === 逐条调试（include_per_item=True 时） ===
    per_item: list[PerItemStages] | None

class ActivatedEntry:
    """被激活的世界书条目摘要"""
    id: str
    keywords: list[str]
    position: str               # before_char / after_char / in-chat
    depth: int | None
    activation_reason: str      # 命中的关键词或 "constant"

class MergedRegex:
    """对齐 assets_normalizer 输出结构"""
    regex_rules: list[dict]     # 合并后的规则数组
    meta: dict                  # {order, input_counts, dedup_removed_count, total, ...}
```

### Stage 模型

5 阶段，对齐后端实际管线 `before_macro regex → macro → after_macro regex`：

```python
class Stages:
    """每个阶段都是完整的消息列表快照"""
    raw: list[SourcedContent]                   # prompt_raw 组装完成，未进入后处理
    after_before_macro_regex: list[SourcedContent]  # before_macro 正则执行后
    after_macro: list[SourcedContent]           # 宏展开后
    after_regex: list[SourcedContent]           # after_macro 正则执行后（最终）

class SourcedContent:
    """保留后端完整 source 对象，tag 为派生便利字段"""
    source: dict            # 完整 source 对象，与 prompt_raw/in_chat_constructor 产出一致
                            # e.g. {type: "history.user", id: "history_3", source_id: "..."}
                            #      {type: "preset.relative", id: "preset_main", ...原始 preset 字段}
                            #      {type: "world_book.in-chat", id: "wb_42", derived_role: "system", ...}
    tag: str                # 从 source.type 派生的简化标记（便利字段，非唯一真相源）
    role: str               # system / user / assistant / thinking
    text: str               # 该阶段的文本内容
    history_depth: int | None  # 如果来自聊天历史，从末尾计数的深度

class PerItemStages:
    """单条内容在各阶段的文本快照"""
    source: dict
    tag: str
    role: str
    history_depth: int | None
    raw: str
    after_before_macro_regex: str
    after_macro: str
    after_regex: str

class VariableState:
    local: dict
    global_: dict   # 前端 JSON key 用 "global"
```

### Message 类型

```python
class Message:
    role: str       # system / user / assistant / thinking
    content: str
    name: str | None
```

> **注**：`thinking` role 用于 extended thinking 模型输出。sandbox 场景未来可能需要 `tool` role，
> 但当前 regex_replace 的 `ROLE_SET` 仅含 `{user, assistant, system}`，`thinking` 消息会透传不被正则处理。
> 后续按需扩展。

## API 端点

在 `/api/workflow/smarttavern/prompt_engine/` 下新增两个端点：

### `build` — 组装提示词（不调 LLM）

```
POST /api/workflow/smarttavern/prompt_engine/build
Input: BuildParams
Output: BuildResult
```

用途：
- 前端 stage inspector 预览
- 沙盒卡 `STSandbox.complete()` 的组装阶段
- 调试与问题定位

**副作用**：默认会持久化变量（与 `route_with_hooks` 行为一致）。设 `dry_run: true` 可跳过变量写入，用于纯预览场景。

### `complete` — 组装 + LLM 调用

```
POST /api/workflow/smarttavern/prompt_engine/complete
Input: BuildParams + LLM 参数（从 llm_config_file 加载，或直传覆盖）
       target_node_id 在 BuildParams 中传入
Output: SSE stream (stages / chunk / finish / usage / postprocess / error / end)
```

SSE 事件流增加一个 `stages` 事件（在 `chunk` 之前发送，仅 `include_stages=true` 时）：

```json
{ "type": "stages", "data": { "raw": [...], "after_before_macro_regex": [...], "after_macro": [...], "after_regex": [...] } }
```

## Hook 执行

新端点**必须**与 `prompt_router` 共享同一套 hook 执行路径。17 个 hook point 全部触发：

```
资产阶段:     beforeNormalizeAssets → afterNormalizeAssets
组装阶段:     beforeRaw → afterInsert → afterRaw
后处理阶段:   beforePostprocess{User,Assistant} → afterPostprocess{User,Assistant}
变量阶段:     beforeVariablesSave → afterVariablesSave
LLM 阶段:     beforeLLMCall → afterLLMCall (仅 complete)
流式阶段:     beforeStreamChunk → afterStreamChunk (仅 complete + stream)
保存阶段:     beforeSaveResponse → afterSaveResponse (仅 complete)
```

这保证插件在新旧端点上行为一致，不产生分叉。

## 与现有模块的映射

引擎内部调用现有模块，不重写逻辑：

```
BuildParams
  │
  ├─ 资产加载 + assets_normalizer.normalize()
  │   [hook: beforeNormalizeAssets / afterNormalizeAssets]
  │   注：normalize 作用于资产（preset/worldbook/character/regex），发生在消息读取之前
  │
  ├─ 消息读取
  │   threaded: chat_branches/openai_messages（树 → 扁平路径）
  │   sandbox:  直接使用 BuildParams.messages（跳过 conversation_file）
  │
  ├─ prompt_raw.assemble_full()        → 消息组装（framing_prompt + in_chat_constructor）
  │   [hook: beforeRaw / afterInsert / afterRaw]
  │   → 产出 stage: raw
  │
  ├─ prompt_postprocess.apply()        → 后处理管线
  │   [hook: beforePostprocess{User,Assistant} / afterPostprocess{User,Assistant}]
  │   ├─ regex_replace(placement=before_macro)  → stage: after_before_macro_regex
  │   ├─ macro.process()                        → stage: after_macro
  │   └─ regex_replace(placement=after_macro)   → stage: after_regex
  │
  ├─ variables_update.save()           → 变量持久化（dry_run 时跳过）
  │   [hook: beforeVariablesSave / afterVariablesSave]
  │
  └─ (complete 模式) llm_api.chat()    → SSE stream
      [hook: beforeLLMCall / afterLLMCall / beforeStreamChunk / afterStreamChunk]
      [hook: beforeSaveResponse / afterSaveResponse]
```

## Threaded vs Sandbox 输入适配

### Threaded 模式

```python
# 前端传入
BuildParams(
    conversation_file="conversations/abc/conversation.json",
    character_file="characters/luna/character.json",
    preset_file="presets/default/preset.json",
    # ...
    view="assistant_view",
)

# 引擎内部：
# 1. 从 conversation_file 读取消息树 → 展开当前活跃路径 → messages
# 2. 从 settings.json 补全未显式指定的资产引用
```

### Sandbox 模式

```python
# 沙盒 Bridge 传入
BuildParams(
    messages=[
        Message(role="user", content="讲个故事"),
        Message(role="assistant", content="从前有座山..."),
        Message(role="user", content="继续"),
    ],
    extra_system="你是一个互动小说引擎，请用第二人称叙述",
    character_file="characters/suying/character.json",
    preset_file="presets/default/preset.json",
    # ...
    view="assistant_view",
    dry_run=True,  # sandbox 默认不持久化变量
)

# 引擎内部：
# 1. messages 直接使用，不从 conversation_file 读取（需要新代码路径，
#    当前 route_process_view_impl Step 5 必读 conversation_file）
# 2. extra_system 插入到角色描述之后、对话消息之前，
#    携带 source={type: "sandbox.extra_system", id: "extra_system"}
# 3. 其余流程完全相同
```

## 前端对接

moonlit-whispers 的 `src/api/` 新增：

```typescript
// src/api/promptEngine.ts
import { apiPost, streamSSE } from './client';

const BASE = 'workflow/smarttavern/prompt_engine';

export const promptEngine = {
  build: (params: BuildParams) =>
    apiPost<BuildResult>(`${BASE}/build`, params),

  complete: (params: BuildParams, onEvent: (e: SSEEvent) => void, signal?: AbortSignal) =>
    streamSSE(`${BASE}/complete`, params, onEvent, signal),
};
```

> **注**：`SSEEvent` 类型需新增 `stages` 事件。当前前端 SSE consumer 只处理
> `chunk / finish / usage / postprocess / error / end`，需要扩展。

## 未做的（后续 RFC）

- **Token 预算管理**：截断策略、固定区域保护（安全提示 / 角色人设不优先丢弃）
- **vector 激活**：世界书 `activationMode=vector` 的向量搜索回调
- **前端预览运行时**：用 fast-tavern NPM 包在浏览器端做轻量预览（不含 hooks）
- **conformance tests**：对齐 fast-tavern 的测试 fixture，验证输出一致性；hook 对等性测试（新旧端点行为一致）
- **per-rule sandbox 控制**：`applyInSandbox` 字段区分管线清理 vs 视觉装饰正则
- **output_format / system_role_policy**：tagged 输出格式和 system→user 角色转换。当前后端无实现，v1 暂不纳入，待需求明确后单独 RFC

## 兼容性

- 现有的 `prompt_router/complete_with_hooks` 和 `prompt_router/route_with_hooks` 继续可用
- 新端点是并行路径，不是替换，共享同一套 hook 执行
- moonlit-whispers 应做能力探测：优先调 `prompt_engine`，fallback 到 `prompt_router`
- 待 moonlit-whispers 稳定后，旧端点可标记 deprecated

## 前端对接进度（moonlit-whispers）

| commit | 内容 | plan |
|--------|------|------|
| `c588b74` | 最小端到端对话流：启动 hydrate、newChat 后端创建、handleSend 消息同步 + 流式 | `/root/.claude/plans/rustling-pondering-pony.md` |
| `11ed053` | 修复竞态/PID 链/错误处理：handleSend 竞态守卫、PID 链提前更新、catch 分路径、active preset/persona | — |
| `1c30c7c` | 开发环境：Vite proxy `/api` → `localhost:8050`；修 health 端点路径 + 空 base 守卫 | — |
| `e7b7300` | API 命名空间全修正（7 个 BASE 加 `modules/`/`workflow/` 前缀）；ChatInput 改用 `promptRouter.completeStream`；删除 greeting 重复插入；启动时加载角色 greeting（first_mes + alternate_greetings）和 LLM 配置；凭证持久化（setAsActive → updateLlmConfigFile）；连接测试改 listModels；创建对话传 llm_config_file | `/root/.claude/plans/parallel-launching-unicorn.md` |
| `c44475b` | 修复 LLM config hydrate 顺序不确定：`Promise.all` + `push` 改为 map+filter 保持后端列表顺序 | — |
| `cabec0c` | testConnection 改用真实 chat 探测（`max_tokens=16`），成功显示响应时间，失败 toast 弹出原始错误；URL 预览面板（debounced `preview_urls`）；新建连接命名流程；后端 `b8b6bab` 配套 `normalize_base_url` + `preview_urls` 端点 + 修 Anthropic listModels 双 `/v1` | `/root/.claude/plans/magical-percolating-pine.md` |
| `ee85b47`→`4206d17` | API 连接 Zustand persist（localStorage）；persist merge 补 `status: 'idle'`；合并策略（后端优先 + 本地独有保留，`isActive` 去重）；空连接空状态 UI；保存 toast；`deleteApiConnection` fallback 修正；testConnection 检查 `success` 字段（后端 200+`success:false` 不再误判为成功） | `/root/.claude/plans/persist-api-connections.md` |
