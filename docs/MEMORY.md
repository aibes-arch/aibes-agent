# aibes-agent Memory 系统

aibes-agent 提供可扩展的长期记忆（Memory）能力，让 Agent 在会话之间保存和检索重要信息。

---

## 核心概念

- **MemoryEntry**：一条记忆，包含 `id`、`text`、`metadata`、`created_at`。
- **MemoryStore**：存储抽象，支持 `add`、`search`、`delete`、`clear`。
- **MemoryTool**：Agent 可直接调用的工具：`SaveMemory` 和 `SearchMemory`。

---

## 内置实现

### InMemoryMemoryStore

零依赖的内存实现，基于关键词重叠评分，适合测试和小规模使用。

```python
from aibes_agent.memory import InMemoryMemoryStore

store = InMemoryMemoryStore()
store.add("aibes-agent supports plugins and skills.", {"topic": "framework"})
results = store.search("plugins", top_k=5)
for entry in results:
    print(entry.text)
```

### ChromaMemoryStore（可选）

需要安装 `chromadb`：

```bash
pip install chromadb
```

```python
from aibes_agent.memory import ChromaMemoryStore

store = ChromaMemoryStore(persist_directory=".aibes-agent/chroma")
store.add("aibes-agent supports plugins and skills.")
results = store.search("plugins", top_k=5)
```

---

## 在 Agent 中使用 Memory

```python
from aibes_agent import ToolRegistry, ToolContext
from aibes_agent.memory import build_memory_tools
from aibes_agent.core.engine import AgentLoop

store = InMemoryMemoryStore()
registry = ToolRegistry()
for tool in build_memory_tools(store):
    registry.register(tool)

agent = AgentLoop(llm=llm, registry=registry, config=config)
```

Agent 现在可以使用：

- `SaveMemory(text="...", topic="...")` 保存信息。
- `SearchMemory(query="...", top_k=5)` 检索相关记忆。

---

## 自定义 MemoryStore

```python
from aibes_agent.memory.store import MemoryStore, MemoryEntry

class MyMemoryStore(MemoryStore):
    def add(self, text: str, metadata=None) -> str: ...
    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]: ...
    def delete(self, entry_id: str) -> bool: ...
    def clear(self) -> None: ...
```

---

## 与 Tool 缓存的关系

- **ToolResultCache**：缓存只读工具的结果，减少重复调用。
- **MemoryStore**：保存 Agent 认为重要的信息，支持跨任务检索。

两者互补，可通过配置分别启用持久化后端。
