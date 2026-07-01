# minagent 模块设计文档

> **版本**: 0.1.0  
> **最后更新**: 2026-07-01  
> **关联文档**: [架构设计](./ARCHITECTURE.md)、[版本演进计划](./ROADMAP.md)

---

## 1. 项目目录结构

```text
minagent/
├── minagent/                 # 主包
│   ├── __init__.py           # 公开 API + 日志配置
│   ├── cli.py                # 命令行入口
│   ├── core/                 # 引擎层
│   │   ├── __init__.py
│   │   ├── context.py        # 上下文 / 消息 / token 估算
│   │   ├── engine.py         # AgentConfig / AgentLoop
│   │   ├── llm.py            # LLMClient / LLMResponse
│   │   └── tool_registry.py  # ToolRegistry
│   ├── permissions/          # 权限层
│   │   ├── __init__.py
│   │   └── engine.py         # PermissionEngine / PermissionRule
│   └── tools/                # 工具层
│       ├── __init__.py       # 工具导出
│       ├── base.py           # Tool / ToolContext / ToolResult
│       ├── fs.py             # 文件工具
│       ├── search.py         # Grep / Glob
│       ├── shell.py          # Bash
│       └── task.py           # TaskList
├── examples/
│   └── readme_demo.py        # 可运行示例
├── tests/
│   └── test_tools.py         # 单元测试
├── docs/                     # 设计文档
├── pyproject.toml
└── README.md
```

---

## 2. `minagent.core` 引擎层

### 2.1 `minagent.core.context`

负责会话上下文管理。

#### `Message`

```python
class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
```

`Message.to_openai()` 将消息转换为 OpenAI API 格式。

#### `ContextWindow`

```python
class ContextWindow(BaseModel):
    max_tokens: int = Field(default=128000, ge=1000)
    messages: List[Message] = Field(default_factory=list)
```

核心方法：

| 方法 | 说明 |
|-----|------|
| `add(message)` | 添加消息 |
| `add_user(content)` | 添加用户消息 |
| `add_assistant(content, tool_calls)` | 添加助手消息 |
| `add_tool_result(id, content, name)` | 添加工具结果 |
| `to_openai_messages()` | 导出为 OpenAI 格式 |
| `rough_token_count()` | 按 `len(text) // 4` 粗略估算 |
| `should_compact()` | 判断是否需要压缩 |
| `compact()` | 保留 system + 最近 6 条消息 |

---

### 2.2 `minagent.core.llm`

#### `LLMClient`

```python
class LLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("MINAGENT_MODEL", "gpt-4o-mini")
        self.timeout = timeout
```

配置优先级：**显式参数 > 环境变量 > 默认值**。

#### `LLMClient.chat()`

```python
async def chat(
    self,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 4000,
    temperature: float = 0.2,
) -> "LLMResponse":
```

- 构造 OpenAI 兼容的 `chat.completions` 请求。
- 如果传入 `tools`，自动加上 `tool_choice: "auto"`。
- 使用 `httpx.AsyncClient` 异步请求。
- 通过 `response.raise_for_status()` 抛出 HTTP 异常。

#### `LLMResponse`

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

---

### 2.3 `minagent.core.engine`

#### `AgentConfig`

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

#### `AgentLoop`

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

`run()` 产生的事件见 [架构设计文档的“可观测性”章节](./ARCHITECTURE.md#8-可观测性)。

---

### 2.4 `minagent.core.tool_registry`

#### `ToolRegistry`

```python
class ToolRegistry:
    def __init__(self) -> None
    def register(self, tool: Tool) -> "ToolRegistry"
    def register_many(self, tools: List[Tool]) -> "ToolRegistry"
    def get(self, name: str) -> Optional[Tool]
    def has(self, name: str) -> bool
    def list_tools(self) -> List[str]
    def to_openai_schemas(self) -> List[Dict[str, Any]]
    async def execute(self, tool_calls, context) -> List[Dict[str, Any]]
```

#### 并发/串行分区

```python
def _partition_tool_calls(self, tool_calls):
    batches = []
    for tc in tool_calls:
        tool = self.get_tool(tc["function"]["name"])
        parsed = tool.input_model.model_validate(tc["function"].get("arguments", {}))
        is_concurrent = tool.is_concurrency_safe(parsed)
        # 相同性质的调用合并为同一批次
```

执行策略：

- 并发批次内使用 `asyncio.gather(..., return_exceptions=True)`。
- 串行批次逐个 `await`。
- 每个 tool_call 单独捕获异常，避免一个工具失败导致整批失败。

---

## 3. `minagent.tools` 工具层

### 3.1 `minagent.tools.base`

#### `ToolContext`

```python
@dataclass
class ToolContext:
    cwd: str
    env: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any
    def set(self, key: str, value: Any) -> None
```

`metadata` 用于在多个工具调用间共享状态，例如 `TaskListTool` 的任务列表。

#### `ToolResult`

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

#### `Tool` 抽象基类

```python
class Tool(ABC):
    name: str = ""
    description: str = ""
    input_model: Type[BaseModel]
    output_model: Type[BaseModel] = ToolResult

    def to_openai_schema(self) -> Dict[str, Any]
    def is_read_only(self, input: BaseModel) -> bool
    def is_concurrency_safe(self, input: BaseModel) -> bool

    @abstractmethod
    async def call(self, input: BaseModel, context: ToolContext) -> ToolResult
```

子类必须定义 `name`、`description`、`input_model`，并实现 `call()`。

---

### 3.2 `minagent.tools.fs` 文件工具

| 工具 | 输入模型 | 说明 |
|-----|---------|------|
| `FileRead` | `file_path`, `offset`(1-based), `limit` | 读取文本文件，支持分页 |
| `FileWrite` | `file_path`, `content` | 创建或覆盖文件 |
| `FileEdit` | `file_path`, `old_string`, `new_string` | 精确替换文件内容 |

注意：所有路径都会通过 `Path(...).expanduser().resolve()` 解析为绝对路径。

---

### 3.3 `minagent.tools.search` 搜索工具

#### `GrepTool`

封装 `ripgrep (rg)`，要求系统已安装 `rg`。

输入：

```python
class GrepInput(BaseModel):
    pattern: str
    path: str = ""
    glob: str = ""
    output_mode: str = "files_with_matches"  # files_with_matches / content / count
    head_limit: int = 250
```

#### `GlobTool`

递归遍历目录，按 glob 模式匹配文件名。

```python
class GlobInput(BaseModel):
    pattern: str
    path: str = ""   # 空则使用 context.cwd
```

实现细节：

- 跳过隐藏目录和 `__pycache__`。
- Windows 下会把 `/c/path` 形式转换为 `C:/path`。

---

### 3.4 `minagent.tools.shell`

#### `BashTool`

```python
class BashInput(BaseModel):
    command: str
    timeout: int = 60
    cwd: str = ""   # 空则使用 context.cwd
```

只读判断：

```python
def is_read_only(self, input: BashInput) -> bool:
    read_only_prefixes = (
        "ls", "find", "grep", "cat", "head", "tail",
        "wc", "echo", "git status", "git log", "git diff",
    )
    return input.command.strip().startswith(read_only_prefixes)
```

Windows 兼容：

- 如果 `cwd` 以 `/c/` 开头，会转换为 `C:\` 形式。
- 命令通过 `asyncio.create_subprocess_shell` 执行。

---

### 3.5 `minagent.tools.task`

#### `TaskListTool`

在 `ToolContext.metadata["tasks"]` 中维护简单任务列表。

```python
class TaskListInput(BaseModel):
    action: str = "list"      # list / add / done
    task: str = ""            # add 时使用
    task_id: int = -1         # done 时使用
```

`is_read_only()` 对 `list` 操作返回 `True`，`add/done` 返回 `False`。

---

## 4. `minagent.permissions` 权限层

### 4.1 `PermissionRule`

```python
@dataclass
class PermissionRule:
    action: str          # allow / deny / ask
    resource_type: str   # filesystem / shell / tool
    pattern: str
```

### 4.2 `PermissionEngine`

```python
class PermissionEngine:
    def __init__(self, rules=None, mode="auto")

    @staticmethod
    def default() -> "PermissionEngine"
    async def check(tool_name, arguments, context) -> bool
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "PermissionEngine"
```

#### 匹配顺序

1. `full_auto`：直接返回 `True`。
2. `ask`：当前演示版本直接返回 `True`（生产环境应弹窗）。
3. `auto`：
   - 先匹配 `tool` 规则。
   - 再匹配 `filesystem` 规则（参数中的 `file_path` / `path`）。
   - 再匹配 `shell` 规则（参数中的 `command`）。
   - 无匹配则默认允许。

---

## 5. `minagent.cli` 命令行入口

### 5.1 入口点

`pyproject.toml`：

```toml
[project.scripts]
minagent = "minagent.cli:app"
```

### 5.2 使用方式

```bash
minagent examples/readme_demo.py
```

CLI 会：

1. 检查脚本文件是否存在。
2. 把脚本以 `__name__ == "__main__"` 的方式执行。
3. 让脚本“看到”自己的命令行参数（`sys.argv`）。

### 5.3 实现

```python
app = typer.Typer(help="minagent — minimal Python agent framework CLI")

@app.command()
def run(script: str, args: Optional[List[str]] = None) -> None:
    _run_script(Path(script), args or [])
```

当只有一个命令时，Typer 允许省略子命令名，因此 `minagent examples/readme_demo.py` 等价于 `minagent run examples/readme_demo.py`。

---

## 6. 事件类型与消费

`AgentLoop.run()` 产生的事件结构：

```python
{"type": "user_task", "content": str}
{"type": "llm_response", "turn": int, "content": str, "tool_calls": list, "model": str, "usage": dict}
{"type": "permission_denied", "tool_call": dict, "reason": str}
{"type": "tool_result", "tool_call_id": str, "name": str, "content": str}
{"type": "compact", "message": str}
{"type": "error", "message": str}
{"type": "final", "content": str}
```

示例消费代码（来自 `examples/readme_demo.py`）：

```python
async for event in agent.run(task):
    if event["type"] == "llm_response":
        print(f"\n[LLM Turn {event['turn']}]\n{event['content']}")
        if event["tool_calls"]:
            print(f"Tool calls: {[tc['function']['name'] for tc in event['tool_calls']]}")
    elif event["type"] == "tool_result":
        print(f"\n[Tool: {event['name']}]\n{event['content'][:500]}")
    elif event["type"] == "final":
        print(f"\n[Final]\n{event['content']}")
    elif event["type"] == "error":
        print(f"\n[Error] {event['message']}")
```

---

## 7. 配置与环境变量

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `OPENAI_BASE_URL` | OpenAI 兼容 API 基础地址 | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | API Key | `""` |
| `MINAGENT_MODEL` | 默认模型 | `gpt-4o-mini` |
| `MINAGENT_LOG_LEVEL` | 日志级别 | `INFO` |

也可以在代码中显式配置：

```python
llm = LLMClient(
    base_url="http://192.168.2.179:1234/v1",
    api_key="dummy",
    model="qwen/qwen3.6-35b-a3b",
    timeout=120.0,
)
```

---

## 8. 开发指南

### 8.1 如何添加一个新工具

1. 在 `minagent/tools/` 下创建新文件或在现有文件中新增类。
2. 继承 `Tool`，定义 `name`、`description`、`input_model`。
3. 实现 `call()`。
4. 根据需要重写 `is_read_only()` 以影响并发策略。
5. 在 `minagent/tools/__init__.py` 中导出。
6. 在 `minagent/__init__.py` 中导出（可选，供用户直接导入）。

示例：

```python
from pydantic import BaseModel, Field
from minagent.tools.base import Tool, ToolContext, ToolResult

class HttpGetInput(BaseModel):
    url: str = Field(..., description="URL to fetch")

class HttpGetTool(Tool):
    name = "HttpGet"
    description = "Fetch a URL via HTTP GET."
    input_model = HttpGetInput

    def is_read_only(self, input: HttpGetInput) -> bool:
        return True

    async def call(self, input: HttpGetInput, context: ToolContext) -> ToolResult:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(input.url)
                r.raise_for_status()
                return ToolResult.ok(r.text[:2000])
        except Exception as e:
            return ToolResult.fail(str(e))
```

### 8.2 如何自定义权限规则

```python
from minagent.permissions.engine import PermissionEngine, PermissionRule

perm = PermissionEngine(
    rules=[
        PermissionRule("allow", "tool", "FileRead"),
        PermissionRule("deny", "shell", "rm -rf .*"),
        PermissionRule("allow", "filesystem", "/safe/path/**"),
    ],
    mode="auto",
)
```

---

## 9. 测试

测试位于 `tests/test_tools.py`，覆盖：

- 文件读写与编辑
- Bash 只读命令
- Glob 文件枚举
- TaskList 增删改查
- ToolRegistry 注册与 schema 生成

运行：

```bash
pytest tests/ -q
```

---

*下一章：[版本演进计划](./ROADMAP.md)*
