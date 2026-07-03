# aibes-agent 会话持久化

`aibes-agent` 可以保存和恢复对话历史与任务状态，支持跨进程继续执行。

---

## 配置

```yaml
session:
  store: file          # file | memory | sqlite | redis
  path: ".aibes-agent/sessions"
  url: "redis://localhost:6379/0"   # redis 时使用
  ttl: 0                             # redis 自动过期时间（秒），0 表示不过期
```

后端说明：

| `store` | 说明 | 适用场景 |
|---------|------|----------|
| `file` | JSON 文件（默认） | 单机、快速验证 |
| `memory` | 进程内字典 | 测试、无状态运行 |
| `sqlite` | SQLite 数据库 | 需要结构化查询或大量会话 |
| `redis` | Redis（需安装 `redis` 包） | 分布式、多进程共享 |

---

## API 使用

```python
import asyncio
from aibes_agent import MinagentConfig
from aibes_agent.core.engine import AgentLoop

cfg = MinagentConfig.load()
store = cfg.to_session_store()
agent = AgentLoop(..., session_store=store)

async for event in agent.run("My task", session_id="sess-1"):
    print(event)
```

第二次运行时，Agent 会自动恢复 `sess-1` 的上下文。

---

## CLI 使用

运行脚本时指定 session：

```bash
aibes-agent run examples/readme_demo.py --session sess-1 --config aibes-agent.yaml
```

管理已保存的会话：

```bash
aibes-agent sessions list
aibes-agent sessions delete sess-1
aibes-agent sessions clear
aibes-agent sessions cleanup --max-age 86400
```

---

## 存储格式

会话保存为 JSON，包含以下字段：

```json
{
  "session_id": "sess-1",
  "messages": [...],
  "tasks": [...],
  "metadata": {}
}
```

---

## 自定义存储后端

继承 `SessionStore` 并实现以下方法即可接入其他后端：

```python
from aibes_agent.core.session import SessionStore, SessionState

class MySessionStore(SessionStore):
    async def save(self, state: SessionState) -> None: ...
    async def load(self, session_id: str) -> Optional[SessionState]: ...
    async def list_sessions(self) -> List[str]: ...
    async def delete(self, session_id: str) -> bool: ...
    async def clear(self) -> None: ...
    async def cleanup(self, max_age_seconds: float) -> int: ...
```
