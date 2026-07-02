# aibes-agent 钻井工程 Agent 指南

> **版本**: 0.4.0  
> **最后更新**: 2026-07-02  
> **关联文档**: [API 参考](./API_REFERENCE.md)、[Skill 系统](./SKILLS.md)

---

## 1. 功能概述

v0.4.0 提供钻井工程领域工具：

- `ParseWitsmlTool`：解析 WITSML XML（well、wellbore、trajectory、log、formation）
- `AnalyzeDrillingLogTool`：CSV/JSON 钻井日志异常检测（IQR）
- `ValidateFormulaTool`：验证水力学公式，支持模板和单位换算
- `QueryKnowledgeBaseTool`：查询钻井规程与事故案例

## 2. 安装

```bash
pip install aibes-agent[drilling]
```

## 3. 使用示例

```python
from aibes_agent import (
    AgentConfig, AgentLoop, ParseWitsmlTool, AnalyzeDrillingLogTool,
    ValidateFormulaTool, QueryKnowledgeBaseTool,
    LLMClient, PermissionEngine, ToolRegistry, ToolContext,
)
import os

llm = LLMClient(base_url="http://localhost:1234/v1", api_key="dummy", model="qwen3-coder")
registry = ToolRegistry()
registry.register_many([
    ParseWitsmlTool(), AnalyzeDrillingLogTool(),
    ValidateFormulaTool(), QueryKnowledgeBaseTool(),
])

config = AgentConfig(
    system_prompt="You are a drilling engineering expert. Analyze data and cite sources.",
    max_turns=15,
)
perm = PermissionEngine.default()
agent = AgentLoop(llm=llm, registry=registry, config=config, permission_engine=perm, tool_context=ToolContext(cwd=os.getcwd()))

async for event in agent.run("Validate ECD formula and check WITSML data"):
    if event["type"] == "final":
        print(event["content"])
```

## 4. 公式模板

`ValidateFormulaTool` 支持以下模板：

| 模板 | 表达式 |
|------|--------|
| `ecd` | `rho * g * TVD / 1000` |
| `annular_pressure` | `rho * g * TVD` |
| `bit_hhp` | `delta_p * q / 1714` |

单位换算：`psi_to_pa`、`pa_to_psi`、`m_to_ft`、`ft_to_m`、`kg_m3_to_ppg`、`ppg_to_kg_m3`。

## 5. Skill

项目已内置 `.aibes-agent/skills/drilling/skill.yaml`，包含 `witsml`、`hydraulics` 等 profile。

```bash
aibes-agent run examples/drilling_analysis_agent.py --skill drilling
```

## 6. 示例脚本

见 `examples/drilling_analysis_agent.py` 和 `examples/hydraulics_validator_agent.py`。

---

*最后更新：2026-07-02*
