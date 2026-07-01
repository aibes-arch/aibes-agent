# minagent API 参考

> **版本**: 0.1.0  
> **最后更新**: 2026-07-01  
> **关联文档**: [架构设计](./ARCHITECTURE.md)、[模块设计](./MODULE_DESIGN.md)

---

## 目录

- [顶层导出](#顶层导出)
- [核心引擎 `minagent.core.engine`](#核心引擎-minagentcoreengine)
- [LLM 客户端 `minagent.core.llm`](#llm-客户端-minagentcorellm)
- [上下文 `minagent.core.context`](#上下文-minagentcorecontext)
- [工具注册表 `minagent.core.tool_registry`](#工具注册表-minagentcoretool_registry)
- [权限 `minagent.permissions.engine`](#权限-minagentpermissionsengine)
- [工具基类 `minagent.tools.base`](#工具基类-minagenttoolsbase)
- [文件工具 `minagent.tools.fs`](#文件工具-minagenttoolsfs)
- [搜索工具 `minagent.tools.search`](#搜索工具-minagenttoolssearch)
- [Shell 工具 `minagent.tools.shell`](#shell-工具-minagenttoolsshell)
- [任务工具 `minagent.tools.task`](#任务工具-minagenttoolstask)
- [CLI `minagent.cli`](#cli-minagentcli)
- [事件类型](#事件类型)

---

## 顶层导出

`minagent/__init__.py` 导出的公开 API：

```python
from minagent import (
    AgentConfig,
    AgentLoop,
    LLMClient,
    ToolRegistry,
    PermissionEngine,
    ToolContext,
    BashTool,
    FileEditTool,
    FileReadTool,
    FileWriteTool,
    GlobTool,
    GrepTool,
    TaskListTool,
)
```

---

## 核心引擎 `minagent.core.engine`

### `AgentConfig`

Agent 配置类。

```python
class AgentConfig:
    def __init__(
        self,
        system_prompt: str = "",
        max_turns: int = 30,
        max_tokens_per_turn: int = 4000,
        temperature: float = 0.2,
        auto_compact: bool = True,
    )
```

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `system_prompt` | `str` | `""` | 系统提示词 |
| `max_turns` | `int` | `30` | 最大对话轮数 |
| `max_tokens_per_turn` | `int` | `4000` | 每轮 LLM 最大 token 数 |
| `temperature` | `float` | `0.2` | LLM 温度 |
| `auto_compact` | `bool` | `True` | 是否自动压缩上下文 |

### `AgentLoop`

Agent 主循环。

```python
class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        config: AgentConfig,
        permission_engine: Optional[PermissionEngine] = None,
        tool_context: Optional[ToolContext] = None,
    )

    async def run(
        self,
        task: str,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| `llm` | `LLMClient` | LLM 客户端 |
| `registry` | `ToolRegistry` | 工具注册表 |
| `config` | `AgentConfig` | Agent 配置 |
| `permission_engine` | `PermissionEngine` | 权限引擎，默认新建一个 |
| `tool_context` | `ToolContext` | 工具执行上下文，默认 `cwd="/"` |

`run()` 返回异步事件流，事件类型见 [事件类型](#事件类型)。

---

## LLM 客户端 `minagent.core.llm`

### `LLMClient`

OpenAI 兼容的异步 LLM 客户端。

```python
class LLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    )
```

配置优先级：**显式参数 > 环境变量 > 默认值**。

| 来源 | 环境变量 | 默认值 |
|-----|---------|--------|
| `base_url` | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `api_key` | `OPENAI_API_KEY` | `""` |
| `model` | `MINAGENT_MODEL` | `gpt-4o-mini` |

属性：

| 属性 | 类型 | 说明 |
|-----|------|------|
| `base_url` | `str` | API 基础地址（已去除末尾 `/`） |
| `api_key` | `str` | API Key |
| `model` | `str` | 默认模型名 |
| `timeout` | `float` | 请求超时（秒） |

### `LLMClient.chat()`

```python
async def chat(
    self,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 4000,
    temperature: float = 0.2,
) -> "LLMResponse"
```

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `messages` | `List[Dict[str, Any]]` | 必填 | OpenAI 格式的消息列表 |
| `tools` | `Optional[List[Dict[str, Any]]]` | `None` | OpenAI function schema 列表 |
| `max_tokens` | `int` | `4000` | 最大生成 token 数 |
| `temperature` | `float` | `0.2` | 温度 |

### `LLMResponse`

```python
class LLMResponse:
    def __init__(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        model: str = "",
        usage: Optional[Dict[str, int]] = None,
    )

    def has_tool_calls(self) -> bool
    def to_message(self) -> Dict[str, Any]

    @staticmethod
    def from_openai(data: Dict[str, Any]) -> "LLMResponse"
```

| 属性 | 类型 | 说明 |
|-----|------|------|
| `content` | `str` | 助手文本内容 |
| `tool_calls` | `List[Dict[str, Any]]` | OpenAI 格式的 tool_calls |
| `model` | `str` | 实际响应模型 |
| `usage` | `Dict[str, int]` | token 使用统计 |

---

## 上下文 `minagent.core.context`

### `Message`

```python
class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_openai(self) -> Dict[str, Any]
```

### `ContextWindow`

```python
class ContextWindow(BaseModel):
    max_tokens: int = Field(default=128000, ge=1000)
    messages: List[Message] = Field(default_factory=list)

    def add(self, message: Message) -> None
    def add_user(self, content: str) -> None
    def add_assistant(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None
    def add_tool_result(self, tool_call_id: str, content: str, name: str) -> None
    def to_openai_messages(self) -> List[Dict[str, Any]]
    def rough_token_count(self) -> int
    def should_compact(self) -> bool
    def compact(self) -> None
```

| 方法 | 说明 |
|-----|------|
| `rough_token_count()` | 按 `len(text) // 4` 粗略估算 token |
| `should_compact()` | 当 token 数超过 `max_tokens * 0.8` 时返回 `True` |
| `compact()` | 保留 system 消息和最近 6 条消息，中间替换为摘要提示 |

---

## 工具注册表 `minagent.core.tool_registry`

### `ToolRegistry`

```python
class ToolRegistry:
    def __init__(self) -> None

    def register(self, tool: Tool) -> "ToolRegistry"
    def register_many(self, tools: List[Tool]) -> "ToolRegistry"
    def get(self, name: str) -> Optional[Tool]
    def has(self, name: str) -> bool
    def list_tools(self) -> List[str]
    def to_openai_schemas(self) -> List[Dict[str, Any]]
    def get_tool(self, name: str) -> Tool

    async def execute(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ToolContext,
    ) -> List[Dict[str, Any]]
```

| 方法 | 说明 |
|-----|------|
| `register()` | 注册单个工具，同名会抛 `ValueError` |
| `register_many()` | 批量注册，支持链式调用 |
| `to_openai_schemas()` | 生成所有工具的 OpenAI function schema |
| `execute()` | 执行 tool_calls，自动按并发/串行策略编排 |

---

## 权限 `minagent.permissions.engine`

### `PermissionRule`

```python
@dataclass
class PermissionRule:
    action: str          # allow / deny / ask
    resource_type: str   # filesystem / shell / tool
    pattern: str
```

### `PermissionEngine`

```python
class PermissionEngine:
    def __init__(
        self,
        rules: Optional[List[PermissionRule]] = None,
        mode: str = "auto",
    )

    @staticmethod
    def default() -> "PermissionEngine"

    async def check(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> bool

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "PermissionEngine"
```

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `rules` | `List[PermissionRule]` | `[]` | 权限规则列表 |
| `mode` | `str` | `"auto"` | `ask` / `auto` / `full_auto` |

| 方法 | 说明 |
|-----|------|
| `default()` | 返回内置默认规则：读工具允许，写/Bash 工具询问 |
| `check()` | 判断指定工具调用是否被允许 |
| `from_config()` | 从字典配置创建权限引擎 |

---

## 工具基类 `minagent.tools.base`

### `ToolContext`

```python
@dataclass
class ToolContext:
    cwd: str
    env: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any
    def set(self, key: str, value: Any) -> None
```

### `ToolResult`

```python
@dataclass
class ToolResult:
    success: bool
    content: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def ok(content: str, **metadata) -> "ToolResult"
    @staticmethod
    def fail(error: str, content: str = "", **metadata) -> "ToolResult"
```

### `Tool`

```python
class Tool(ABC):
    name: str = ""
    description: str = ""
    input_model: Type[BaseModel]
    output_model: Type[BaseModel] = ToolResult

    def __init__(self) -> None
    def to_openai_schema(self) -> Dict[str, Any]
    def is_read_only(self, input: BaseModel) -> bool
    def is_concurrency_safe(self, input: BaseModel) -> bool

    @abstractmethod
    async def call(self, input: BaseModel, context: ToolContext) -> ToolResult
```

子类必须定义 `name`、`description`、`input_model`，并实现 `call()`。

---

## 文件工具 `minagent.tools.fs`

### `FileReadTool`

```python
class FileReadTool(Tool):
    name = "FileRead"
```

输入模型：

```python
class FileReadInput(BaseModel):
    file_path: str
    offset: int = 1
    limit: int = 500
```

行为：

- 读取 `file_path` 的文本内容。
- `offset` 为 1-based 行号。
- 返回 `ToolResult` 的 `metadata` 包含 `total_lines`、`returned_lines` 等。

### `FileWriteTool`

```python
class FileWriteTool(Tool):
    name = "FileWrite"
```

输入模型：

```python
class FileWriteInput(BaseModel):
    file_path: str
    content: str
```

行为：

- 创建或覆盖文件，自动创建父目录。
- 返回 `metadata` 包含 `action`（`created` / `updated`）。

### `FileEditTool`

```python
class FileEditTool(Tool):
    name = "FileEdit"
```

输入模型：

```python
class FileEditInput(BaseModel):
    file_path: str
    old_string: str
    new_string: str
```

行为：

- 精确替换文件中第一次出现的 `old_string`。
- 如果 `old_string` 不存在，返回失败。

---

## 搜索工具 `minagent.tools.search`

### `GrepTool`

```python
class GrepTool(Tool):
    name = "Grep"
```

输入模型：

```python
class GrepInput(BaseModel):
    pattern: str
    path: str = ""
    glob: str = ""
    output_mode: str = "files_with_matches"
    head_limit: int = 250
```

| 字段 | 说明 |
|-----|------|
| `pattern` | ripgrep 正则模式 |
| `path` | 搜索路径，空则使用 `context.cwd` |
| `glob` | 文件过滤 glob |
| `output_mode` | `files_with_matches` / `content` / `count` |
| `head_limit` | 结果上限 |

依赖：系统已安装 `ripgrep (rg)`。

### `GlobTool`

```python
class GlobTool(Tool):
    name = "Glob"
```

输入模型：

```python
class GlobInput(BaseModel):
    pattern: str
    path: str = ""
```

行为：

- 递归遍历 `path`（或 `context.cwd`）。
- 按文件名匹配 `pattern`。
- 跳过隐藏目录和 `__pycache__`。

---

## Shell 工具 `minagent.tools.shell`

### `BashTool`

```python
class BashTool(Tool):
    name = "Bash"
```

输入模型：

```python
class BashInput(BaseModel):
    command: str
    timeout: int = 60
    cwd: str = ""
```

行为：

- 使用 `asyncio.create_subprocess_shell` 执行命令。
- `cwd` 为空时使用 `context.cwd`。
- Windows 下会把 `/c/path` 形式转换为 `C:\path`。
- 只读命令判定：`ls`、`find`、`grep`、`cat`、`head`、`tail`、`wc`、`echo`、`git status`、`git log`、`git diff`。

---

## 任务工具 `minagent.tools.task`

### `TaskListTool`

```python
class TaskListTool(Tool):
    name = "TaskList"
```

输入模型：

```python
class TaskListInput(BaseModel):
    action: str = "list"    # list / add / done
    task: str = ""
    task_id: int = -1
```

行为：

- 在 `ToolContext.metadata["tasks"]` 中维护任务列表。
- `list` 为只读操作，`add/done` 为写入操作。

---

## CLI `minagent.cli`

### `app`

```python
app = typer.Typer(help="minagent — minimal Python agent framework CLI")
```

Typer 应用对象，也是 `pyproject.toml` 中的入口点：

```toml
[project.scripts]
minagent = "minagent.cli:app"
```

### `run()`

```python
@app.command()
def run(
    script: Annotated[str, typer.Argument(help="Path to the agent script to run")],
    args: Annotated[Optional[list[str]], typer.Argument(help="Arguments passed to the script")] = None,
) -> None
```

用法：

```bash
minagent examples/readme_demo.py
```

---

## 事件类型

`AgentLoop.run()` 产生的事件结构：

### `user_task`

```python
{"type": "user_task", "content": str}
```

### `llm_response`

```python
{
    "type": "llm_response",
    "turn": int,
    "content": str,
    "tool_calls": List[Dict[str, Any]],
    "model": str,
    "usage": Dict[str, int],
}
```

### `permission_denied`

```python
{"type": "permission_denied", "tool_call": Dict[str, Any], "reason": str}
```

### `tool_result`

```python
{"type": "tool_result", "tool_call_id": str, "name": str, "content": str}
```

### `compact`

```python
{"type": "compact", "message": str}
```

### `error`

```python
{"type": "error", "message": str}
```

### `final`

```python
{"type": "final", "content": str}
```

---

*下一章：[快速开始 / 示例教程](./QUICK_START.md)*
