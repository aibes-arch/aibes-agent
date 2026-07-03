# aibes-agent 版本演进计划

> **版本**: 0.6.0  
> **最后更新**: 2026-07-02  
> **关联文档**: [架构设计](./ARCHITECTURE.md)、[模块设计](./MODULE_DESIGN.md)

---

## 1. 版本策略

`aibes-agent` 采用**语义化版本**（SemVer）：

- **MAJOR**：不兼容的 API 变更。
- **MINOR**：新增功能，保持向后兼容。
- **PATCH**：Bug 修复与性能优化。

每个 MINOR 版本聚焦一个核心主题，保持“小步快跑、快速验证”的节奏。

---

## 2. 版本总览

| 版本 | 主题 | 状态 | 目标时间 |
|-----|------|------|---------|
| **v0.1.0** | MVP：Agent Loop + 基础工具 + 权限系统 | ✅ 已完成 | 2026-07 |
| **v0.2.0** | 子 Agent、上下文压缩增强、任务管理升级、权限 ask 交互、工具缓存、重试、统计 | ✅ 已完成 | 2026-07 |
| **v0.3.0** | MCP 支持、Web UI、Skill 系统 | ✅ 已完成 | 2026-07 |
| **v0.4.0** | Plugin 机制、领域工具包扩展 | ✅ 已完成 | 2026-07 |
| **v0.5.0** | 会话与 Memory 增强 | ✅ 已完成 | 2026-07 |
| **v0.6.0** | Planner 与任务编排 | ✅ 已完成 | 2026-07 |
| **v0.7.0** | Workflow Engine | 📋 已规划 | 待定 |
| **v0.8.0** | 桌面 / TUI / IDE 插件 | 📋 已规划 | 待定 |
| **v1.0.0** | 稳定版：完整测试、文档、生产可用 | 📋 远期 | 待定 |

---

## 3. 能力全景与版本对照

| 能力 | 当前状态 | 目标版本 | 说明 |
|------|----------|----------|------|
| **Agent Runtime** | ✅ 完整 | v0.1.0 | `AgentLoop` + `LLMClient` + `ToolRegistry`，ReAct 风格循环 |
| **Context 管理** | ✅ 完整 | v0.1.0 | `ContextWindow`、token 估算、自动压缩 |
| **权限系统** | ✅ 完整 | v0.1.0 | `PermissionEngine` 规则引擎 |
| **子 Agent** | ✅ 完整 | v0.2.0 | `AgentTool` / `AgentProfile` |
| **Skill Loader** | ✅ 完整 | v0.3.0 | `.aibes-agent/skills/` YAML 加载与合并 |
| **MCP Client** | ✅ 完整 | v0.3.0 | `MCPClient` + `MCPTool`，支持 stdio/SSE |
| **Web UI** | ✅ 完整 | v0.3.0 | FastAPI + SSE 实时界面 |
| **Plugin Manager** | ✅ 完整 | v0.4.0 | 本地目录 + entry point 插件发现与加载 |
| **Session 管理** | ✅ 完整 | v0.5.0 | 支持 file/memory/sqlite/redis 后端，提供 delete/clear/cleanup API |
| **Memory** | ⚠️ 部分 | v0.5.0/v0.6.0 | `MemoryStore` 抽象、`InMemoryMemoryStore`、可选 `ChromaMemoryStore`、`MemoryTool`；语义 embedding 记忆为可选增强 |
| **Planner** | ✅ 完整 | v0.6.0 | `Planner` + `PlanExecutor` + `PlannerTool`，支持计划生成、校验、依赖执行与重规划 |
| **Workflow Engine** | ❌ 缺失 | v0.7.0 | 计划 DAG/状态机工作流引擎 |
| **CLI / Web UI** | ✅ 完整 | v0.1.0/v0.3.0 | CLI 与 Web UI 已可用 |
| **Desktop / GUI** | ❌ 缺失 | v0.8.0 | 计划 TUI、VS Code / JetBrains 插件 |

---

## 4. v0.1.0 — MVP

### 3.1 目标

验证“最小 Agent 闭环”是否成立：

> 自然语言任务 → LLM 推理 → 工具调用 → 结果回注 → 多轮循环 → 最终答案

### 3.2 已实现功能

| 模块 | 功能 |
|-----|------|
| `core.engine` | `AgentConfig` / `AgentLoop`：ReAct 风格多轮循环 |
| `core.llm` | OpenAI 兼容 API 客户端，支持 `tools` + `tool_choice: auto` |
| `core.context` | `ContextWindow` / `Message`，基础 token 估算与压缩 |
| `core.tool_registry` | 工具注册、schema 转换、并发/串行编排 |
| `tools.fs` | `FileRead` / `FileWrite` / `FileEdit` |
| `tools.search` | `Grep`（ripgrep） / `Glob` |
| `tools.shell` | `Bash`（基于 `asyncio.create_subprocess_shell`） |
| `tools.task` | 简单任务列表 |
| `permissions.engine` | 三级权限模式（ask / auto / full_auto） |
| `cli` | `aibes-agent <script.py>` 命令行入口 |
| 日志与事件流 | `loguru` + 事件流，支持可观测性 |

### 3.3 已知限制

- `ask` 权限模式尚未接入真实交互，当前自动通过。
- 上下文压缩是“截断式”而非“摘要式”。
- 没有持久化记忆，进程结束后状态丢失。
- 工具错误处理偏简单，缺少重试和回退。
- 缺少子 Agent 能力。

---

## 5. v0.2.0 — Agent 协作与上下文增强

### 4.1 目标

让 `aibes-agent` 能处理更复杂的任务：任务分解、子 Agent 协作、更智能的上下文管理。

### 4.2 计划功能

| 功能 | 说明 | 优先级 |
|-----|------|--------|
| **子 Agent（AgentTool）** | 允许 Agent 调用子 Agent 完成独立子任务 | P0 |
| **上下文压缩增强** | 基于 LLM 生成历史摘要，替代简单截断 | P0 |
| **任务列表增强** | 支持子任务、依赖关系、进度追踪 | P1 |
| **权限 ask 模式真实交互** | CLI 中弹出确认提示，支持 `yes/no/yes-to-all` | P1 |
| **工具结果缓存** | 缓存文件读取、搜索结果，避免重复调用 | P1 |
| **错误恢复** | 工具失败自动重试、降级、报告 | P2 |
| **Cost/Token 统计** | 累计 token 消耗、轮数、耗时 | P2 |

### 4.3 AgentTool 设计草案

```python
class AgentTool(Tool):
    name = "Agent"
    description = "Delegate a sub-task to a specialized sub-agent."
    input_model = AgentInput

class AgentInput(BaseModel):
    task: str = Field(..., description="Sub-task description")
    agent_profile: str = Field("default", description="Agent profile name")
```

执行流程：

1. 根据 `agent_profile` 加载对应的 system prompt 和工具集。
2. 创建独立的 `AgentLoop` 和 `ContextWindow`。
3. 运行子任务并返回最终答案给父 Agent。

---

## 6. v0.3.0 — MCP、Web UI 与 Skill 系统

### 5.1 目标

扩展 `aibes-agent` 的接入能力和易用性：接入外部工具生态、提供图形化界面、支持项目级技能配置。

### 5.2 计划功能

| 功能 | 说明 | 优先级 |
|-----|------|--------|
| **MCP 客户端** | 通过 [Model Context Protocol](https://modelcontextprotocol.io/) 调用外部 MCP 服务器 | P0 |
| **Web UI** | 基于 FastAPI + SSE/WebSocket 的实时 Web 界面 | P0 |
| **Skill 系统** | 按项目加载 `.aibes-agent/skills/` 下的自定义 prompt 和工具组合 | P0 |
| **配置文件化** | 支持 `aibes-agent.yaml` 配置 LLM、工具、权限、Skill | P1 |
| **会话持久化** | 保存/恢复对话历史、任务状态 | P1 |
| **多模型路由** | 根据任务类型选择不同模型 | P2 |

### 5.3 Skill 系统草案

项目目录下创建 `.aibes-agent/skills/code-review/skill.yaml`：

```yaml
name: code-review
system_prompt: |
  你是一个严格的代码审查专家，关注：
  1. 正确性
  2. 可维护性
  3. 安全性
  4. 性能
tools:
  - FileRead
  - Grep
  - Bash
```

加载 Skill 后，`AgentLoop` 会自动合并 system prompt 和工具集。

---

## 7. v0.4.0 — Plugin 机制与领域工具包

### 7.1 目标

将 `aibes-agent` 从通用框架扩展为特定领域的实用 Agent。

### 7.2 计划领域

| 领域 | 典型工具 | 场景 |
|-----|---------|------|
| **钻井工程代码分析** | `ParseWitsmlTool`、`AnalyzeDrillingLogTool`、`ValidateFormulaTool` | 解析钻井数据、验证算法、生成报告 |
| **代码审查** | `GitDiffTool`、`CoverageTool`、`LintTool` | 自动 review PR、跑测试、检查覆盖率 |
| **文档处理** | `PdfExtractTool`、`MarkdownMergeTool` | 批量处理技术文档 |

### 7.3 领域工具设计原则

- 领域工具包以**可选依赖**形式提供，例如 `pip install aibes-agent[drilling]`。
- 每个领域包包含自己的 tools、skills、prompts 和示例脚本。
- 不影响核心框架的轻量性。

---

## 8. v0.5.0 — 会话与 Memory 增强

### 8.1 目标

补齐 Session 管理与长期记忆的短板，让 Agent 能够跨会话保持上下文、检索历史知识。

### 8.2 计划功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **多后端 Session Store** | 支持内存、SQLite、Redis 等后端 | P0 |
| **会话清理 API** | 删除、归档、过期清理会话 | P1 |
| **工具结果长期缓存** | 持久化只读工具结果，跨进程复用 | P1 |
| **向量记忆（Vector Memory）** | 基于 embedding 的语义检索记忆 | P2 |
| **记忆摘要** | 自动提炼会话摘要，加速后续加载 | P2 |

---

## 9. v0.6.0 — Planner 与任务编排

### 9.1 目标

从“LLM 隐式选工具”升级为“显式规划 + 执行”的 Agent 模式。

### 9.2 计划功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **独立 Planner 模块** | 根据目标生成可执行计划（步骤、依赖、工具） | P0 |
| **计划验证与回退** | 检查计划可行性，失败后重新规划 | P1 |
| **目标分解** | 自动将复杂任务拆分为子任务 | P1 |
| **与子 Agent 集成** | Planner 决定何时调用哪个 Agent profile | P2 |

---

## 10. v0.7.0 — Workflow Engine

### 10.1 目标

提供可声明、可持久化的工作流引擎，支持多步骤、条件分支、循环和人工审批节点。

### 10.2 计划功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **Workflow DSL** | YAML/JSON 定义 DAG 工作流 | P0 |
| **状态机执行器** | 驱动工作流节点执行、失败重试 | P0 |
| **条件分支与循环** | `if`/`forEach`/`parallel` 节点 | P1 |
| **人工审批节点** | 暂停工作流等待用户确认 | P2 |
| **工作流持久化** | 保存工作流运行状态，支持断点续跑 | P2 |

---

## 11. v0.8.0 — 桌面 / TUI / IDE 插件

### 11.1 目标

在 CLI 和 Web UI 之外，提供更贴近开发者工作流的交互界面。

### 11.2 计划功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **终端 TUI** | 基于 Textual/Rich 的交互式终端界面 | P1 |
| **VS Code 插件** | 在编辑器内直接运行 Agent 任务 | P2 |
| **JetBrains 插件** | IntelliJ/PyCharm 插件支持 | P2 |
| **原生桌面 GUI** | 基于 Qt/Electron 的跨平台客户端（远期） | P3 |

---

## 12. 长期规划（v1.0+）

| 方向 | 目标 |
|-----|------|
| **稳定性** | 单元测试覆盖率 > 80%，集成测试覆盖主要工具 |
| **性能** | 并发工具池、连接池、流式 LLM 响应 |
| **安全** | 真正的权限交互、命令白名单、沙箱执行 |
| **可观测性** | 结构化日志、Trace、审计回放 |
| **多模态** | 支持图片、PDF、Notebook 等输入 |
| **企业级** | RBAC、审计日志、团队共享 Skill |

---

## 13. 参与贡献

每个版本都会优先实现社区反馈最强烈的功能。如果你有需求，可以：

1. 在 `examples/` 下提交新的使用场景示例。
2. 为 `aibes_agent.tools` 添加新工具。
3. 完善文档和测试。

---

*参考：`README.md` Roadmap、`docs/references/05_Claude_Code_源码架构分析.md`*
