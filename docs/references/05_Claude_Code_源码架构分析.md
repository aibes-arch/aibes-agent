# Claude Code 源码架构分析（v2.1.88）

> 基于泄露的 npm 包 source map 提取的 `source/src` 目录（1,332 个 TypeScript 文件）进行分析。
> 分析目的：理解 Claude Code 的 Agent 设计、工具调用机制、上下文管理，为构建自己的代码分析 Agent 提供参考。

---

## 一、仓库概览

| 项目 | 数据 |
|------|------|
| **版本** | @anthropic-ai/claude-code@2.1.88 |
| **源码文件** | 1,332 个 `.ts` / `.tsx` 文件 |
| **解压大小** | 171 MB（含 `cli.js` 和 source map） |
| **构建工具** | Bun（使用 `bun:bundle` 编译时特性） |
| **语言** | TypeScript + React（Ink 终端 UI） |
| **依赖** | 约 2,850 个（npm 依赖，未在源码中展开） |

### 目录结构

```
source/src/
├── assistant/          # 会话历史、助理能力
├── bootstrap/        # 启动状态、会话状态、配置
├── bridge/           # IDE / 浏览器 / 远程桥接
├── buddy/            # 吉祥物/伴侣 Agent（小机器人）
├── cli/              # 命令行入口、传输层、输出处理
├── commands/         # 内置命令（/file, /git, /cost, /plan 等）
├── components/       # React 组件（权限对话框、结构化 diff、agent 等）
├── constants/        # 常量、提示词、限制
├── context/          # 上下文通知、状态
├── coordinator/      # 协调器模式
├── entrypoints/      # SDK 入口、MCP 入口
├── hooks/            # React hooks 和工具使用权限
├── ink/              # 终端 UI 渲染
├── keybindings/      # 快捷键
├── memdir/           # 内存目录/记忆文件
├── migrations/       # 配置迁移
├── moreright/        # 扩展权限
├── native-ts/        # 原生模块桥接
├── outputStyles/     # 输出样式
├── plugins/          # 插件系统
├── query/            # 查询执行、状态转换、token 预算
├── remote/           # 远程会话
├── schemas/          # 数据结构 schema
├── screens/          # 终端屏幕 UI
├── server/           # 本地服务器
├── services/         # 核心服务（API、compact、LSP、MCP、工具执行等）
├── skills/           # Skill 系统
├── state/            # 应用状态
├── tasks/            # 任务管理（本地 shell、后台任务）
├── tools/            # 工具定义（Read、Write、Bash、Grep、Agent、MCP 等）
├── types/            # 类型定义
├── upstreamproxy/    # 上游代理
├── utils/            # 通用工具函数
├── vim/              # Vim 模式
└── voice/            # 语音模式
```

---

## 二、核心架构：三层 Agent 设计

Claude Code 不是简单的"聊天 + 工具"，而是 **三层 Agent 架构**：

```
┌────────────────────────────────────────────────────┐
│  Layer 1: User Interface (CLI / REPL / SDK / IDE)   │
│  - 接收用户输入                                      │
│  - 渲染工具结果                                      │
│  - 管理权限对话框                                    │
└─────────────────────┬────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│  Layer 2: Agent Loop (query.ts / query engine)      │
│  - 调用 LLM                                          │
│  - 解析 tool_use                                     │
│  - 调用工具编排器                                    │
│  - 处理上下文压缩/自动 compact                       │
└─────────────────────┬────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│  Layer 3: Tools & Services                          │
│  - 文件读写                                          │
│  - Shell / Bash 执行                                 │
│  - 代码搜索（Grep/Glob）                             │
│  - 子 Agent 执行                                     │
│  - MCP 服务器                                        │
│  - LSP / Git / 测试框架                              │
└────────────────────────────────────────────────────┘
```

### 2.1 Layer 1：UI 层

Claude Code 的 UI 是 **Ink（React for terminal）** 构建的终端 UI：

- 实时显示工具执行进度（spinner、进度条）
- 渲染结构化 diff、代码高亮
- 权限确认对话框（文件写入、bash 执行等）
- 文件树、上下文可视化

**关键点**：UI 和 Agent Loop 是解耦的。Agent Loop 产生 `Message` 和 `ToolResult`，UI 负责渲染。

### 2.2 Layer 2：Agent Loop

核心入口：`source/src/query.ts`（1,729 行，70KB）。

Agent Loop 的核心流程：

```
1. 准备 system prompt（项目上下文、工具定义、CLAUDE.md）
2. 发送 messages + tools 到 LLM
3. 接收 assistant message
4. 解析 assistant message 中的 tool_use blocks
5. 调用 toolOrchestration 执行工具
6. 将 tool_result 添加到 messages
7. 循环回到步骤 2
8. 直到 assistant 没有 tool_use 或达到最大轮数
```

**关键能力**：
- **上下文压缩（compact）**：当 token 超过阈值时自动压缩历史消息
- **Token 预算管理**：每轮预算、总预算、任务预算
- **工具使用总结（tool use summary）**：压缩历史 tool_use/tool_result
- **自动继续（auto-continue）**：处理 max_output_tokens 限制
- **错误恢复**：API 失败、工具失败、超时处理

### 2.3 Layer 3：工具与服务

工具系统是 Claude Code 的核心竞争力。源码中 `tools/` 目录定义了所有工具。

---

## 三、工具系统：定义、权限与编排

### 3.1 工具定义（Tool.ts）

每个工具通过 `buildTool` 创建，包含丰富的元数据：

```typescript
// source/src/Tool.ts 中的 Tool 类型核心字段
export type Tool<Input, Output, Progress> = {
  name: string                    // 工具名
  aliases?: string[]              // 别名
  searchHint?: string             // 用于 ToolSearch 的关键词
  description(input): string     // 动态描述
  inputSchema: Input              // Zod 输入 schema
  outputSchema?: Output           // Zod 输出 schema
  call(args, context, canUseTool, parentMessage, onProgress): Promise<ToolResult<Output>>
  
  // 权限与安全
  checkPermissions(input, context): Promise<PermissionResult>
  validateInput?(input, context): Promise<ValidationResult>
  isReadOnly(input): boolean
  isDestructive?(input): boolean
  isConcurrencySafe(input): boolean
  toAutoClassifierInput(input): unknown
  
  // UI 渲染
  renderToolUseMessage(...)
  renderToolResultMessage(...)
  getToolUseSummary(input): string | null
  getActivityDescription(input): string | null
  userFacingName(input): string
  
  // 上下文
  maxResultSizeChars: number
  isMcp?: boolean
  isLsp?: boolean
  shouldDefer?: boolean
  alwaysLoad?: boolean
  interruptBehavior?(): 'cancel' | 'block'
}
```

**关键设计**：
- 每个工具都是 **自描述** 的：包含 schema、权限、渲染、并发控制
- 工具通过 `buildTool` 统一注册，便于扩展
- 工具输入/输出都用 Zod 严格校验
- 权限检查在工具调用前执行，与业务逻辑分离

### 3.2 工具分类

Claude Code 的工具分为几大类：

| 类型 | 代表工具 | 说明 |
|------|---------|------|
| **文件读写** | `FileReadTool`, `FileWriteTool`, `FileEditTool` | 核心代码操作 |
| **代码搜索** | `GrepTool`, `GlobTool`, `LSPGrepTool` | ripgrep 封装 |
| **Shell 执行** | `BashTool` | 子进程执行、权限分级 |
| **Agent 协作** | `AgentTool` | 子 Agent 执行 |
| **任务管理** | `TaskCreateTool`, `TaskUpdateTool`, `TaskListTool`, `TaskGetTool`, `TaskStopTool` | 后台任务 |
| **计划模式** | `EnterPlanModeTool`, `ExitPlanModeTool` | 规划与执行分离 |
| **Web 工具** | `WebSearchTool`, `WebFetchTool` | 联网搜索 |
| **MCP 工具** | `MCPTool` | 外部 MCP 服务器 |
| **LSP 工具** | `LSPTool` | 语言服务器协议 |
| **Git 工具** | 内置在 BashTool 中 | diff, commit, branch |
| **Skill 工具** | `SkillTool` | 自定义 skill |
| **定时任务** | `ScheduleCronTool` | cron 任务管理 |
| **消息通知** | `SendMessageTool` | 发送消息（Slack 等） |

### 3.3 工具编排（toolOrchestration.ts）

`source/src/services/tools/toolOrchestration.ts` 是工具执行的核心：

```typescript
// 核心逻辑：将 tool_use 分成串行/并发批次
export async function* runTools(
  toolUseMessages: ToolUseBlock[],
  assistantMessages: AssistantMessage[],
  canUseTool: CanUseToolFn,
  toolUseContext: ToolUseContext,
): AsyncGenerator<MessageUpdate, void> {
  for (const { isConcurrencySafe, blocks } of partitionToolCalls(...)) {
    if (isConcurrencySafe) {
      // 只读工具批量并发执行（默认最多 10 个并发）
      yield* runToolsConcurrently(blocks, ...)
    } else {
      // 写入/破坏性工具串行执行
      yield* runToolsSerially(blocks, ...)
    }
  }
}
```

**关键设计**：
- 只读工具（Grep、Read）可以并发，提升效率
- 写入工具（Write、Edit、Bash 破坏性命令）必须串行，避免冲突
- 通过 `isConcurrencySafe` 动态判断
- 每个 tool 执行都有 `toolUseContext` 共享状态

### 3.4 权限系统

权限系统非常复杂，分布在多个文件中：

| 文件 | 作用 |
|------|------|
| `utils/permissions/PermissionResult.ts` | 权限结果类型 |
| `utils/permissions/filesystem.ts` | 文件读写权限 |
| `utils/permissions/shellRuleMatching.ts` | shell 命令规则匹配 |
| `utils/permissions/yoloClassifier.ts` | 自动模式安全分类器 |
| `components/permissions/FilePermissionDialog/` | 权限对话框 UI |

权限模式：
- **Ask**：每次询问
- **Auto**：安全操作自动允许（只读、项目内写入）
- **Full Auto**：全部自动（危险）
- **分类器**：用 LLM 自动判断命令风险

**设计启示**：权限不能一刀切，需要按操作类型、路径、命令模式细分。

---

## 四、Agent 与子 Agent 设计

### 4.1 AgentTool

`source/src/tools/AgentTool/runAgent.ts`（973 行）实现子 Agent 运行：

```typescript
// 子 Agent 启动时会：
1. 初始化 Agent 特定的 MCP 服务器
2. 创建独立的文件状态缓存
3. 创建子 Agent 上下文（createSubagentContext）
4. 设置 Agent 的 system prompt
5. 执行 Agent 循环
6. 清理资源并返回结果
```

子 Agent 可以：
- 继承父 Agent 的工具和 MCP 服务器
- 定义自己的 MCP 服务器
- 拥有独立的会话记录
- 与父 Agent 共享部分状态

### 4.2 Agent 定义

Agent 定义通过 `loadAgentsDir.ts` 从文件加载，支持：

```yaml
---
name: code-review
model: claude-sonnet-4
prompt: 你是一个代码审查专家，专注于...
tools:
  - FileReadTool
  - GrepTool
  - BashTool
mcpServers:
  - github
---
```

### 4.3 多 Agent 协作模式

Claude Code 支持多种多 Agent 模式：

| 模式 | 说明 |
|------|------|
| **父子 Agent** | 主 Agent 分配任务给子 Agent |
| **并行 Agent** | 多个子 Agent 同时处理不同任务 |
| **后台 Agent** | 子 Agent 在后台持续运行 |
| **Team Agent** | 团队共享记忆和上下文 |

---

## 五、上下文管理：这是 Claude Code 的护城河

### 5.1 上下文组成

Claude Code 的上下文由多个部分组成：

| 来源 | 内容 |
|------|------|
| **System Prompt** | 通用指令、工具定义、当前模型信息 |
| **System Context** | Git 状态、当前目录、文件树、环境变量 |
| **Memory Files** | `CLAUDE.md` 等项目记忆文件 |
| **Skills** | 自定义 Skill 的 prompt 和工具 |
| **MCP Tools** | 外部 MCP 服务器提供的工具 |
| **Agents** | 子 Agent 定义 |
| **Conversation History** | 用户消息、助手消息、工具结果 |
| **Tool Definitions** | 当前加载的工具 schema |

### 5.2 上下文分析（analyzeContext.ts）

`source/src/utils/analyzeContext.ts`（1,382 行）实现了上下文可视化：

- 统计每个部分的 token 占用
- 按类别显示（系统提示、工具、记忆文件、消息等）
- 生成颜色方块图（grid squares）
- 提供 `context` 命令查看

### 5.3 自动压缩（autoCompact）

当上下文超过阈值时，Claude Code 会：

1. **Microcompact**：压缩最近几轮消息
2. **Compact**：生成历史摘要
3. **Snip**：删除早期消息
4. **Context Collapse**：保留关键信息，丢弃细节

**关键设计**：压缩后保留的摘要能被 LLM 理解，而不是简单截断。

### 5.4 文件读取缓存

`source/src/utils/fileStateCache.ts`：

- 缓存文件读取时间戳
- 检测文件在读取后是否被外部修改
- 避免重复读取相同文件
- 写入前检查文件是否被外部修改（防止覆盖）

---

## 六、工具实现细节：以 FileReadTool 和 BashTool 为例

### 6.1 FileReadTool

`source/src/tools/FileReadTool/FileReadTool.ts`（1,183 行，40KB）

功能：
- 读取文本文件（支持 offset/limit 分块）
- 读取图片文件（自动压缩、尺寸限制）
- 读取 PDF 文件（分页提取）
- 读取 Notebook 文件（ipynb）
- 自动加载文件对应目录的 Skill
- 权限检查
- 文件修改检测
- 分析日志

**关键能力**：
- 大文件自动分块读取
- 图片按 token 预算压缩
- PDF 按页数限制
- 读取时自动发现并使用相关 Skill

### 6.2 BashTool

`source/src/tools/BashTool/BashTool.tsx`（1,143 行，162KB）

功能：
- 执行 shell 命令
- 解析命令语义（搜索/读取/列表/静默）
- 超时控制（默认、最大）
- 后台任务支持
- 沙箱模式
- 安全解析（AST 分析）
- 输出图片处理
- Git 操作跟踪

**关键设计**：
- 命令分类（搜索/读取/列表）影响 UI 折叠显示
- 危险命令通过权限系统确认
- 支持长时间运行的后台任务
- 对 `cd` 命令特殊处理，保持当前工作目录

### 6.3 GrepTool

`source/src/tools/GrepTool/GrepTool.ts`（577 行）

封装了 ripgrep，支持：
- 正则搜索
- 文件类型过滤
- 输出模式（content/files/count）
- 上下文行数
- 结果限制（limit/offset 分页）
- 权限检查（只读）

---

## 七、构建自己的代码分析 Agent：参考 Claude Code 的设计

基于以上分析，如果你想构建一个自己的代码分析 Agent（比如钻井工程代码分析 Agent），可以借鉴以下架构：

### 7.1 最小可行架构（MVP）

```
┌─────────────────────────────────────────────┐
│  User Interface (CLI / Web / IDE Plugin)     │
│  - 接收自然语言任务                          │
│  - 显示工具执行进度                          │
│  - 渲染结果                                  │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Agent Loop (Python / Node.js)              │
│  - 调用 LLM                                  │
│  - 解析 tool_use                             │
│  - 工具编排                                  │
│  - 上下文管理                                │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Tools                                       │
│  - FileReadTool                              │
│  - FileWriteTool                             │
│  - BashTool / ShellTool                      │
│  - GrepTool / SearchTool                     │
│  - GitTool                                   │
│  - 领域特定工具（如 parse-drilling-log）      │
└─────────────────────────────────────────────┘
```

### 7.2 推荐技术栈

| 层级 | 推荐选型 | 说明 |
|------|---------|------|
| 后端 | Python 3.11+ | 丰富的生态、数据处理强 |
| 框架 | FastAPI | 异步、类型支持好 |
| LLM | GPT-4o / Claude / Qwen3-Coder | 代码能力强 |
| 工具调用 | OpenAI 兼容 API + function calling | 标准化 |
| 文件搜索 | ripgrep | 快速、跨平台 |
| 数据库 | SQLite / PostgreSQL | 存储记忆、历史 |
| 前端 | React + SSE / WebSocket | 实时显示 |
| 终端 UI | Rich / Textual | 快速 CLI 界面 |

### 7.3 核心模块设计

#### 模块 1：工具注册中心

```python
class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Tool:
        return self.tools.get(name)
    
    def to_openai_schema(self) -> List[dict]:
        return [tool.to_schema() for tool in self.tools.values()]
```

#### 模块 2：Agent Loop

```python
class AgentLoop:
    async def run(self, task: str, context: AgentContext, max_turns=30):
        messages = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": task}
        ]
        
        for turn in range(max_turns):
            response = await llm.chat(messages, tools=context.tools)
            
            if not response.tool_calls:
                return response.content
            
            messages.append(response.to_message())
            
            for tool_call in response.tool_calls:
                result = await self.execute_tool(tool_call, context)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        
        return "达到最大轮数"
```

#### 模块 3：工具基类

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Type

class Tool(ABC):
    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    
    @abstractmethod
    async def call(self, input: BaseModel, context: ToolContext) -> ToolResult:
        pass
    
    def is_read_only(self, input: BaseModel) -> bool:
        return False
    
    def is_concurrency_safe(self, input: BaseModel) -> bool:
        return self.is_read_only(input)
```

#### 模块 4：权限系统

```python
class PermissionEngine:
    def __init__(self, rules: List[PermissionRule]):
        self.rules = rules
    
    async def check(self, tool_name: str, input: dict, context: AgentContext) -> PermissionResult:
        # 1. 应用 always-allow / always-deny 规则
        # 2. 对 bash 命令进行 AST 分析
        # 3. 对文件路径进行模式匹配
        # 4. 高风险操作弹窗确认
        pass
```

#### 模块 5：上下文管理

```python
class ContextManager:
    def __init__(self, max_tokens=128000):
        self.max_tokens = max_tokens
        self.messages = []
    
    def add_message(self, message):
        self.messages.append(message)
        if self.token_count() > self.max_tokens * 0.8:
            self.compact()
    
    def compact(self):
        # 保留最近 N 轮，压缩早期对话为摘要
        pass
    
    def token_count(self):
        # 使用 tokenizer 估算
        pass
```

### 7.4 必备工具清单

| 工具 | 优先级 | 说明 |
|------|--------|------|
| FileReadTool | ⭐⭐⭐ | 读取代码文件 |
| FileWriteTool | ⭐⭐⭐ | 创建/覆盖文件 |
| FileEditTool | ⭐⭐⭐ | 精确修改文件（比全文重写更省 token） |
| BashTool | ⭐⭐⭐ | 运行命令、git、测试 |
| GrepTool | ⭐⭐⭐ | 代码搜索 |
| GlobTool | ⭐⭐ | 文件枚举 |
| GitTool | ⭐⭐ | git diff, log, status |
| TaskListTool | ⭐⭐ | 任务跟踪 |
| AgentTool | ⭐⭐ | 子 Agent 协作 |
| 领域工具 | ⭐⭐⭐ | 根据业务定制 |

### 7.5 领域特定扩展（以钻井工程为例）

可以添加这些自定义工具：

| 工具 | 功能 |
|------|------|
| `ParseWitsmlTool` | 解析 WITSML 钻井数据 |
| `AnalyzeDrillingLogTool` | 分析钻井日志异常 |
| `QueryPinnsTool` | 查询 PINN 文献知识库 |
| `GenerateReportTool` | 生成钻井分析报告 |
| `ValidateFormulaTool` | 验证水力学公式 |

### 7.6 实现路线图

| 阶段 | 目标 | 时间 |
|------|------|------|
| **Phase 1** | 实现基础 Agent Loop + 文件读写 + Bash | 1-2 周 |
| **Phase 2** | 添加 Grep/Glob、Git 集成、上下文管理 | 1-2 周 |
| **Phase 3** | 添加权限系统、任务管理、子 Agent | 2-3 周 |
| **Phase 4** | 添加领域工具、Skill 系统、MCP | 2-3 周 |
| **Phase 5** | 优化 UI、性能、错误恢复、测试 | 持续 |

---

## 八、关键设计教训

1. **工具优先于提示词**：工具的能力决定 Agent 的能力上限
2. **权限系统必须内建**：不要后期补，一开始就要设计
3. **上下文管理是核心**：没有好的上下文管理，Agent 无法处理大项目
4. **只读工具并发、写入工具串行**：这是安全与效率的平衡
5. **结果需要渲染**：用户需要看到工具做了什么，而不是只给 LLM 看
6. **错误处理要详尽**：工具失败、API 失败、超时、权限拒绝都要处理
7. **可观测性**：每一步操作都要记录、可审计、可回滚
8. **渐进式加载**：不要一次加载所有工具，用 ToolSearch 延迟加载

---

## 九、相关文件与延伸阅读

| 文件 | 作用 |
|------|------|
| `source/src/Tool.ts` | 工具类型定义和 buildTool |
| `source/src/services/tools/toolOrchestration.ts` | 工具执行编排 |
| `source/src/services/tools/toolExecution.ts` | 单个工具执行 |
| `source/src/query.ts` | Agent 主循环 |
| `source/src/utils/analyzeContext.ts` | 上下文分析 |
| `source/src/tools/AgentTool/runAgent.ts` | 子 Agent 实现 |
| `source/src/tools/FileReadTool/FileReadTool.ts` | 文件读取 |
| `source/src/tools/BashTool/BashTool.tsx` | Bash 执行 |
| `source/src/tools/GrepTool/GrepTool.ts` | 代码搜索 |
| `source/src/constants/prompts.ts` | 系统提示词 |
| `source/src/skills/loadSkillsDir.ts` | Skill 加载 |
| `source/src/services/mcp/client.ts` | MCP 客户端 |

---

## 十、结论

Claude Code 的价值不仅在于它调用了强大的 LLM，更在于它构建了一套完整的 **Agent 工程体系**：

- 丰富的工具系统
- 精细的权限控制
- 强大的上下文管理
- 稳定的错误恢复
- 优雅的 UI 渲染
- 可扩展的 Skill 和 MCP 机制

对于构建自己的代码分析 Agent，最核心的参考是：

1. **把工具做得又多又稳**
2. **把权限系统做细**
3. **把上下文管理做透**
4. **保持架构可扩展**

不要试图复制所有功能，先实现最小闭环（LLM + 读文件 + 写文件 + Bash + 搜索），然后逐步扩展。

---

*最后更新：2026-06-30*
