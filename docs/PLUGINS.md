# aibes-agent Plugin 机制

Plugin 是 **可复用、可独立调用的 Python 模块/包**，用于向 aibes-agent 贡献：

- 新的 Tool
- 新的 Skill
- 新的子 Agent Profile

插件内部的业务逻辑**不依赖 aibes-agent**，可以直接当作普通 Python 代码导入和调用；只有注册到框架时才需要用到 `Tool`、`Skill` 等类型。

---

## 插件契约

一个插件模块至少需要满足以下**任意一种**约定：

### 1. 声明式：`__aibes_plugin__`

```python
# my_plugin/__init__.py
from aibes_agent.tools import Tool, ToolContext, ToolResult
from .core import fetch_weather  # 纯业务逻辑，可独立调用

class WeatherTool(Tool[WeatherInput]):
    name = "Weather"
    description = "Fetch weather for a city."
    input_model = WeatherInput

    async def call(self, input, context):
        return ToolResult.ok(fetch_weather(input.city))

__aibes_plugin__ = {
    "name": "weather",
    "version": "1.0.0",
    "tools": [WeatherTool],
}
```

### 2. 命令式：`setup(registry, config)`

```python
def setup(registry, config):
    registry.register(WeatherTool())
```

命令式方式适合需要访问运行时 `ToolRegistry` 和 `AgentConfig` 的场景。

---

## 发现来源

### 本地目录插件

默认搜索路径：`.aibes-agent/plugins`

```text
.aibes-agent/plugins/
└── weather/
    ├── plugin.yaml          # 可选
    ├── __init__.py          # 插件入口
    ├── core.py              # 独立业务逻辑
    └── tool.py              # Tool 包装
```

`plugin.yaml` 示例：

```yaml
name: weather
version: "1.0.0"
module: weather             # 可选；默认使用目录名
```

`plugin.yaml` 中的 `name` 和 `version` 会覆盖 `__aibes_plugin__` 里的值。

### pip 安装插件

第三方包通过 `pyproject.toml` 声明 entry point：

```toml
[project.entry-points."aibes_agent.plugins"]
my_plugin = "my_plugin.aibes_plugin"
```

然后在 `my_plugin/aibes_plugin.py` 中声明 `__aibes_plugin__` 或 `setup()`。

---

## 程序化加载

```python
from aibes_agent import PluginLoader, PluginBuilder
from aibes_agent.skills import SkillBuilder
from aibes_agent.tools import FileReadTool

plugins = PluginLoader().load_all()          # 本地 + entry points
builder = PluginBuilder(plugins)

tool_pool = {"FileRead": FileReadTool(), **builder.build_tools()}
skills = SkillLoader().load_all() + builder.build_skills()

agent_config, registry, profiles = SkillBuilder(skills, tool_pool).build()
profiles.update(builder.build_profiles())
builder.apply_setups(registry, agent_config)
```

---

## 配置

在 `aibes-agent.yaml` 或 `.aibes-agent/config.yaml` 中：

```yaml
plugins:
  auto_load: true
  entry_points: true
  paths:
    - ".aibes-agent/plugins"
    - "./third-party-plugins"
```

| 字段 | 说明 |
|------|------|
| `auto_load` | 是否自动加载插件（保留字段，当前默认启用） |
| `entry_points` | 是否读取 `aibes_agent.plugins` entry points |
| `paths` | 本地插件目录列表，后面的路径可覆盖前面的同名插件 |

---

## 示例

参考 `examples/greeting_plugin/`：

- `greeting.py`：纯函数，可独立运行。
- `tool.py`：Tool 包装。
- `__init__.py`：暴露 `__aibes_plugin__`。
- `demo.py`：演示独立调用与框架内调用。

运行示例：

```bash
python examples/greeting_plugin/greeting.py Alice
python examples/greeting_plugin/demo.py
```

---

## CLI 命令

```bash
# 列出已发现的插件
aibes-agent plugins list

# 同时列出每个插件提供的工具
aibes-agent plugins list --tools

# 指定配置文件
aibes-agent plugins list --config ./aibes-agent.yaml
```

---

## 设计原则

1. **独立可调用**：插件的核心逻辑应该是普通 Python 代码，不强制继承框架类型。
2. **失败隔离**：插件导入失败时记录 warning，不影响框架和其他插件加载。
3. **命名冲突**：同名插件/工具以**先发现者为准**；命令式 `setup` 中的注册仍遵循 `ToolRegistry` 自身的重复检测。
