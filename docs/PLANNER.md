# Planner 与任务编排

> **版本**: v0.6.0  
> **最后更新**: 2026-07-02  
> **关联文档**: [模块设计](./MODULE_DESIGN.md)、[API 参考](./API_REFERENCE.md)

---

## 1. 概述

`aibes-agent` 在 v0.6.0 引入独立的 **Planner（规划器）** 模块，把 Agent 从“LLM 隐式选工具”升级为“显式规划 + 执行”模式：

- 将复杂任务拆解为带依赖关系的执行步骤
- 每个步骤可以调用单个工具，或委托给某个子 Agent profile
- 自动按依赖顺序执行，失败后可重新规划

Planner 既可以直接在代码中调用，也通过 `PlannerTool` 暴露给 `AgentLoop`，并在 Web UI 启动时自动注册。

---

## 2. 核心组件

```text
Planner
   │ plan(task) -> Plan
   │ validate(plan)
   │ decompose(task)
   └─ replan(task, failed_plan, reason)

PlanExecutor
   └─ execute(plan) -> Plan

PlannerTool (Tool)
   └─ call({task, allow_replan}) -> ToolResult
```

| 组件 | 文件 | 职责 |
|------|------|------|
| `Plan` / `PlanStep` | `aibes_agent/planner/models.py` | 计划数据模型 |
| `Planner` | `aibes_agent/planner/planner.py` | 生成、校验、重新生成计划 |
| `PlanExecutor` | `aibes_agent/planner/executor.py` | 按依赖顺序执行计划 |
| `PlannerTool` | `aibes_agent/planner/tool.py` | 把 Planner 封装成可调用的 Tool |

---

## 3. 数据模型

### 3.1 `PlanStep`

| 字段 | 类型 | 说明 |
|------|------|------|
| `step_id` | `str` | 步骤唯一标识 |
| `description` | `str` | 步骤描述，会作为子 Agent 的任务输入 |
| `tool` | `Optional[str]` | 本步骤要调用的工具名（与 `agent_profile` 二选一） |
| `agent_profile` | `Optional[str]` | 本步骤要委托的子 Agent profile 名 |
| `depends_on` | `List[str]` | 前置步骤 `step_id` 列表 |
| `status` | `str` | `pending` / `running` / `done` / `failed` |
| `result` | `str` | 执行结果或错误信息 |

### 3.2 `Plan`

| 字段 | 类型 | 说明 |
|------|------|------|
| `task` | `str` | 原始任务描述 |
| `steps` | `List[PlanStep]` | 执行步骤列表 |

便捷方法：

- `Plan.is_complete()`：所有步骤均为 `done` 或 `failed`
- `Plan.failed_steps()`：返回失败步骤
- `Plan.to_dict()` / `Plan.from_dict()`：序列化与反序列化

---

## 4. Planner

`Planner` 负责把自然语言任务转换为结构化的 `Plan`。

### 4.1 构造

```python
from aibes_agent import LLMClient, ToolRegistry
from aibes_agent.planner import Planner

planner = Planner(
    llm=llm,
    registry=registry,
    profiles={"coder": coder_profile},
    max_steps=10,
)
```

- `llm`: 用于生成计划的 LLM 客户端
- `registry`: 可用工具注册表，Planner 会用它校验步骤里的 `tool`
- `profiles`: 可选子 Agent profile 字典，用于校验 `agent_profile`
- `max_steps`: 单计划最大步骤数，超出会被截断

### 4.2 主要方法

#### `async plan(task: str) -> Plan`

向 LLM 发送规划 prompt，要求其返回如下 JSON：

```json
{
  "steps": [
    {
      "step_id": "1",
      "description": "列出项目下的所有 Python 文件",
      "tool": "Glob"
    },
    {
      "step_id": "2",
      "description": "读取每个文件并总结职责",
      "tool": "FileRead",
      "depends_on": ["1"]
    }
  ]
}
```

返回的候选计划会经过 `validate()` 校验；若 LLM 输出无法解析或校验失败，则返回**单步回退计划**（fallback plan），直接委托给 `default` profile 或当前 Agent 执行，避免完全失败。

#### `validate(plan: Plan) -> bool`

校验内容：

1. 步骤引用的 `tool` 必须存在于 `registry`
2. 步骤引用的 `agent_profile` 必须存在于 `profiles`
3. `depends_on` 中的 `step_id` 必须存在

#### `async decompose(task: str) -> List[str]`

把任务拆成 3-7 条子任务，返回字符串列表。可用于需要粗粒度拆分的场景。

#### `async replan(task: str, failed_plan: Plan, reason: str) -> Plan`

基于失败原因和原计划，让 LLM 生成修正后的新计划，并再次校验。

---

## 5. PlanExecutor

`PlanExecutor` 负责把 `Plan` 真正跑起来。

### 5.1 执行流程

1. 按 `depends_on` 做**拓扑排序**
2. 依次执行每个步骤
3. 若某步骤的任一依赖失败，则跳过该步骤并标记为 `failed`
4. 每个步骤内部启动一个受限的 `AgentLoop`
   - 若步骤指定 `agent_profile`，使用该 profile 的 system prompt 和工具集
   - 若步骤指定 `tool`，只把该工具加入子注册表
   - 否则使用全部可用工具

### 5.2 构造

```python
from aibes_agent import PermissionEngine, ToolContext
from aibes_agent.planner import PlanExecutor

executor = PlanExecutor(
    llm=llm,
    registry=registry,
    profiles={"coder": coder_profile},
    permission_engine=PermissionEngine.default(),
    tool_context=ToolContext(cwd=os.getcwd()),
    max_turns_per_step=10,
)

result_plan = await executor.execute(plan)
```

- `max_turns_per_step`: 每个步骤内部 AgentLoop 的最大轮数，防止单步无限循环

---

## 6. PlannerTool

`PlannerTool` 把整套“规划 + 执行”封装为一个普通 Tool，方便 `AgentLoop` 在合适的时候自行调用。

### 6.1 输入模型

```python
class PlannerInput(BaseModel):
    task: str              # 要规划和执行的复杂任务
    allow_replan: bool = True   # 失败后是否尝试重新规划一次
```

### 6.2 注册方式

```python
from aibes_agent.planner import PlannerTool

registry.register(
    PlannerTool(
        llm=llm,
        registry=registry,
        profiles=profiles,
        permission_engine=permission_engine,
        tool_context=tool_context,
    )
)
```

### 6.3 Web UI 自动注册

在 `aibes_agent web` 启动时， lifespan 会自动把 `PlannerTool` 注册到 `ToolRegistry` 中，与 `AgentTool` 并列可用。

### 6.4 输出格式

执行完成后，`PlannerTool` 返回一段格式化文本，包含每步的执行状态和结果摘要，例如：

```text
Plan for: 列出 aibes_agent 目录下的 Python 文件并总结职责

[✓] 1: 列出 aibes_agent 目录下的所有 Python 文件
    -> 找到 12 个文件 ...
[✓] 2: 读取每个文件并总结主要职责
    -> 已生成文件职责摘要 ...
```

---

## 7. 使用示例

完整示例见 [`examples/planner_demo.py`](../examples/planner_demo.py)。

```python
import asyncio
import os
from aibes_agent import LLMClient, PermissionEngine, ToolContext, ToolRegistry
from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.planner import PlannerTool
from aibes_agent.tools import BashTool, FileReadTool, GlobTool, GrepTool

async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("AIBES_AGENT_MODEL"),
    )

    registry = ToolRegistry()
    registry.register(FileReadTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    registry.register(
        PlannerTool(
            llm=llm,
            registry=registry,
            permission_engine=PermissionEngine.default(),
            tool_context=ToolContext(cwd=os.getcwd()),
        )
    )

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=AgentConfig(system_prompt="Use the Planner tool for complex multi-step tasks."),
        permission_engine=PermissionEngine.default(),
        tool_context=ToolContext(cwd=os.getcwd()),
    )

    async for event in agent.run("请列出 aibes_agent 目录下的所有 Python 文件，并总结每个文件的主要职责。"):
        print(event)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. 设计原则与注意事项

1. **Planner 只负责“计划”**：它生成结构化的步骤，但不直接执行工具。
2. **执行器负责“如何跑”**：每个步骤都是一个受限的子 AgentLoop，拥有自己的工具集和轮数限制。
3. **失败可回退**：LLM 输出不合法时，Planner 会生成单步回退计划，保证调用方不会空转。
4. **依赖失败会跳过**：执行器不会执行依赖已失败的步骤，避免错误扩散。
5. **Replan 只触发一次**：`PlannerTool` 默认失败后只重新规划一次，防止无限循环。

---

## 9. 已知限制

- Planner 依赖 LLM 生成合法 JSON，当前使用轻量级 prompt + JSON 解析，未接入结构化输出 schema。
- 计划步骤之间通过 `depends_on` 串行化，暂不支持步骤内并行。
- Replan 不会修改已经执行成功的步骤，仅在失败时生成完整新计划重新执行。

---

*参考：[模块设计](./MODULE_DESIGN.md)、[API 参考](./API_REFERENCE.md)*
