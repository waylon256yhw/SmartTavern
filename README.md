# SmartTavern

基于 ModularFlow Framework 的模块化 AI 聊天与角色扮演平台，参考 SillyTavern 设计，提供更灵活的插件架构和项目管理能力。

## 功能特性

- **AI 对话**：支持多种 LLM 后端（OpenAI、Claude、本地模型等），流式/非流式补全
- **角色扮演**：角色卡、人设、世界书、正则替换规则，构建沉浸式对话体验
- **对话分支**：聊天历史树状管理，支持分支、回溯、重试
- **提示词工程**：可视化 Prompt 编辑器，支持宏变量、多阶段后处理管线
- **插件系统**：前后端双插件架构，Hook 机制，热加载
- **项目管理**：动态发现与管理多个前后端子项目，自动端口分配
- **主题与背景**：可自定义主题和聊天背景
- **国际化**：内置 i18n 支持

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+ / FastAPI / Uvicorn / uv |
| 前端 | Vue 3 / TypeScript / Vite / Pinia / Tailwind CSS / Bun |
| 通信 | REST + WebSocket（统一网关） |
| 图片处理 | Pillow（PNG 元数据嵌入/提取） |

## 快速开始

### 环境要求

- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Python >= 3.10（uv 会自动管理）
- [Bun](https://bun.sh/)（前端包管理与构建）

### Docker 部署（推荐）

```bash
docker compose up -d
```

多阶段构建自动完成前端（Bun）和后端（Python）的打包，单容器运行在 `http://localhost:8050`。

- 对话数据持久化到 `./backend_projects/SmartTavern/data`
- LLM 配置通过 `./api-config.json` 挂载（只读）

### 本地开发

```bash
# 1. 安装后端依赖（自动创建 .venv）
uv sync

# 2. 安装前端依赖
cd frontend_projects/SmartTavern && bun install && cd ../..

# 3. 启动后端 API 网关（默认监听 0.0.0.0:8050）
uv run smarttavern

# 4. 启动前端开发服务器（另开终端）
cd frontend_projects/SmartTavern && bun run dev
```

开发模式下前端 Vite 运行在 `http://localhost:5173`，后端 API 文档位于 `http://localhost:8050/docs`。

支持 `--reload` 热重载后端：

```bash
uv run smarttavern --reload
```

### 本地生产模式

不使用 Docker 时，`--serve` 会自动构建前端并以单端口提供服务：

```bash
uv run smarttavern --serve          # 首次自动构建前端
uv run smarttavern --serve --rebuild  # 强制重新构建
```

Windows 用户可直接双击 `Start.bat` 一键启动（需预装 uv）。

## 项目结构

```
SmartTavern/
├── Dockerfile                     # 多阶段构建（Bun 前端 + Python 后端）
├── docker-compose.yml             # 容器编排
├── pyproject.toml                 # 项目元数据与依赖（uv/hatchling）
├── start_all_apis.py              # 后端统一入口（uv run smarttavern）
├── core/                          # 框架核心
│   ├── api_gateway.py             #   FastAPI 网关（REST + WebSocket）
│   ├── api_registry.py            #   API 注册中心（@register_api）
│   ├── api_client.py              #   SDK 客户端（HTTP + 进程内直调）
│   └── services.py                #   模块发现与服务管理
├── api/
│   ├── modules/                   #   功能模块 API
│   │   ├── project_manager/       #     项目生命周期管理
│   │   ├── llm_api/               #     LLM 调用封装
│   │   └── SmartTavern/           #     聊天/角色/世界书/正则等
│   ├── workflow/                   #   工作流 API（对话补全管线）
│   └── plugins/                   #   插件 API（Hook 管理）
├── backend_projects/              # 后端子项目
│   ├── SmartTavern/               #   主后端（含 4 个插件）
│   └── ProjectManager/            #   项目管理后端
├── frontend_projects/             # 前端子项目
│   ├── SmartTavern/               #   主 UI（Vue 3）
│   ├── PromptEditor/              #   Prompt 编辑器
│   └── ProjectManager/            #   管理面板
└── DEVELOPMENT_NOTES.md           # 开发者规范文档
```

## 架构概览

### 后端

所有 API 模块通过 `@register_api` 装饰器自动注册到全局 `FunctionRegistry`，由 `APIGateway` 统一暴露为 REST/WebSocket 端点。模块间调用强制走 `core.call_api()` 门面，禁止直接 import 其他模块实现。

支持进程内直调优化（`MF_INPROC=1`），同进程调用绕过 HTTP 开销。

### 前端

采用 Workflow Host 事件驱动架构：

```
Vue 组件 ←→ Pinia Store ←→ Bridge Controller ←→ Channel ←→ 后端 API
```

核心流程（用户发消息 → AI 回复）：

```
InputRow → completionBridge → chat_completion API
  → assets_normalizer → prompt_raw → prompt_postprocess → llm_api
  → chat_branches（保存） → 前端 SSE 流式渲染
```

## 开发文档

详细的开发规范（API 调用约定、端口管理、模块注册、WebSocket 协议等）请参阅 [DEVELOPMENT_NOTES.md](DEVELOPMENT_NOTES.md)。
