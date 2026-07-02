# aibes-agent 代码审查 Agent 指南

> **版本**: 0.4.0  
> **最后更新**: 2026-07-02  
> **关联文档**: [API 参考](./API_REFERENCE.md)、[Skill 系统](./SKILLS.md)

---

## 1. 功能概述

v0.4.0 提供代码审查领域工具，帮助 Agent 自动完成代码审查任务：

- `GitDiffTool`：获取 git diff
- `LintTool`：运行 ruff、mypy、bandit
- `CoverageTool`：运行或解析测试覆盖率

## 2. 安装

```bash
pip install aibes-agent[code_review]
```

## 3. 使用示例

```python
from aibes_agent import (
    AgentConfig, AgentLoop, GitDiffTool, LintTool, CoverageTool,
    LLMClient, PermissionEngine, ToolRegistry, ToolContext,
)
import os

llm = LLMClient(base_url="http://localhost:1234/v1", api_key="dummy", model="qwen3-coder")
registry = ToolRegistry()
registry.register_many([GitDiffTool(), LintTool(), CoverageTool()])

config = AgentConfig(
    system_prompt="You are a strict code reviewer. Review changes and output a Markdown report.",
    max_turns=15,
)
perm = PermissionEngine.default()
agent = AgentLoop(llm=llm, registry=registry, config=config, permission_engine=perm, tool_context=ToolContext(cwd=os.getcwd()))

async for event in agent.run("Review current git changes"):
    if event["type"] == "final":
        print(event["content"])
```

## 4. Skill

项目已内置 `.aibes-agent/skills/code-review/skill.yaml`，包含 `lint`、`coverage`、`security` 等 profile。

```bash
aibes-agent run examples/code_review_agent.py --skill code-review
```

## 5. 示例脚本

见 `examples/code_review_agent.py` 和 `examples/security_audit_agent.py`。

---

*最后更新：2026-07-02*
