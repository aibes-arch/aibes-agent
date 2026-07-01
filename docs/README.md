# aibes-agent 文档中心

> 本目录存�?`aibes-agent` 项目的设计文档、参考资料和开发指南�?
---

## 文档索引

### 设计文档

| 文档 | 说明 |
|-----|------|
| [架构设计](./ARCHITECTURE.md) | 总体架构、核心设计原则、执行流程、上下文与工具系统设�?|
| [模块设计](./MODULE_DESIGN.md) | 每个模块的接口、数据模型、开发指�?|
| [API 参考](./API_REFERENCE.md) | 核心类与函数的完整接口参�?|
| [版本演进计划](./ROADMAP.md) | 版本规划、功能路线图、长期目�?|

### v0.3.0 功能文档

| 文档 | 说明 |
|-----|------|
| [配置文件](./CONFIG.md) | `aibes-agent.yaml` 配置格式与加载机制 |
| [Skill 系统](./SKILLS.md) | 项目级 Skill 定义、加载与使用 |
| [MCP 支持](./MCP.md) | 接入外部 MCP 服务器 |
| [Web UI](./WEB_UI.md) | FastAPI + SSE Web 界面 |
| [会话持久化](./SESSION.md) | 保存与恢复对话状态 |

### 开发与实践

| 文档 | 说明 |
|-----|------|
| [快速开始](./QUICK_START.md) | 安装、配置、运行示例、编写第一�?Agent |
| [工具开发实战指南](./TOOL_DEVELOPMENT.md) | 如何�?aibes-agent 开发新工具，含完整示例 |
| [领域应用案例](./DOMAIN_CASE.md) | 代码审查 Agent 设计案例与钻井工程扩展方�?|
| [贡献指南](./CONTRIBUTING.md) | 开发环境、代码规范、PR 流程、测试与文档要求 |

### 参考资�?
| 文档 | 说明 |
|-----|------|
| [README 知识库索引](./references/README_知识库索�?md) | AI 编程与智能体相关参考资料索�?|
| [Claude Code 代码分析实战指南](./references/04_Claude_Code_代码分析实战指南.md) | Claude Code 的能力分析、实战用�?|
| [Claude Code 源码架构分析](./references/05_Claude_Code_源码架构分析.md) | 基于泄露源码�?Claude Code 架构解析 |
| [Agentic AI 架构设计深度分析](./references/20260519_Agentic_AI_架构设计深度分析.md) | Agentic AI 通用架构模式与设计方�?|

---

## 快速导�?
- **想理�?aibes-agent 怎么设计的？** �?[架构设计](./ARCHITECTURE.md)
- **想查看某个类/函数的用法？** �?[API 参考](./API_REFERENCE.md)
- **想了解未来会加什么功能？** �?[版本演进计划](./ROADMAP.md)
- **想快速跑起来�?* �?[快速开始](./QUICK_START.md)
- **想写新工具？** �?[工具开发实战指南](./TOOL_DEVELOPMENT.md)
- **想参与贡献？** �?[贡献指南](./CONTRIBUTING.md)

---

## 文档维护

- 新增/修改模块后，请同步更�?[模块设计](./MODULE_DESIGN.md) �?[API 参考](./API_REFERENCE.md)�?- 调整架构或接口时，请同步更新 [架构设计](./ARCHITECTURE.md)�?- 新增工具时，请同步更�?[工具开发实战指南](./TOOL_DEVELOPMENT.md) �?[模块设计](./MODULE_DESIGN.md)�?- 版本规划变更时，请同步更�?[版本演进计划](./ROADMAP.md)�?
---

*最后更新：2026-07-01*
