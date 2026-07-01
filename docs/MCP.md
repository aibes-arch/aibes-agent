# aibes-agent MCP 支持

`aibes-agent` 可以通过 [Model Context Protocol](https://modelcontextprotocol.io/) 调用外部 MCP 服务器提供的工具。

---

## 依赖

```bash
pip install aibes-agent[mcp]
```

---

## 配置 MCP 服务器

在 `aibes-agent.yaml` 中定义：

```yaml
mcp_servers:
  filesystem:
    transport: stdio
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "."]
  remote:
    transport: sse
    url: "http://localhost:8080/sse"
```

---

## 工具命名

MCP 工具会被加上前缀，避免与内置工具冲突：

```text
mcp_<server_name>_<tool_name>
```

例如 `filesystem` 服务器的 `read_file` 工具会变为 `mcp_filesystem_read_file`。

---

## 程序化使用

```python
import asyncio
from aibes_agent.config import MCPServerConfig
from aibes_agent.mcp.client import MCPClient

async def main():
    async with MCPClient({
        "fs": MCPServerConfig(
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "."],
        )
    }) as client:
        tools = await client.get_tools()
        print(list(tools.keys()))

asyncio.run(main())
```

---

## 安全提示

- 只连接可信的 MCP 服务器。
- MCP 工具默认视为非只读，需要权限引擎授权。
- 通过 Skill 可以限制 Agent 可使用的 MCP 工具范围。
