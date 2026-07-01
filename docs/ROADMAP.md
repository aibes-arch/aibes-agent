# minagent 版本演进计划

> **版本**: 0.1.0  
> **最后更新**: 2026-07-01  
> **关联文档**: [架构设计](./ARCHITECTURE.md)、[模块设计](./MODULE_DESIGN.md)

---

## 1. 版本策略

`minagent` 采用**语义化版本**（SemVer）：

- **MAJOR**：不兼容的 API 变更。
- **MINOR**：新增功能，保持向后兼容。
- **PATCH**：Bug 修复与性能优化。

每个 MINOR 版本聚焦一个核心主题，保持“小步快跑、快速验证”的节奏。

---

## 2. 版本总览

| 版本 | 主题 | 状态 | 目标时间 |
|-----|------|------|---------|
| **v0.1.0** | MVP：Agent Loop + 基础工具 + 权限系统 | 🚧 已可用 | 2026-07 |
| **v0.2.0** | 子 Agent、上下文压缩增强、任务管理升级 | 📋 规划中 | 2026-Q3 |
| **v0.3.0** | MCP 支持、Web UI、Skill 系统 | 📋 规划中 | 2026-Q4 |
| **v0.4.0** | 领域工具包（钻井工程、代码审查） | 📋 规划中 | 2027-Q1 |
| **v1.0.0** | 稳定版：完整测试、文档、生产可用 | 📋 远期 | 待定 |

---

## 3. v0.1.0 — MVP（当前版本）

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
| `cli` | `minagent <script.py>` 命令行入口 |
| 日志与事件流 | `loguru` + 事件流，支持可观测性 |

### 3.3 已知限制

- `ask` 权限模式尚未接入真实交互，当前自动通过。
- 上下文压缩是“截断式”而非“摘要式”。
- 没有持久化记忆，进程结束后状态丢失。
- 工具错误处理偏简单，缺少重试和回退。
- 缺少子 Agent 能力。

---

## 4. v0.2.0 — Agent 协作与上下文增强

### 4.1 目标

让 `minagent` 能处理更复杂的任务：任务分解、子 Agent 协作、更智能的上下文管理。

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

## 5. v0.3.0 — MCP、Web UI 与 Skill 系统

### 5.1 目标

扩展 `minagent` 的接入能力和易用性：接入外部工具生态、提供图形化界面、支持项目级技能配置。

### 5.2 计划功能

| 功能 | 说明 | 优先级 |
|-----|------|--------|
| **MCP 客户端** | 通过 [Model Context Protocol](https://modelcontextprotocol.io/) 调用外部 MCP 服务器 | P0 |
| **Web UI** | 基于 FastAPI + SSE/WebSocket 的实时 Web 界面 | P0 |
| **Skill 系统** | 按项目加载 `.minagent/skills/` 下的自定义 prompt 和工具组合 | P0 |
| **配置文件化** | 支持 `minagent.yaml` 配置 LLM、工具、权限、Skill | P1 |
| **会话持久化** | 保存/恢复对话历史、任务状态 | P1 |
| **多模型路由** | 根据任务类型选择不同模型 | P2 |

### 5.3 Skill 系统草案

项目目录下创建 `.minagent/skills/code-review/skill.yaml`：

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

## 6. v0.4.0 — 领域工具包

### 6.1 目标

将 `minagent` 从通用框架扩展为特定领域的实用 Agent。

### 6.2 计划领域

| 领域 | 典型工具 | 场景 |
|-----|---------|------|
| **钻井工程代码分析** | `ParseWitsmlTool`、`AnalyzeDrillingLogTool`、`ValidateFormulaTool` | 解析钻井数据、验证算法、生成报告 |
| **代码审查** | `GitDiffTool`、`CoverageTool`、`LintTool` | 自动 review PR、跑测试、检查覆盖率 |
| **文档处理** | `PdfExtractTool`、`MarkdownMergeTool` | 批量处理技术文档 |

### 6.3 领域工具设计原则

- 领域工具包以**可选依赖**形式提供，例如 `pip install minagent[drilling]`。
- 每个领域包包含自己的 tools、skills、prompts 和示例脚本。
- 不影响核心框架的轻量性。

---

## 7. 长期规划（v1.0+）

| 方向 | 目标 |
|-----|------|
| **稳定性** | 单元测试覆盖率 > 80%，集成测试覆盖主要工具 |
| **性能** | 并发工具池、连接池、流式 LLM 响应 |
| **安全** | 真正的权限交互、命令白名单、沙箱执行 |
| **可观测性** | 结构化日志、Trace、审计回放 |
| **多模态** | 支持图片、PDF、Notebook 等输入 |
| **企业级** | RBAC、审计日志、团队共享 Skill |

---

## 8. 参与贡献

每个版本都会优先实现社区反馈最强烈的功能。如果你有需求，可以：

1. 在 `examples/` 下提交新的使用场景示例。
2. 为 `minagent.tools` 添加新工具。
3. 完善文档和测试。

---

*参考：`README.md` Roadmap、`docs/references/05_Claude_Code_源码架构分析.md`*
