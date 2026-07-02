# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-07-02

### Added
- Domain toolkits as optional extras:
  - `aibes-agent[code_review]` with `GitDiffTool`, `LintTool`, `CoverageTool`
  - `aibes-agent[drilling]` with `ParseWitsmlTool`, `AnalyzeDrillingLogTool`, `ValidateFormulaTool`, `QueryKnowledgeBaseTool`
  - `aibes-agent[documents]` with `PdfExtractTool`, `MarkdownMergeTool`
- New skills:
  - `.aibes-agent/skills/drilling/skill.yaml`
  - `.aibes-agent/skills/document-processor/skill.yaml`
  - Enhanced `.aibes-agent/skills/code-review/skill.yaml` with lint/coverage profiles
- New example scripts:
  - `examples/code_review_agent.py`
  - `examples/drilling_analysis_agent.py`
  - `examples/document_processor_agent.py`
- New documentation:
  - `docs/DOCUMENTS.md`
  - Updated `docs/API_REFERENCE.md` and `docs/MODULE_DESIGN.md` with v0.4.0 sections
- Tests for all new domain tools in `tests/test_code_review_tools.py`, `tests/test_drilling_tools.py`, `tests/test_document_tools.py`

### Changed
- Bumped version from 0.3.0 to 0.4.0 across `pyproject.toml`, `README.md`, and all docs headers
- Updated `docs/ROADMAP.md` to mark v0.4.0 as completed
- `aibes_agent.web.server._built_in_tool_pool()` now includes all new domain tools

## [0.3.0] - 2026-07-01

### Added
- MCP client support (`aibes_agent.mcp`)
- FastAPI + SSE Web UI (`aibes_agent.web`)
- Skill system (`aibes_agent.skills`)
- Configuration file support (`aibes-agent.yaml`)
- Session persistence (`aibes_agent.core.session`)
- Model router (`aibes_agent.core.router`)
