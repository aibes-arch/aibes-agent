# aibes-agent 工具开发实战指�?
> **版本**: 0.4.0  
> **最后更�?*: 2026-07-02  
> **关联文档**: [API 参考](./API_REFERENCE.md)、[模块设计](./MODULE_DESIGN.md)

---

## 目录

- [1. 工具是什么](#1-工具是什�?
- [2. 最小工具示例](#2-最小工具示�?
- [3. 工具基类详解](#3-工具基类详解)
- [4. 输入模型设计](#4-输入模型设计)
- [5. 输出与错误处理](#5-输出与错误处�?
- [6. 并发与权限](#6-并发与权�?
- [7. 完整实战：HTTP 请求工具](#7-完整实战-http-请求工具)
- [8. 完整实战：JSON 文件读取工具](#8-完整实战-json-文件读取工具)
- [9. 工具测试](#9-工具测试)
- [10. 工具集成清单](#10-工具集成清单)
- [11. 最佳实践](#11-最佳实�?

---

## 1. 工具是什�?
�?`aibes-agent` 中，**工具（Tool�?* �?Agent 与外部世界交互的接口。Agent 本身不会直接读文件、执行命令或访问网络，它只能通过调用工具来完成这些操作�?
一个好的工具应该：

- 职责单一
- 输入/输出定义清晰
- 错误处理完善
- �?LLM 友好（描述明确、参数易懂）

---

## 2. 最小工具示�?
```python
from pydantic import BaseModel, Field
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class GreetInput(BaseModel):
    name: str = Field(..., description="Name to greet")


class GreetTool(Tool):
    name = "Greet"
    description = "Return a greeting message for the given name."
    input_model = GreetInput

    def is_read_only(self, input: GreetInput) -> bool:
        return True

    async def call(self, input: GreetInput, context: ToolContext) -> ToolResult:
        return ToolResult.ok(f"Hello, {input.name}!")
```

使用�?
```python
from aibes-agent import ToolRegistry

registry = ToolRegistry()
registry.register(GreetTool())
```

---

## 3. 工具基类详解

```python
class Tool(ABC):
    name: str = ""                    # 工具名，必须唯一
    description: str = ""             # �?LLM 看的描述
    input_model: Type[BaseModel]      # 输入 schema
    output_model: Type[BaseModel] = ToolResult

    def to_openai_schema(self) -> Dict[str, Any]
    def is_read_only(self, input: BaseModel) -> bool
    def is_concurrency_safe(self, input: BaseModel) -> bool

    @abstractmethod
    async def call(self, input: BaseModel, context: ToolContext) -> ToolResult
```

### 必须实现

- `name`
- `description`
- `input_model`
- `call()`

### 建议重写

- `is_read_only()`：影响并发策略和权限判断�?- `is_concurrency_safe()`：默认等�?`is_read_only()`，复杂工具可单独控制�?
---

## 4. 输入模型设计

使用 Pydantic `BaseModel` 定义输入，每个字段都要写 `description`，这�?LLM 理解参数的关键�?
### 示例：文件读�?
```python
class FileReadInput(BaseModel):
    file_path: str = Field(
        ...,
        description="Absolute path to the file to read",
    )
    offset: int = Field(
        1,
        description="Line number to start from (1-indexed)",
    )
    limit: int = Field(
        500,
        description="Maximum number of lines to read",
    )
```

### 设计建议

1. **字段名用英文小写 + 下划�?*，与 LLM 常见风格一致�?2. **必填字段�?`...`**，可选字段给默认值�?3. **description 要写清楚单位、格式、约�?*�?4. **枚举值说�?*：如果字段是枚举，列出可选值�?
```python
class SearchInput(BaseModel):
    output_mode: str = Field(
        "files_with_matches",
        description="Output format: files_with_matches, content, or count",
    )
```

---

## 5. 输出与错误处�?
工具统一返回 `ToolResult`�?
### 成功

```python
return ToolResult.ok(
    content="file content here",
    file_path="/path/to/file",
    total_lines=100,
)
```

### 失败

```python
return ToolResult.fail(
    error="File not found: /path/to/file",
    content="",  # 可选的额外信息
)
```

### 错误处理原则

1. **不要让异常抛�?*：`ToolRegistry` 会捕�?`call()` 中的异常，但最好自己处理�?2. **错误信息要具�?*：包含文件名、命令、原因�?3. **敏感信息不要返回**：比�?API Key、密码�?
```python
async def call(self, input, context):
    try:
        result = await do_something(input)
        return ToolResult.ok(result)
    except FileNotFoundError as e:
        return ToolResult.fail(f"File not found: {e.filename}")
    except TimeoutError:
        return ToolResult.fail("Operation timed out")
    except Exception as e:
        return ToolResult.fail(f"Unexpected error: {type(e).__name__}: {e}")
```

---

## 6. 并发与权�?
### 6.1 只读 vs 写入

```python
def is_read_only(self, input: MyInput) -> bool:
    return input.action == "read"
```

`ToolRegistry` 会据此决定：

- 只读工具 �?并发执行
- 写入工具 �?串行执行

### 6.2 动态并�?
有些工具根据参数决定只读/写入�?
```python
class BashTool(Tool):
    def is_read_only(self, input: BashInput) -> bool:
        return input.command.strip().startswith(("ls", "cat", "echo"))
```

### 6.3 权限配合

`PermissionEngine` 会检�?`filesystem` / `shell` / `tool` 规则。工具参数中应包含可被检查的关键字段�?
- 文件操作：`file_path` �?`path`
- Shell 操作：`command`

---

## 7. 完整实战：HTTP 请求工具

```python
import httpx
from pydantic import BaseModel, Field
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class HttpGetInput(BaseModel):
    url: str = Field(..., description="URL to fetch")
    timeout: int = Field(30, description="Request timeout in seconds")


class HttpGetTool(Tool):
    name = "HttpGet"
    description = "Fetch a URL via HTTP GET and return the response body (truncated to 2000 chars)."
    input_model = HttpGetInput

    def is_read_only(self, input: HttpGetInput) -> bool:
        return True

    async def call(self, input: HttpGetInput, context: ToolContext) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=input.timeout) as client:
                response = await client.get(input.url)
                response.raise_for_status()
                text = response.text[:2000]
                return ToolResult.ok(
                    text,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                )
        except httpx.HTTPStatusError as e:
            return ToolResult.fail(f"HTTP error {e.response.status_code} for {input.url}")
        except httpx.RequestError as e:
            return ToolResult.fail(f"Request failed: {e}")
        except Exception as e:
            return ToolResult.fail(f"Unexpected error: {e}")
```

---

## 8. 完整实战：JSON 文件读取工具

```python
import json
from pathlib import Path
from pydantic import BaseModel, Field
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class JsonReadInput(BaseModel):
    file_path: str = Field(..., description="Path to JSON file")
    key: str = Field("", description="Dot-separated key to extract, e.g. 'user.name'")


class JsonReadTool(Tool):
    name = "JsonRead"
    description = "Read a JSON file and optionally extract a nested key."
    input_model = JsonReadInput

    def is_read_only(self, input: JsonReadInput) -> bool:
        return True

    def _get_nested(self, data, key: str):
        if not key:
            return data
        for part in key.split("."):
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                return None
        return data

    async def call(self, input: JsonReadInput, context: ToolContext) -> ToolResult:
        path = Path(input.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return ToolResult.fail(f"Invalid JSON: {e}")
        except Exception as e:
            return ToolResult.fail(f"Failed to read file: {e}")

        value = self._get_nested(data, input.key)
        if input.key and value is None:
            return ToolResult.fail(f"Key '{input.key}' not found in {path}")

        return ToolResult.ok(
            json.dumps(value, ensure_ascii=False, indent=2),
            file_path=str(path),
            key=input.key,
        )
```

---

## 9. 工具测试

每个工具都应该有单元测试。以 `JsonReadTool` 为例�?
```python
import pytest
from aibes_agent.tools.base import ToolContext
from my_tools.json_read import JsonReadTool


@pytest.mark.asyncio
async def test_json_read(tmp_path):
    tool = JsonReadTool()
    ctx = ToolContext(cwd=str(tmp_path))

    file = tmp_path / "data.json"
    file.write_text('{"user": {"name": "Alice", "age": 30}}', encoding="utf-8")

    result = await tool.call(
        tool.input_model(file_path=str(file), key="user.name"),
        ctx,
    )

    assert result.success
    assert "Alice" in result.content
```

### 测试要点

1. 正常路径
2. 错误路径（文件不存在、参数无效、超时等�?3. `is_read_only()` 的行�?4. 大输�?边界条件

---

## 10. 工具集成清单

写完工具后，按以下清单集成到项目�?
- [ ] 工具类文件放�?`aibes-agent/tools/` 下或单独的领域包�?- [ ] �?`aibes-agent/tools/__init__.py` 中导�?- [ ] �?`aibes-agent/__init__.py` 中导出（如果希望用户直接 `from aibes-agent import`�?- [ ] �?`ToolRegistry` 中注�?- [ ] 添加单元测试�?`tests/`
- [ ] 更新 [模块设计](./MODULE_DESIGN.md) 文档
- [ ] 更新 [API 参考](./API_REFERENCE.md) 文档

---

## 11. 最佳实�?
### 11.1 描述要写�?LLM �?
```python
# �?description = "Search file contents using ripgrep (rg). Returns matching file paths or lines."

# 不好
description = "grep tool"
```

### 11.2 输出要简�?
LLM 上下文有限，工具输出尽量精简�?
- 文件读取：默�?500 行，支持 `offset`/`limit`
- 搜索：默�?250 条结�?- HTTP：默认截断到 2000 字符

### 11.3 参数命名一�?
- 文件路径�?`file_path` �?`path`
- 命令�?`command`
- 超时�?`timeout`

### 11.4 避免副作�?
只读工具不要修改文件系统或外部状态�?
### 11.5 状态共享通过 ToolContext

如果多个工具调用需要共享状态，使用 `context.set()` �?`context.get()`，而不是全局变量�?
```python
tasks = context.get("tasks", [])
tasks.append(new_task)
context.set("tasks", tasks)
```

---

*下一章：[领域应用案例](./DOMAIN_CASE.md)*
