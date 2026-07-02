# aibes-agent 快速开�?
> **版本**: 0.4.0  
> **最后更�?*: 2026-07-02  
> **前置要求**: Python 3.11+

---

## 目录

- [1. 安装](#1-安装)
- [2. 配置 LLM](#2-配置-llm)
- [3. 运行第一个示例](#3-运行第一个示�?
- [4. 编写自己�?Agent 脚本](#4-编写自己�?agent-脚本)
- [5. 添加自定义工具](#5-添加自定义工�?
- [6. 调整权限](#6-调整权限)
- [7. 常见问题](#7-常见问题)

---

## 1. 安装

### 1.1 从源码安�?
```bash
cd aibes-agent
pip install -e .
```

### 1.2 安装 CLI 依赖

如果你需要使�?`aibes-agent` 命令行入口，建议安装可选依赖：

```bash
pip install -e ".[cli]"
```

这会安装 `typer` �?`rich`�?
### 1.3 安装开发依�?
```bash
pip install -e ".[dev]"
```

---

## 2. 配置 LLM

`aibes-agent` 通过 OpenAI 兼容 API 调用 LLM。你可以使用�?
- OpenAI 官方 API
- 阿里云百�?/ 硅基流动等第三方代理
- 本地模型（LM Studio、Ollama、vLLM 等）

### 2.1 环境变量配置

**PowerShell (Windows)**

```powershell
$env:OPENAI_BASE_URL="http://192.168.2.179:1234/v1"
$env:OPENAI_API_KEY="dummy"
$env:AIBES_AGENT_MODEL="qwen/qwen3.6-35b-a3b"
```

**Bash (Linux/macOS)**

```bash
export OPENAI_BASE_URL="http://192.168.2.179:1234/v1"
export OPENAI_API_KEY="dummy"
export AIBES_AGENT_MODEL="qwen/qwen3.6-35b-a3b"
```

### 2.2 代码中显式配�?
```python
from aibes-agent import LLMClient

llm = LLMClient(
    base_url="http://192.168.2.179:1234/v1",
    api_key="dummy",
    model="qwen/qwen3.6-35b-a3b",
    timeout=120.0,
)
```

---

## 3. 运行第一个示�?
项目已提供一个可运行示例 `examples/readme_demo.py`�?
### 3.1 使用 CLI

```bash
aibes-agent run examples/readme_demo.py
```

### 3.2 使用 Python

```bash
python examples/readme_demo.py
```

### 3.3 预期输出

```text
Task: 请查�?aibes-agent 项目结构，列出所�?Python 文件，并给出这个项目的简要说明�?
============================================================
2026-07-01 09:54:30.551 | INFO     | aibes_agent.core.engine:run:69 - Turn 1/15: calling LLM ...
...

[LLM Turn 1]
我来帮你查看 aibes-agent 项目的结构和 Python 文件�?Tool calls: ['Glob', 'Glob']

[Tool: Glob]
E:\aibes-agent\examples\readme_demo.py
E:\aibes-agent\aibes-agent\cli.py
...

[Final]
## aibes-agent 项目结构
...
```

如果中文显示乱码，先执行�?
```powershell
chcp 65001
```

---

## 4. 编写自己�?Agent 脚本

创建一个文�?`my_agent.py`�?
```python
import asyncio
import os

from aibes-agent import (
    AgentConfig,
    AgentLoop,
    BashTool,
    FileReadTool,
    GlobTool,
    LLMClient,
    PermissionEngine,
    ToolContext,
    ToolRegistry,
)


async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "gpt-4o-mini"),
    )

    registry = ToolRegistry()
    registry.register_many([
        FileReadTool(),
        BashTool(),
        GlobTool(),
    ])

    config = AgentConfig(
        system_prompt="你是一个代码分析助手。请使用工具收集信息，然后给出结论�?,
        max_turns=10,
    )

    perm = PermissionEngine.default()
    tool_context = ToolContext(cwd=os.getcwd())

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=tool_context,
    )

    task = "列出当前目录下所�?Python 文件，并读取 aibes-agent/__init__.py 的内容�?
    async for event in agent.run(task):
        if event["type"] == "llm_response":
            print(f"\n[Turn {event['turn']}] {event['content']}")
            if event["tool_calls"]:
                print("Tools:", [tc["function"]["name"] for tc in event["tool_calls"]])
        elif event["type"] == "tool_result":
            print(f"\n[{event['name']}]\n{event['content'][:300]}")
        elif event["type"] == "final":
            print(f"\n[Final]\n{event['content']}")


if __name__ == "__main__":
    asyncio.run(main())
```

运行�?
```bash
aibes-agent my_agent.py
```

---

## 5. 添加自定义工�?
下面写一个能获取当前时间的小工具�?
### 5.1 定义工具

```python
from datetime import datetime
from pydantic import BaseModel, Field
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class NowInput(BaseModel):
    fmt: str = Field("%Y-%m-%d %H:%M:%S", description="datetime format")


class NowTool(Tool):
    name = "Now"
    description = "Get the current datetime."
    input_model = NowInput

    def is_read_only(self, input: NowInput) -> bool:
        return True

    async def call(self, input: NowInput, context: ToolContext) -> ToolResult:
        now = datetime.now().strftime(input.fmt)
        return ToolResult.ok(f"Current datetime: {now}")
```

### 5.2 注册并使�?
```python
from aibes-agent import ToolRegistry

registry = ToolRegistry()
registry.register(NowTool())
```

LLM 现在可以在需要的时候调�?`Now` 工具了�?
---

## 6. 调整权限

默认权限规则�?
- `FileRead`、`Grep`、`Glob` 自动允许
- `FileWrite`、`FileEdit`、`Bash`、`TaskList` 需要询问（演示版自动通过�?
### 6.1 使用默认权限

```python
from aibes-agent import PermissionEngine

perm = PermissionEngine.default()
```

### 6.2 自定义规�?
```python
from aibes_agent.permissions.engine import PermissionEngine, PermissionRule

perm = PermissionEngine(
    rules=[
        PermissionRule("allow", "tool", "FileRead"),
        PermissionRule("allow", "tool", "Glob"),
        PermissionRule("deny", "shell", "rm -rf .*"),
        PermissionRule("allow", "filesystem", "E:/aibes/aibes-agent/**"),
        PermissionRule("deny", "filesystem", "E:/aibes/aibes-vault/**"),
    ],
    mode="auto",
)
```

### 6.3 配置文件中加�?
```yaml
# aibes-agent.yaml
permissions:
  mode: auto
  rules:
    - action: allow
      resource_type: tool
      pattern: FileRead
    - action: deny
      resource_type: shell
      pattern: "rm -rf .*"
```

```python
import yaml
from aibes_agent.permissions.engine import PermissionEngine

with open("aibes-agent.yaml") as f:
    config = yaml.safe_load(f)

perm = PermissionEngine.from_config(config["permissions"])
```

---

## 7. 常见问题

### Q1: 运行示例后卡�?“calling LLM�?没反应？

大概率是 LLM 服务没有响应或响应较慢。检查：

- `OPENAI_BASE_URL` 是否可访�?- 模型是否已加载完�?- 本地模型首次推理可能需要几十秒

### Q2: 工具返回空结果？

检�?`ToolContext(cwd=...)` 是否指向正确目录。示例中已改�?`os.getcwd()`，避免写�?Unix 路径�?
### Q3: 如何关闭 INFO 日志�?
```powershell
$env:AIBES_AGENT_LOG_LEVEL="WARNING"
```

### Q4: `aibes-agent` 命令找不到？

重新安装 editable 包：

```bash
pip install -e .
```

---

*下一章：[工具开发实战指南](./TOOL_DEVELOPMENT.md)*


---

## 8. v0.2.0 新特性速览

### 8.1 使用子 Agent（AgentTool）

```python
from aibes-agent import AgentProfile, AgentTool

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
registry.register(agent_tool)
```

然后给 Agent 下达任务：

```text
"让 researcher 子 Agent 探索项目结构，然后告诉我主要模块。"
```

### 8.2 查看运行统计

`final` 事件现在包含 `stats`：

```python
elif event["type"] == "final":
    print(event["content"])
    stats = event["stats"]
    print(f"轮数: {stats['turn_count']}, "
          f"LLM 调用: {stats['llm_call_count']}, "
          f"工具调用: {stats['tool_call_count']}, "
          f"Token: {stats['total_tokens']}")
```

### 8.3 权限 ask 模式

程序化默认自动通过：

```python
perm = PermissionEngine.default()
```

命令行交互式确认：

```python
from aibes_agent.permissions.engine import PermissionEngine, cli_ask_callback

perm = PermissionEngine.default(on_ask=cli_ask_callback)
```

CLI 一键通过所有权限询问：

```bash
aibes-agent -y examples/readme_demo.py
```

### 8.4 工具结果缓存

缓存自动启用，无需额外配置。如需禁用，传入无缓存的 `ToolContext`：

```python
from aibes_agent.core.cache import ToolResultCache

tool_context = ToolContext(cwd=os.getcwd(), cache=ToolResultCache(default_ttl=0))
```

---

*最后更新：2026-07-02*


---

## 9. v0.3.0 新特性速览

### 9.1 使用配置文件

创建 `aibes-agent.yaml`：

```yaml
llm:
  base_url: "http://192.168.2.179:1234/v1"
  model: "qwen/qwen3.6-35b-a3b"

skills:
  auto_load: true
  paths:
    - ".aibes-agent/skills"

session:
  store: file
  path: ".aibes-agent/sessions"
```

然后在脚本中加载：

```python
from aibes_agent.config import MinagentConfig

cfg = MinagentConfig.load()
llm = cfg.to_llm_client()
```

### 9.2 加载 Skill

```python
from aibes_agent.skills import SkillBuilder, SkillLoader
from aibes_agent.tools import FileReadTool, GrepTool

tool_pool = {"FileRead": FileReadTool(), "Grep": GrepTool()}
skills = SkillLoader().load_all()
agent_config, registry, profiles = SkillBuilder(skills, tool_pool).build()
```

### 9.3 接入 MCP 服务器

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
    mcp_tools = await client.get_tools()
    registry.register_many(list(mcp_tools.values()))
```

### 9.4 启动 Web UI

```bash
aibes-agent web --config aibes-agent.yaml --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000` 即可交互。

### 9.5 会话持久化

```python
from aibes_agent.core.session import FileSessionStore
from aibes-agent import AgentLoop

store = FileSessionStore(".aibes-agent/sessions")
agent = AgentLoop(..., session_store=store)

async for event in agent.run("My task", session_id="sess-1"):
    ...
```

---

*最后更新：2026-07-02*
