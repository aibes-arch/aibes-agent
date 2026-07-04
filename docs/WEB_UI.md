# aibes-agent Web UI

`aibes-agent` 内置基于 FastAPI + SSE 的实时 Web 界面，可在浏览器中提交任务并观察 Agent 执行过程。

---

## 启动

```bash
aibes-agent web --config aibes-agent.yaml --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000` 即可使用。

### 启动慢 / 卡在 Waiting for application startup

启动时 Web UI 会初始化工具、Skill、MCP 连接等。最常见的原因是 **MCP 服务器连接超时**，例如 `npx` 需要下载包或 MCP 服务未启动。

可以在 `aibes-agent.yaml` 中调整：

```yaml
mcp:
  enabled: true          # 设为 false 可完全跳过 MCP，启动最快
  connect_timeout: 10.0  # 单个 MCP 服务器连接超时（秒）
```

启动日志会显示当前进行到哪一步，方便定位耗时环节。

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | HTML 任务界面 |
| `/api/sessions` | GET | 列出已保存的会话 |
| `/api/tools` | GET | 列出当前可用工具 |
| `/api/run/{session_id}` | POST | 提交任务（后台执行） |
| `/api/events/{session_id}` | GET | SSE 事件流 |

---

## 提交任务示例

```bash
curl -X POST http://127.0.0.1:8000/api/run/my-session \
  -H "Content-Type: application/json" \
  -d '{"task": "List all Python files in the project"}'
```

然后访问：

```bash
curl http://127.0.0.1:8000/api/events/my-session
```

---

## 会话隔离

每个 `session_id` 拥有独立的上下文。同一 `session_id` 的多次任务会共享对话历史（若启用了会话持久化）。
