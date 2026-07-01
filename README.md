# minagent — 最小 Python Agent 框架

> 一个受 Claude Code 启发的最小 Agent 框架，用于构建代码分析、文档处理、自动化任务等领域的 Agent。
>
> **设计原则**：简单、可扩展、可验证。
>
> **版本**: 0.2.0

---

## 一、项目定位

`minagent` 是一个轻量级 Python 框架，让开发者能在几小时内搭建一个具备以下能力的 Agent：

- 通过自然语言接收任务
- 调用工具（读文件、写文件、执行命令、搜索代码等）
- 自主多轮循环直到任务完成
- 可控的权限系统
- 可扩展的工具注册机制
- 基础的上下文管理

**不是** 要替代 Claude Code，而是：
- 快速验证 Agent 思路
- 作为领域专用 Agent（如钻井工程代码分析）的起点
- 学习和教学用途

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  User Interface (CLI / API / Notebook)                       │
│  - 接收用户输入                                              │
│  - 渲染工具执行结果                                          │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent Engine (minagent.core.engine)                         │
│  - 管理 Agent 生命周期                                        │
│  - 编排 LLM 调用与工具执行                                    │
│  - 维护 conversation context                                  │
│  - 处理错误与最大轮数                                         │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM Provider (minagent.core.llm)                            │
│  - OpenAI 兼容 API                                            │
│  - function calling / tool calls                              │
│  - 支持本地模型（qwen3-coder-plus 等）                        │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Tool Registry (minagent.core.tool_registry)                 │
│  - 工具注册与发现                                             │
│  - schema 生成                                                │
│  - 并发/串行编排                                              │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Tools (minagent.tools.*)                                    │
│  - FileReadTool, FileWriteTool, FileEditTool                 │
│  - BashTool, GrepTool, GlobTool, GitTool                     │
│  - TaskListTool, AgentTool (子 Agent)                         │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Permission Engine (minagent.permissions.engine)             │
│  - 规则匹配                                                   │
│  - 风险分类                                                   │
│  - 交互式确认 / 自动模式                                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 |
|------|------|
| `core.engine` | AgentLoop：管理 LLM 调用与工具执行的循环 |
| `core.llm` | LLM 接口封装，统一 OpenAI 兼容调用 |
| `core.tool_registry` | 工具注册、schema 转换、工具发现 |
| `core.context` | 会话上下文、消息历史、token 估算 |
| `core.events` | 事件流，用于 UI 实时展示 |
| `tools.base` | 工具基类、ToolResult、ToolContext |
| `tools.fs` | 文件操作工具 |
| `tools.shell` | Bash/Shell 执行工具 |
| `tools.search` | Grep/Glob 搜索工具 |
| `tools.git` | Git 操作工具 |
| `tools.task` | 任务列表工具 |
| `permissions.engine` | 权限规则引擎 |
| `permissions.rules` | 文件/Shell 规则定义 |

### 2.3 数据流

```
用户输入
    │
    ▼
AgentLoop.run(task)
    │
    ▼
构建 messages = [system prompt] + [history] + [user task]
    │
    ▼
调用 LLM.chat(messages, tools)
    │
    ▼
解析 response.tool_calls
    │
    ▼
权限检查 (PermissionEngine.check)
    │
    ▼
工具执行 (ToolRegistry.execute)
    │
    ├─ 只读工具：并发执行
    ├─ 写入工具：串行执行
    └─ 生成 tool_result
    │
    ▼
将 tool_result 加入 messages
    │
    ▼
循环（直到无 tool_calls 或达到最大轮数）
    │
    ▼
返回最终回复
```

---

## 三、技术选型

| 层面 | 选型 | 理由 |
|------|------|------|
| **语言** | Python 3.11+ | 生态丰富、数据/AI 工具强、易于快速迭代 |
| **Pydantic** | v2 | 类型校验、schema 生成、工具输入输出定义 |
| **LLM API** | OpenAI 兼容接口 | 支持 OpenAI、Anthropic（通过 proxy）、本地模型（vLLM、LM Studio、Ollama） |
| **HTTP 客户端** | `httpx` | 异步、高性能、支持流式 |
| **Shell 执行** | `asyncio.create_subprocess_exec` | 原生异步、跨平台 |
| **代码搜索** | `ripgrep` | 极快、跨平台、支持正则 |
| **配置** | Pydantic Settings + YAML | 结构化配置、环境变量支持 |
| **日志** | `loguru` | 彩色日志、结构化输出 |
| **CLI** | `typer` | 快速构建命令行界面 |
| **测试** | `pytest` | Python 标准测试框架 |
| **可选 UI** | Rich / Textual | 终端富文本显示 |

---

## 四、功能设计

### 4.1 核心功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| Agent 主循环 | 自动调用 LLM、执行工具、多轮对话 | P0 |
| 工具注册 | 通过装饰器或类注册工具 | P0 |
| 工具执行 | 支持只读并发、写入串行 | P0 |
| 权限控制 | 文件/Shell 操作权限检查 | P0 |
| 上下文管理 | 消息历史、system prompt、token 估算 | P0 |
| 错误处理 | 工具失败、API 失败、超时恢复 | P0 |
| 事件流 | 实时输出工具执行事件 | P1 |
| 子 Agent | 支持简单的子 Agent 调用 | P2 |
| 上下文压缩 | 超长消息自动压缩 | P2 |

### 4.2 工具清单（MVP）

| 工具 | 功能 | 读写 | 并发 |
|------|------|------|------|
| `FileReadTool` | 读取文件内容 | 读 | ✅ |
| `FileWriteTool` | 创建或覆盖文件 | 写 | ❌ |
| `FileEditTool` | 按 diff 修改文件 | 写 | ❌ |
| `BashTool` | 执行 shell 命令 | 写/读 | 视命令 |
| `GrepTool` | ripgrep 内容搜索 | 读 | ✅ |
| `GlobTool` | 文件枚举 | 读 | ✅ |
| `TaskListTool` | 任务列表管理 | 写 | ❌ |
| `AgentTool` | 调用子 Agent | 写 | ❌ |

### 4.3 权限设计

| 模式 | 说明 |
|------|------|
| `ask` | 每次危险操作都询问 |
| `auto` | 安全操作自动允许，危险操作询问 |
| `full_auto` | 全部自动（仅用于可信环境） |

权限规则：

```yaml
permissions:
  mode: auto
  filesystem:
    - allow: read
      path: /c/aibes/**
    - deny: write
      path: /c/aibes/aibes-vault/**
    - allow: write
      path: /c/aibes/minagent/**
  shell:
    - allow: "git .*"
    - deny: "rm -rf /"
    - ask: "sudo .*"
```

---

## 五、快速开始

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置环境变量（或 config.yaml）
export OPENAI_BASE_URL=http://192.168.2.179:1234/v1
export OPENAI_API_KEY=sk-xxx
export MINAGENT_MODEL=qwen3-coder-plus-32k

# 3. 运行示例
minagent examples/readme_demo.py
```

---

## 六、文件结构

```
minagent/
├── minagent/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py          # AgentLoop
│   │   ├── llm.py             # LLM 客户端
│   │   ├── tool_registry.py   # 工具注册表
│   │   ├── context.py         # 上下文管理
│   │   └── events.py          # 事件流
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py            # 工具基类
│   │   ├── fs.py              # 文件工具
│   │   ├── shell.py           # Bash 工具
│   │   ├── search.py          # Grep/Glob 工具
│   │   ├── git.py             # Git 工具
│   │   └── task.py            # 任务列表工具
│   ├── permissions/
│   │   ├── __init__.py
│   │   ├── engine.py          # 权限引擎
│   │   └── rules.py           # 规则定义
│   └── utils/
│       ├── __init__.py
│       ├── tokens.py          # token 估算
│       └── format.py          # 格式化
├── tests/
│   ├── __init__.py
│   ├── test_engine.py
│   ├── test_tools.py
│   └── test_permissions.py
├── examples/
│   ├── __init__.py
│   ├── readme_demo.py
│   └── code_review.py
├── config.example.yaml
├── pyproject.toml
├── README.md
└── docs/
    ├── README.md              # 文档中心索引
    ├── ARCHITECTURE.md        # 架构设计
    ├── MODULE_DESIGN.md       # 模块设计
    ├── API_REFERENCE.md       # API 参考
    ├── ROADMAP.md             # 版本演进
    ├── QUICK_START.md         # 快速开始
    ├── TOOL_DEVELOPMENT.md    # 工具开发指南
    ├── DOMAIN_CASE.md         # 领域案例
    ├── CONTRIBUTING.md        # 贡献指南
    └── references/            # 参考资料
```

---

## 七、设计原则

1. **简单优先**：MVP 只实现最核心能力，避免过度设计。
2. **可扩展**：工具、权限、LLM 都通过接口抽象，便于替换。
3. **类型安全**：全代码使用 Pydantic v2 做输入输出校验。
4. **异步原生**：工具执行使用 asyncio，避免阻塞。
5. **可测试**：核心模块都有单元测试。
6. **可观测**：通过事件流输出每一步操作，便于审计和调试。

---

## 八、Roadmap

| 版本 | 目标 |
|------|------|
| 0.1.0 | MVP：AgentLoop + 基础工具 + 权限系统 |
| 0.2.0 | 子 Agent、上下文压缩增强、TaskList 增强、权限 ask 交互、工具缓存、重试、统计 |
| 0.3.0 | MCP 支持、Web UI、Skill 系统 |
| 0.4.0 | 领域工具包（钻井工程、代码审查） |
| 0.3.0 | MCP 支持、Web UI、Skill 系统 |
| 0.4.0 | 领域工具包（钻井工程、代码审查） |

---

*最后更新：2026-06-30*
