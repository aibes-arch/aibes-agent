# aibes-agent 模块设计文档

> **版本**: 0.3.0  
> **最后更新**: 2026-07-01  
> **关联文档**: [架构设计](./ARCHITECTURE.md)、[版本演进计划](./ROADMAP.md)

---

## 1. 项目目录结构

```text
aibes-agent/
├── aibes-agent/                 # 主包
�?  ├── __init__.py           # 公开 API + 日志配置
�?  ├── cli.py                # 命令行入�?�?  ├── core/                 # 引擎�?�?  �?  ├── __init__.py
�?  �?  ├── context.py        # 上下�?/ 消息 / token 估算
�?  �?  ├── engine.py         # AgentConfig / AgentLoop
�?  �?  ├── llm.py            # LLMClient / LLMResponse
�?  �?  └── tool_registry.py  # ToolRegistry
�?  ├── permissions/          # 权限�?�?  �?  ├── __init__.py
�?  �?  └── engine.py         # PermissionEngine / PermissionRule
�?  └── tools/                # 工具�?�?      ├── __init__.py       # 工具导出
�?      ├── base.py           # Tool / ToolContext / ToolResult
�?      ├── fs.py             # 文件工具
�?      ├── search.py         # Grep / Glob
�?      ├── shell.py          # Bash
�?      └── task.py           # TaskList
├── examples/
�?  └── readme_demo.py        # 可运行示�?├── tests/
�?  └── test_tools.py         # 单元测试
├── docs/                     # 设计文档
├── pyproject.toml
└── README.md
```

---

## 2. `aibes_agent.core` 引擎�?
### 2.1 `aibes_agent.core.context`

负责会话上下文管理�?
#### `Message`

```python
class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
```

`Message.to_openai()` 将消息转换为 OpenAI API 格式�?
#### `ContextWindow`

```python
class ContextWindow(BaseModel):
    max_tokens: int = Field(default=128000, ge=1000)
    messages: List[Message] = Field(default_factory=list)
```

核心方法�?
| 方法 | 说明 |
|-----|------|
| `add(message)` | 添加消息 |
| `add_user(content)` | 添加用户消息 |
| `add_assistant(content, tool_calls)` | 添加助手消息 |
| `add_tool_result(id, content, name)` | 添加工具结果 |
| `to_openai_messages()` | 导出�?OpenAI 格式 |
| `rough_token_count()` | �?`len(text) // 4` 粗略估算 |
| `should_compact()` | 判断是否需要压�?|
| `compact()` | 保留 system + 最�?6 条消�?|

---

### 2.2 `aibes_agent.core.llm`

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
        self.model = model or os.getenv("AIBES_AGENT_MODEL", "gpt-4o-mini")
        self.timeout = timeout
```

配置优先级：**显式参数 > 环境变量 > 默认�?*�?
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

- 构�?OpenAI 兼容�?`chat.completions` 请求�?- 如果传入 `tools`，自动加�?`tool_choice: "auto"`�?- 使用 `httpx.AsyncClient` 异步请求�?- 通过 `response.raise_for_status()` 抛出 HTTP 异常�?
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

### 2.3 `aibes_agent.core.engine`

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

`run()` 产生的事件见 [架构设计文档的“可观测性”章节](./ARCHITECTURE.md#8-可观测�?�?
---

### 2.4 `aibes_agent.core.tool_registry`

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

执行策略�?
- 并发批次内使�?`asyncio.gather(..., return_exceptions=True)`�?- 串行批次逐个 `await`�?- 每个 tool_call 单独捕获异常，避免一个工具失败导致整批失败�?
---

## 3. `aibes_agent.tools` 工具�?
### 3.1 `aibes_agent.tools.base`

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

`metadata` 用于在多个工具调用间共享状态，例如 `TaskListTool` 的任务列表�?
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

子类必须定义 `name`、`description`、`input_model`，并实现 `call()`�?
---

### 3.2 `aibes_agent.tools.fs` 文件工具

| 工具 | 输入模型 | 说明 |
|-----|---------|------|
| `FileRead` | `file_path`, `offset`(1-based), `limit` | 读取文本文件，支持分�?|
| `FileWrite` | `file_path`, `content` | 创建或覆盖文�?|
| `FileEdit` | `file_path`, `old_string`, `new_string` | 精确替换文件内容 |

注意：所有路径都会通过 `Path(...).expanduser().resolve()` 解析为绝对路径�?
---

### 3.3 `aibes_agent.tools.search` 搜索工具

#### `GrepTool`

封装 `ripgrep (rg)`，要求系统已安装 `rg`�?
输入�?
```python
class GrepInput(BaseModel):
    pattern: str
    path: str = ""
    glob: str = ""
    output_mode: str = "files_with_matches"  # files_with_matches / content / count
    head_limit: int = 250
```

#### `GlobTool`

递归遍历目录，按 glob 模式匹配文件名�?
```python
class GlobInput(BaseModel):
    pattern: str
    path: str = ""   # 空则使用 context.cwd
```

实现细节�?
- 跳过隐藏目录�?`__pycache__`�?- Windows 下会�?`/c/path` 形式转换�?`C:/path`�?
---

### 3.4 `aibes_agent.tools.shell`

#### `BashTool`

```python
class BashInput(BaseModel):
    command: str
    timeout: int = 60
    cwd: str = ""   # 空则使用 context.cwd
```

只读判断�?
```python
def is_read_only(self, input: BashInput) -> bool:
    read_only_prefixes = (
        "ls", "find", "grep", "cat", "head", "tail",
        "wc", "echo", "git status", "git log", "git diff",
    )
    return input.command.strip().startswith(read_only_prefixes)
```

Windows 兼容�?
- 如果 `cwd` �?`/c/` 开头，会转换为 `C:\` 形式�?- 命令通过 `asyncio.create_subprocess_shell` 执行�?
---

### 3.5 `aibes_agent.tools.task`

#### `TaskListTool`

�?`ToolContext.metadata["tasks"]` 中维护简单任务列表�?
```python
class TaskListInput(BaseModel):
    action: str = "list"      # list / add / done
    task: str = ""            # add 时使�?    task_id: int = -1         # done 时使�?```

`is_read_only()` �?`list` 操作返回 `True`，`add/done` 返回 `False`�?
---

## 4. `aibes_agent.permissions` 权限�?
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

1. `full_auto`：直接返�?`True`�?2. `ask`：当前演示版本直接返�?`True`（生产环境应弹窗）�?3. `auto`�?   - 先匹�?`tool` 规则�?   - 再匹�?`filesystem` 规则（参数中�?`file_path` / `path`）�?   - 再匹�?`shell` 规则（参数中�?`command`）�?   - 无匹配则默认允许�?
---

## 5. `aibes_agent.cli` 命令行入�?
### 5.1 入口�?
`pyproject.toml`�?
```toml
[project.scripts]
aibes-agent = "aibes_agent.cli:app"
```

### 5.2 使用方式

```bash
aibes-agent run examples/readme_demo.py
```

CLI 会：

1. 检查脚本文件是否存在�?2. 把脚本以 `__name__ == "__main__"` 的方式执行�?3. 让脚本“看到”自己的命令行参数（`sys.argv`）�?
### 5.3 实现

```python
app = typer.Typer(help="aibes-agent �?minimal Python agent framework CLI")

@app.command()
def run(script: str, args: Optional[List[str]] = None) -> None:
    _run_script(Path(script), args or [])
```

执行示例脚本：
---

## 6. 事件类型与消�?
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

示例消费代码（来�?`examples/readme_demo.py`）：

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

## 7. 配置与环境变�?
| 环境变量 | 说明 | 默认�?|
|---------|------|--------|
| `OPENAI_BASE_URL` | OpenAI 兼容 API 基础地址 | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | API Key | `""` |
| `AIBES_AGENT_MODEL` | 默认模型 | `gpt-4o-mini` |
| `AIBES_AGENT_LOG_LEVEL` | 日志级别 | `INFO` |

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

## 8. 开发指�?
### 8.1 如何添加一个新工具

1. �?`aibes-agent/tools/` 下创建新文件或在现有文件中新增类�?2. 继承 `Tool`，定�?`name`、`description`、`input_model`�?3. 实现 `call()`�?4. 根据需要重�?`is_read_only()` 以影响并发策略�?5. �?`aibes-agent/tools/__init__.py` 中导出�?6. �?`aibes-agent/__init__.py` 中导出（可选，供用户直接导入）�?
示例�?
```python
from pydantic import BaseModel, Field
from aibes_agent.tools.base import Tool, ToolContext, ToolResult

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

### 8.2 如何自定义权限规�?
```python
from aibes_agent.permissions.engine import PermissionEngine, PermissionRule

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

- 文件读写与编�?- Bash 只读命令
- Glob 文件枚举
- TaskList 增删改查
- ToolRegistry 注册�?schema 生成

运行�?
```bash
pytest tests/ -q
```

---

*下一章：[版本演进计划](./ROADMAP.md)*


---

## 10. v0.2.0 新增模块

### 10.1 `aibes_agent.core.retry`

```python
from aibes_agent.core.retry import async_retry

async def async_retry(
    coro_fn: Callable[[], Awaitable[T]],
    max_retries: int = 2,
    delay: float = 1.0,
    backoff: float = 2.0,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
) -> T
```

用于对异步操作进行指数退避重试。`LLMClient.chat()` 和 `ToolRegistry` 的只读工具调用都使用了它。

### 10.2 `aibes_agent.core.cache`

```python
from aibes_agent.core.cache import ToolResultCache

cache = ToolResultCache(default_ttl=60.0)
```

| 方法 | 说明 |
|-----|------|
| `make_key(tool_name, args, cwd)` | 生成缓存键 |
| `get(key)` | 获取未过期的结果 |
| `set(key, result, ttl)` | 写入结果 |
| `clear()` | 清空缓存 |

`AgentLoop` 会自动为 `tool_context` 创建一个默认缓存。只读工具（`FileRead`、`Grep`、`Glob` 等）的结果会被缓存。

### 10.3 `aibes_agent.core.stats`

```python
from aibes_agent.core.stats import RunStats
```

记录一次 Agent 运行的指标：

- `turn_count`
- `llm_call_count`
- `tool_call_count`
- `total_prompt_tokens`
- `total_completion_tokens`
- `total_tokens`
- `errors`

`AgentLoop` 每轮产生 `stats` 事件，并在 `final` / `error` 事件中附带最终统计。

### 10.4 `aibes_agent.tools.agent`

```python
from aibes_agent.tools.agent import AgentProfile, AgentTool

agent_tool = AgentTool(
    profiles={
        "researcher": AgentProfile(
            name="researcher",
            system_prompt="You are a code exploration specialist.",
            tools=["Glob", "Grep", "FileRead"],
            max_turns=5,
        )
    },
    llm=llm,
    tool_pool={"Glob": glob_tool, "Grep": grep_tool, "FileRead": read_tool},
)
```

`AgentTool` 允许父 Agent 把子任务委派给具有独立 prompt 和工具集的子 Agent。子 Agent 内部独立运行 `AgentLoop`，只把最终结果返回给父 Agent。

### 10.5 增强版 `TaskListTool`

v0.2.0 的 `TaskListTool` 支持：

- 子任务：`add_subtask` + `parent_id`
- 依赖：`dependencies`
- 进度：`set_progress`（0-100）
- 状态：`pending` / `in_progress` / `done` / `failed`

### 10.6 权限 ask 真实交互

```python
from aibes_agent.permissions.engine import PermissionEngine, cli_ask_callback

perm = PermissionEngine.default(interactive=True)
# 或在自定义引擎中传入 on_ask
perm = PermissionEngine(rules=..., on_ask=cli_ask_callback)
```

CLI 也支持 `--yes-to-all` / `-y` 自动通过所有 ask。

### 10.7 `ContextWindow.compact()` 增强

```python
await ctx.compact(llm)
```

如果传入 `llm`，会用 LLM 生成被压缩历史消息的摘要；失败时回退到旧行为。

---

*最后更新：2026-07-01*


---

## 11. v0.3.0 新增模块

### 11.1 `aibes_agent.config`

`MinagentConfig` 是顶层配置容器，支持从 YAML 加载：

```python
from aibes_agent.config import MinagentConfig

cfg = MinagentConfig.load("aibes-agent.yaml")
llm = cfg.to_llm_client()
perm = cfg.to_permission_engine()
store = cfg.to_session_store()
```

配置搜索顺序：显式路径 → `AIBES_AGENT_CONFIG` 环境变量 → `./aibes-agent.yaml` → `./.aibes-agent/config.yaml`。

### 11.2 `aibes_agent.skills`

| 文件 | 职责 |
|------|------|
| `skill.py` | `Skill` / `SkillProfile` 数据类 |
| `loader.py` | `SkillLoader`：从 `.aibes-agent/skills/<name>/skill.yaml` 加载 |
| `builder.py` | `SkillBuilder`：合并 system prompt、构建 ToolRegistry 与 AgentProfile |

Skill YAML 示例：

```yaml
name: code-review
system_prompt: You are a strict code reviewer.
tools:
  - FileRead
  - Grep
profiles:
  security:
    system_prompt: Focus on security.
    tools:
      - FileRead
    max_turns: 5
```

### 11.3 `aibes_agent.mcp`

| 文件 | 职责 |
|------|------|
| `client.py` | `MCPClient`：管理多 server 连接、tool discovery |
| `tool.py` | `MCPTool`：把 MCP tool 包装为 aibes-agent `Tool` |

使用示例：

```python
from aibes_agent.config import MCPServerConfig
from aibes_agent.mcp.client import MCPClient

async with MCPClient({
    "filesystem": MCPServerConfig(
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "."],
    )
}) as client:
    tools = await client.get_tools()
    registry.register_many(list(tools.values()))
```

### 11.4 `aibes_agent.core.session`

`FileSessionStore` 保存 `SessionState`（messages + tasks）到 JSON：

```python
from aibes_agent.core.session import FileSessionStore, SessionState

store = FileSessionStore(".aibes-agent/sessions")
await store.save(SessionState(session_id="s1", messages=[...]))
state = await store.load("s1")
```

### 11.5 `aibes_agent.core.router`

```python
from aibes_agent.core.router import ModelRouter

router = ModelRouter(default="base", rules=[(re.compile("^write.*"), "coder")])
model = router.route("write a function")  # "coder"
```

### 11.6 `aibes_agent.web`

| 文件 | 职责 |
|------|------|
| `server.py` | FastAPI 应用、路由、HTML 页面、lifespan |
| `runner.py` | `WebRunner`：会话管理、SSE 事件广播、AgentLoop 执行 |

启动方式：

```bash
aibes-agent web --config aibes-agent.yaml --host 127.0.0.1 --port 8000
```

---

*最后更新：2026-07-01*
