# aibes-agent 贡献指南

> **版本**: 0.1.0  
> **最后更�?*: 2026-07-01

感谢你对 `aibes-agent` 的关注！本指南帮助你快速参与项目贡献�?
---

## 目录

- [1. 开发环境搭建](#1-开发环境搭�?
- [2. 代码规范](#2-代码规范)
- [3. 提交 Pull Request 流程](#3-提交-pull-request-流程)
- [4. 测试要求](#4-测试要求)
- [5. 文档要求](#5-文档要求)
- [6. 新增工具 checklist](#6-新增工具-checklist)
- [7. 报告问题](#7-报告问题)

---

## 1. 开发环境搭�?
### 1.1 克隆仓库

```bash
git clone <repository-url>
cd aibes-agent
```

### 1.2 创建虚拟环境

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 1.3 安装开发依�?
```bash
pip install -e ".[dev,cli]"
```

这会安装�?
- `pytest` / `pytest-asyncio`
- `black` / `mypy`
- `typer` / `rich`

---

## 2. 代码规范

### 2.1 格式�?
使用 `black`�?
```bash
black aibes-agent tests examples
```

项目配置（`pyproject.toml`）：

```toml
[tool.black]
line-length = 100
target-version = ['py311']
```

### 2.2 类型检�?
```bash
mypy aibes-agent
```

### 2.3 导入顺序

- 标准�?- 第三方库
- 项目内部模块

示例�?
```python
import asyncio
from typing import Any, Dict

import httpx
from pydantic import BaseModel

from aibes_agent.tools.base import Tool, ToolContext, ToolResult
```

### 2.4 命名规范

- 类名：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 工具名：`PascalCase`（如 `FileRead`、`Grep`�?
### 2.5 异步代码

- 工具 `call()` 必须�?`async def`�?- IO 操作使用 `asyncio` 原生接口�?`httpx.AsyncClient`�?
---

## 3. 提交 Pull Request 流程

1. **Fork 仓库** 或创建新分支�?
```bash
git checkout -b feature/my-feature
```

2. **编写代码** 并添加测试�?3. **运行测试和检�?*�?
```bash
black --check aibes-agent tests examples
mypy aibes-agent
pytest tests/ -q
```

4. **更新文档**：如果修改了架构、接口或新增工具，同步更�?`docs/`�?5. **提交 commit**：commit message 用中文或英文均可，要求清晰描述改动�?
```bash
git commit -m "feat: add JsonReadTool"
```

6. **推送并创建 PR**�?
---

## 4. 测试要求

### 4.1 运行测试

```bash
pytest tests/ -q
```

### 4.2 新增测试

- 每个新工具必须有单元测试�?- 覆盖正常路径和错误路径�?- 异步测试使用 `@pytest.mark.asyncio`�?
示例�?
```python
import pytest
from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.fs import FileReadTool, FileWriteTool


@pytest.mark.asyncio
async def test_file_read_write(tmp_path):
    read_tool = FileReadTool()
    write_tool = FileWriteTool()
    ctx = ToolContext(cwd=str(tmp_path))

    test_file = tmp_path / "test.txt"
    await write_tool.call(
        write_tool.input_model(file_path=str(test_file), content="hello"),
        ctx,
    )
    result = await read_tool.call(
        read_tool.input_model(file_path=str(test_file)),
        ctx,
    )
    assert "hello" in result.content
```

### 4.3 避免外部依赖

- 测试不应依赖真实�?LLM 服务�?- 测试不应修改用户真实文件系统，优先使�?`tmp_path`�?
---

## 5. 文档要求

### 5.1 必须更新的文�?
| 改动类型 | 需要更新的文档 |
|---------|--------------|
| 新增/修改核心类接�?| [API 参考](./API_REFERENCE.md)、[模块设计](./MODULE_DESIGN.md) |
| 新增工具 | [模块设计](./MODULE_DESIGN.md)、[API 参考](./API_REFERENCE.md)、[工具开发实战指南](./TOOL_DEVELOPMENT.md) |
| 架构调整 | [架构设计](./ARCHITECTURE.md) |
| 版本规划 | [版本演进计划](./ROADMAP.md) |
| 新增使用方式 | [快速开始](./QUICK_START.md) |

### 5.2 文档格式

- 使用 Markdown�?- 代码块标注语言�?- 表格用于对比和清单�?- 相对路径链接到项目内其他文档�?
---

## 6. 新增工具 Checklist

如果你想�?`aibes-agent` 贡献一个新工具，请按以下清单检查：

- [ ] 继承 `Tool` 并实�?`call()`
- [ ] 定义清晰�?`name`、`description`、`input_model`
- [ ] 实现 `is_read_only()`（影响并发策略）
- [ ] 完善的错误处理，返回 `ToolResult.fail(...)`
- [ ] 控制输出长度，避免过大内容冲击上下文
- [ ] 添加�?`aibes-agent/tools/__init__.py`
- [ ] 添加�?`aibes-agent/__init__.py`（可选）
- [ ] �?`tests/` 中添加单元测�?- [ ] 更新文档

---

## 7. 报告问题

如果你发�?bug 或有功能建议，请提供�?
1. **复现步骤**
2. **环境信息**：Python 版本、操作系统、`pip list` 中相关包版本
3. **最小可复现代码**
4. **期望行为** �?**实际行为**

---

再次感谢你的贡献�?
