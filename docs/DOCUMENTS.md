# aibes-agent 文档处理

> **版本**: 0.4.0  
> **最后更新**: 2026-07-02  
> **关联文档**: [API 参考](./API_REFERENCE.md)、[模块设计](./MODULE_DESIGN.md)

---

## 1. 功能概述

v0.4.0 引入文档处理领域工具，支持从 PDF 提取文本以及合并多个 Markdown 文件。

## 2. 可选依赖

```bash
pip install aibes-agent[documents]
```

该 extras 会安装 `pymupdf`。

## 3. 工具说明

### `PdfExtractTool`

从 PDF 文件中提取文本内容。

```python
from aibes_agent import PdfExtractTool

tool = PdfExtractTool()
result = await tool.call(tool.input_model(file_path="report.pdf"), ctx)
print(result.content)
```

输入参数：
- `file_path`: PDF 文件路径
- `pages`: 可选，指定 1-based 页码列表
- `max_chars`: 最大返回字符数，默认 20000

### `MarkdownMergeTool`

合并多个 Markdown 文件。

```python
from aibes_agent import MarkdownMergeTool

tool = MarkdownMergeTool()
result = await tool.call(tool.input_model(paths=["docs/*.md"], add_toc=True), ctx)
print(result.content)
```

输入参数：
- `paths`: 文件路径、glob 模式或目录列表
- `output_path`: 可选，输出文件路径
- `add_toc`: 是否根据 H1/H2 生成目录

## 4. Skill

项目已内置 `.aibes-agent/skills/document-processor/skill.yaml`，可直接使用：

```bash
aibes-agent run examples/document_processor_agent.py --skill document-processor
```

## 5. 示例

见 `examples/document_processor_agent.py`。

---

*最后更新：2026-07-02*
