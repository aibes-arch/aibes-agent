# minagent 快速开始

> **版本**: 0.1.0  
> **最后更新**: 2026-07-01  
> **前置要求**: Python 3.11+

---

## 目录

- [1. 安装](#1-安装)
- [2. 配置 LLM](#2-配置-llm)
- [3. 运行第一个示例](#3-运行第一个示例)
- [4. 编写自己的 Agent 脚本](#4-编写自己的-agent-脚本)
- [5. 添加自定义工具](#5-添加自定义工具)
- [6. 调整权限](#6-调整权限)
- [7. 常见问题](#7-常见问题)

---

## 1. 安装

### 1.1 从源码安装

```bash
cd minagent
pip install -e .
```

### 1.2 安装 CLI 依赖

如果你需要使用 `minagent` 命令行入口，建议安装可选依赖：

```bash
pip install -e ".[cli]"
```

这会安装 `typer` 和 `rich`。

### 1.3 安装开发依赖

```bash
pip install -e ".[dev]"
```

---

## 2. 配置 LLM

`minagent` 通过 OpenAI 兼容 API 调用 LLM。你可以使用：

- OpenAI 官方 API
- 阿里云百炼 / 硅基流动等第三方代理
- 本地模型（LM Studio、Ollama、vLLM 等）

### 2.1 环境变量配置

**PowerShell (Windows)**

```powershell
$env:OPENAI_BASE_URL="http://192.168.2.179:1234/v1"
$env:OPENAI_API_KEY="dummy"
$env:MINAGENT_MODEL="qwen/qwen3.6-35b-a3b"
```

**Bash (Linux/macOS)**

```bash
export OPENAI_BASE_URL="http://192.168.2.179:1234/v1"
export OPENAI_API_KEY="dummy"
export MINAGENT_MODEL="qwen/qwen3.6-35b-a3b"
```

### 2.2 代码中显式配置

```python
from minagent import LLMClient

llm = LLMClient(
    base_url="http://192.168.2.179:1234/v1",
    api_key="dummy",
    model="qwen/qwen3.6-35b-a3b",
    timeout=120.0,
)
```

---

## 3. 运行第一个示例

项目已提供一个可运行示例 `examples/readme_demo.py`。

### 3.1 使用 CLI

```bash
minagent examples/readme_demo.py
```

### 3.2 使用 Python

```bash
python examples/readme_demo.py
```

### 3.3 预期输出

```text
Task: 请查看 minagent 项目结构，列出所有 Python 文件，并给出这个项目的简要说明。

============================================================
2026-07-01 09:54:30.551 | INFO     | minagent.core.engine:run:69 - Turn 1/15: calling LLM ...
...

[LLM Turn 1]
我来帮你查看 minagent 项目的结构和 Python 文件。
Tool calls: ['Glob', 'Glob']

[Tool: Glob]
E:\aibes-agent\examples\readme_demo.py
E:\aibes-agent\minagent\cli.py
...

[Final]
## minagent 项目结构
...
```

如果中文显示乱码，先执行：

```powershell
chcp 65001
```

---

## 4. 编写自己的 Agent 脚本

创建一个文件 `my_agent.py`：

```python
import asyncio
import os

from minagent import (
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
        model=os.getenv("MINAGENT_MODEL", "gpt-4o-mini"),
    )

    registry = ToolRegistry()
    registry.register_many([
        FileReadTool(),
        BashTool(),
        GlobTool(),
    ])

    config = AgentConfig(
        system_prompt="你是一个代码分析助手。请使用工具收集信息，然后给出结论。",
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

    task = "列出当前目录下所有 Python 文件，并读取 minagent/__init__.py 的内容。"
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

运行：

```bash
minagent my_agent.py
```

---

## 5. 添加自定义工具

下面写一个能获取当前时间的小工具。

### 5.1 定义工具

```python
from datetime import datetime
from pydantic import BaseModel, Field
from minagent.tools.base import Tool, ToolContext, ToolResult


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

### 5.2 注册并使用

```python
from minagent import ToolRegistry

registry = ToolRegistry()
registry.register(NowTool())
```

LLM 现在可以在需要的时候调用 `Now` 工具了。

---

## 6. 调整权限

默认权限规则：

- `FileRead`、`Grep`、`Glob` 自动允许
- `FileWrite`、`FileEdit`、`Bash`、`TaskList` 需要询问（演示版自动通过）

### 6.1 使用默认权限

```python
from minagent import PermissionEngine

perm = PermissionEngine.default()
```

### 6.2 自定义规则

```python
from minagent.permissions.engine import PermissionEngine, PermissionRule

perm = PermissionEngine(
    rules=[
        PermissionRule("allow", "tool", "FileRead"),
        PermissionRule("allow", "tool", "Glob"),
        PermissionRule("deny", "shell", "rm -rf .*"),
        PermissionRule("allow", "filesystem", "E:/aibes/minagent/**"),
        PermissionRule("deny", "filesystem", "E:/aibes/aibes-vault/**"),
    ],
    mode="auto",
)
```

### 6.3 配置文件中加载

```yaml
# minagent.yaml
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
from minagent.permissions.engine import PermissionEngine

with open("minagent.yaml") as f:
    config = yaml.safe_load(f)

perm = PermissionEngine.from_config(config["permissions"])
```

---

## 7. 常见问题

### Q1: 运行示例后卡在 “calling LLM” 没反应？

大概率是 LLM 服务没有响应或响应较慢。检查：

- `OPENAI_BASE_URL` 是否可访问
- 模型是否已加载完成
- 本地模型首次推理可能需要几十秒

### Q2: 工具返回空结果？

检查 `ToolContext(cwd=...)` 是否指向正确目录。示例中已改为 `os.getcwd()`，避免写死 Unix 路径。

### Q3: 如何关闭 INFO 日志？

```powershell
$env:MINAGENT_LOG_LEVEL="WARNING"
```

### Q4: `minagent` 命令找不到？

重新安装 editable 包：

```bash
pip install -e .
```

---

*下一章：[工具开发实战指南](./TOOL_DEVELOPMENT.md)*
