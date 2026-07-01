# aibes-agent 会话持久化

`aibes-agent` 可以保存和恢复对话历史与任务状态，支持跨进程继续执行。

---

## 配置

```yaml
session:
  store: file
  path: ".aibes-agent/sessions"
```

---

## API 使用

```python
import asyncio
from aibes_agent.core.engine import AgentLoop
from aibes_agent.core.session import FileSessionStore

store = FileSessionStore(".aibes-agent/sessions")
agent = AgentLoop(..., session_store=store)

async for event in agent.run("My task", session_id="sess-1"):
    print(event)
```

---

## CLI 使用

```bash
aibes-agent run examples/readme_demo.py --session sess-1 --config aibes-agent.yaml
```

第二次运行时，Agent 会自动恢复 `sess-1` 的上下文。

---

## 存储格式

会话以 JSON 文件保存：

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

继承 `SessionStore` 实现 `save`、`load`、`list_sessions` 方法即可接入其他后端（如 Redis、数据库）。
