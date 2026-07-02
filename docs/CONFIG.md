# aibes-agent 配置文件

`aibes-agent` 支持通过 `aibes-agent.yaml` 或 `.aibes-agent/config.yaml` 进行项目级配置。

---

## 搜索顺序

1. CLI 显式传入：`--config path/to/config.yaml`
2. 环境变量：`AIBES_AGENT_CONFIG`
3. 当前目录：`./aibes-agent.yaml`
4. 当前目录：`./.aibes-agent/config.yaml`
5. 全部缺失时使用默认值

---

## 完整示例

```yaml
llm:
  base_url: "http://192.168.2.179:1234/v1"
  api_key: "dummy"
  model: "qwen/qwen3.6-35b-a3b"
  timeout: 120.0
  max_retries: 2
  retry_delay: 1.0

router:
  default: "qwen/qwen3.6-35b-a3b"
  rules:
    - pattern: "^(write|edit|create).*"
      model: "qwen/qwen3-coder-plus-32k"

permissions:
  mode: auto
  rules:
    - { action: allow, resource_type: tool, pattern: FileRead }
    - { action: ask,  resource_type: tool, pattern: Bash }

skills:
  auto_load: true
  paths:
    - ".aibes-agent/skills"

plugins:
  auto_load: true
  entry_points: true
  paths:
    - ".aibes-agent/plugins"

mcp_servers:
  filesystem:
    transport: stdio
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "."]

session:
  store: file
  path: ".aibes-agent/sessions"

web:
  host: "127.0.0.1"
  port: 8000
```

---

## 环境变量覆盖

| 环境变量 | 覆盖字段 |
|----------|----------|
| `AIBES_AGENT_CONFIG` | 配置文件路径 |
| `AIBES_AGENT_BASE_URL` | `llm.base_url` |
| `AIBES_AGENT_API_KEY` | `llm.api_key` |
| `AIBES_AGENT_MODEL` | `llm.model` |
| `AIBES_AGENT_LOG_LEVEL` | 日志级别 |

---

## 程序化使用

```python
from aibes_agent.config import MinagentConfig

cfg = MinagentConfig.load()
llm = cfg.to_llm_client()
perm = cfg.to_permission_engine()
store = cfg.to_session_store()
```
