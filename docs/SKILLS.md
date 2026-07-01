# aibes-agent Skill 系统

Skill 是可复用的 **system prompt + 工具集 + 子 Agent profile** 组合，适合按项目或领域组织 Agent 能力。

---

## Skill 目录结构

```text
.aibes-agent/skills/
└── code-review/
    └── skill.yaml
```

`skill.yaml` 示例：

```yaml
name: code-review
description: Strict code review assistant.
system_prompt: |
  You are a strict code reviewer. Focus on correctness, maintainability,
  security, and performance.
tools:
  - FileRead
  - Grep
  - Glob
profiles:
  security:
    system_prompt: Focus only on security issues.
    tools:
      - FileRead
      - Grep
    max_turns: 5
```

---

## 字段说明

| 字段 | 说明 |
|------|------|
| `name` | Skill 名称，默认使用目录名 |
| `description` | 描述 |
| `system_prompt` | 合并到 Agent system prompt |
| `tools` | 该 Skill 授权使用的工具名列表 |
| `mcp_servers` | （可选）该 Skill 依赖的 MCP server 名 |
| `profiles` | 子 Agent profile 定义 |

---

## 加载与使用

```python
from aibes_agent.skills import SkillBuilder, SkillLoader
from aibes_agent.tools import FileReadTool, GrepTool

tool_pool = {"FileRead": FileReadTool(), "Grep": GrepTool()}
skills = SkillLoader().load_all()
builder = SkillBuilder(skills, tool_pool)

agent_config, registry, profiles = builder.build()
```

如果未加载任何 Skill，`SkillBuilder` 会自动注册全部内置工具，确保默认行为可用。

---

## 多 Skill 合并规则

- 多个 Skill 的 `system_prompt` 按顺序拼接。
- 工具集取并集。
- 同名 profile 会抛出错误。
