# aibes-agent 领域应用案例：代码审�?Agent

> **版本**: 0.1.0  
> **最后更�?*: 2026-07-01  
> **关联文档**: [工具开发实战指南](./TOOL_DEVELOPMENT.md)、[架构设计](./ARCHITECTURE.md)

---

## 目录

- [1. 场景与目标](#1-场景与目�?
- [2. 需要的工具](#2-需要的工具)
- [3. 系统设计](#3-系统设计)
- [4. 完整脚本示例](#4-完整脚本示例)
- [5. 运行与输出](#5-运行与输�?
- [6. 可扩展方向](#6-可扩展方�?
- [7. 另一个方向：钻井工程代码分析](#7-另一个方向钻井工程代码分�?

---

## 1. 场景与目�?
在团队协作中，代码审查（Code Review）是保证代码质量的关键环节。但人工 review 耗时费力，容易遗漏�?
基于 `aibes-agent` 构建一�?*代码审查 Agent**，可以：

- 自动读取变更文件
- 运行测试和静态检�?- 分析代码中的潜在问题
- 输出结构化的审查报告

### 审查维度

| 维度 | 说明 |
|-----|------|
| 正确�?| 是否有明�?bug、异常处理是否完�?|
| 可维护�?| 命名、注释、复杂度、重复代�?|
| 安全�?| 是否�?SQL 注入、命令注入、敏感信息泄�?|
| 性能 | 是否有不必要的循环、阻塞操作、N+1 查询 |
| 测试覆盖 | 新增代码是否有对应测�?|

---

## 2. 需要的工具

| 工具 | 用�?|
|-----|------|
| `FileRead` | 读取变更的代码文�?|
| `Grep` | 搜索特定模式（如 `eval`、`exec`、`password`�?|
| `Glob` | 枚举项目文件 |
| `Bash` | 运行 `git diff`、测试、lint |
| `TaskList` | 跟踪审查步骤 |

后续可扩展：

- `GitDiffTool`：直接获�?PR diff
- `CoverageTool`：读取测试覆盖率报告
- `LintTool`：运�?`ruff`、`mypy`、`black --check`

---

## 3. 系统设计

```mermaid
flowchart LR
    U[用户输入<br/>"review 当前变更"] --> A[CodeReviewAgent]
    A --> T1[FileRead]
    A --> T2[Grep]
    A --> T3[Bash<br/>git diff / pytest]
    A --> T4[TaskList]
    T1 --> A
    T2 --> A
    T3 --> A
    A --> R[审查报告]
```

Agent 工作流：

1. 获取 `git diff`，识别变更文件�?2. 读取每个变更文件的内容�?3. 搜索高风险模式（�?`eval`、`subprocess.shell=True`）�?4. 运行单元测试�?lint�?5. 综合分析，输�?Markdown 审查报告�?
---

## 4. 完整脚本示例

创建 `examples/code_review_agent.py`�?
```python
import asyncio
import os

from aibes-agent import (
    AgentConfig,
    AgentLoop,
    BashTool,
    FileReadTool,
    GlobTool,
    GrepTool,
    LLMClient,
    PermissionEngine,
    PermissionRule,
    TaskListTool,
    ToolContext,
    ToolRegistry,
)


async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen/qwen3.6-35b-a3b"),
    )

    registry = ToolRegistry()
    registry.register_many([
        FileReadTool(),
        BashTool(),
        GrepTool(),
        GlobTool(),
        TaskListTool(),
    ])

    config = AgentConfig(
        system_prompt="""你是一位严格的代码审查专家。请按以下维度审查代码变更：
1. 正确性：是否有明�?bug、异常处理是否完�?2. 可维护性：命名、注释、复杂度、重复代�?3. 安全性：是否�?SQL 注入、命令注入、敏感信息泄�?4. 性能：是否有不必要的循环、阻塞操�?5. 测试覆盖：新增代码是否有对应测试

请使用工具收集信息，最终输出一份结构化�?Markdown 审查报告�?"",
        max_turns=15,
    )

    # 允许读取项目文件，允许运�?git、pytest、ruff 等安全命�?    perm = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "tool", "Grep"),
            PermissionRule("allow", "tool", "Glob"),
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("allow", "tool", "TaskList"),
            PermissionRule("allow", "shell", "git .*"),
            PermissionRule("allow", "shell", "pytest .*"),
            PermissionRule("allow", "shell", "ruff .*"),
            PermissionRule("allow", "shell", "python -m pytest .*"),
        ],
        mode="auto",
    )

    tool_context = ToolContext(cwd=os.getcwd())

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=tool_context,
    )

    task = "请审查当�?git 工作区的代码变更，输出一份代码审查报告�?

    async for event in agent.run(task):
        if event["type"] == "llm_response":
            print(f"\n[LLM Turn {event['turn']}]")
            if event["content"]:
                print(event["content"])
            if event["tool_calls"]:
                names = [tc["function"]["name"] for tc in event["tool_calls"]]
                print(f"Tool calls: {names}")
        elif event["type"] == "tool_result":
            print(f"\n[Tool: {event['name']}]\n{event['content'][:500]}")
        elif event["type"] == "final":
            print(f"\n{'='*60}\n[审查报告]\n{event['content']}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. 运行与输�?
### 5.1 运行

```bash
aibes-agent run examples/code_review_agent.py
```

### 5.2 典型执行流程

```text
[LLM Turn 1]
我先查看当前代码变更�?Tool calls: ['Bash']

[Tool: Bash]
diff --git a/aibes-agent/core/engine.py b/aibes-agent/core/engine.py
...

[LLM Turn 2]
接下来读取变更文件并运行测试�?Tool calls: ['FileRead', 'FileRead', 'Bash']

[Tool: FileRead]
... engine.py 内容 ...

[Tool: Bash]
============================= test session starts ==============================
...

[LLM Turn 5]
============================================================
[审查报告]
## 代码审查报告

### 变更文件
- `aibes-agent/core/engine.py`
- `aibes-agent/core/llm.py`

### 审查结果

| 维度 | 评分 | 说明 |
|------|------|------|
| 正确�?| �?通过 | 新增日志不影响核心逻辑 |
| 可维护�?| ⚠️ 建议 | 建议为日志消息添加常�?|
| 安全�?| �?通过 | 无新增安全风�?|
| 性能 | �?通过 | 日志为同步写入，量小可接�?|
| 测试覆盖 | ⚠️ 建议 | 建议补充日志相关测试 |

### 建议
1. ...
```

---

## 6. 可扩展方�?
### 6.1 接入 Git PR

未来可添�?`GitDiffTool`�?
```python
class GitDiffTool(Tool):
    name = "GitDiff"
    description = "Get git diff for the working directory or a specific commit range."
```

### 6.2 接入 Lint / Coverage

```python
PermissionRule("allow", "shell", "ruff check ."),
PermissionRule("allow", "shell", "pytest --cov=aibes-agent tests/"),
```

### 6.3 保存审查报告

�?Agent 调用 `FileWriteTool` 把报告写�?`.aibes-agent/reviews/{timestamp}.md`�?
---

## 7. 另一个方向：钻井工程代码分析

`aibes-agent` 同样适用于垂直领域。以**钻井工程代码分析**为例�?
### 7.1 领域工具

| 工具 | 功能 |
|-----|------|
| `ParseWitsmlTool` | 解析 WITSML 钻井数据 |
| `AnalyzeDrillingLogTool` | 分析钻井日志异常 |
| `ValidateFormulaTool` | 验证水力学公�?|
| `QueryKnowledgeBaseTool` | 查询钻井规程和事故案�?|

### 7.2 典型任务

```text
"分析这段钻井参数计算代码，检查单位换算是否正确，
 并验证水力学公式是否符合 SY/T 标准�?
```

### 7.3 与代码审�?Agent 的异�?
- **相同**：都使用 `FileRead`、`Grep`、`Bash` 等基础工具�?- **不同**：需要领域工具解析专业数据格式，system prompt 需要注入领域知识�?
---

## 8. 小结

通过代码审查 Agent 这个案例，可以看�?`aibes-agent` 的核心价值：

- **快速组合基础工具**完成复杂任务
- **通过 system prompt 定义领域角色**
- **通过权限规则控制工具行为**
- **通过事件流获取执行过�?*

你可以在此基础上，替换工具�?prompt，快速构建属于自己的领域 Agent�?
---

*下一章：[贡献指南](./CONTRIBUTING.md)*
