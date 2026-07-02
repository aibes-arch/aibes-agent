import importlib.util
import json
from pathlib import Path

import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.drilling import (
    AnalyzeDrillingLogTool,
    ParseWitsmlTool,
    QueryKnowledgeBaseTool,
    ValidateFormulaTool,
)


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_analyze_drilling_log_csv(tmp_path, ctx):
    log_file = tmp_path / "log.csv"
    log_file.write_text(
        "depth,ROP,WOB\n"
        "100,10.0,20\n"
        "200,10.2,21\n"
        "300,10.5,22\n"
        "400,10.8,21\n"
        "500,11.0,20\n"
        "600,50.0,22\n",
        encoding="utf-8",
    )

    tool = AnalyzeDrillingLogTool()
    result = await tool.call(tool.input_model(file_path=str(log_file), column="ROP"), ctx)
    assert result.success
    data = json.loads(result.content)
    assert data["column"] == "ROP"
    assert data["anomaly_count"] >= 1


@pytest.mark.asyncio
async def test_analyze_drilling_log_json(tmp_path, ctx):
    log_file = tmp_path / "log.json"
    log_file.write_text(
        json.dumps(
            [
                {"depth": 100, "ROP": 10.0, "WOB": 20},
                {"depth": 200, "ROP": 10.2, "WOB": 21},
                {"depth": 300, "ROP": 10.5, "WOB": 22},
                {"depth": 400, "ROP": 10.8, "WOB": 21},
                {"depth": 500, "ROP": 11.0, "WOB": 20},
                {"depth": 600, "ROP": 50.0, "WOB": 22},
            ]
        ),
        encoding="utf-8",
    )

    tool = AnalyzeDrillingLogTool()
    result = await tool.call(tool.input_model(file_path=str(log_file), column="ROP"), ctx)
    assert result.success
    data = json.loads(result.content)
    assert data["anomaly_count"] >= 1


@pytest.mark.asyncio
async def test_validate_formula_simple(ctx):
    tool = ValidateFormulaTool()
    result = await tool.call(
        tool.input_model(
            formula="ECD = rho * g * TVD / 1000", variables={"rho": 1200, "g": 9.81, "TVD": 2000}
        ),
        ctx,
    )
    assert result.success
    data = json.loads(result.content)
    assert data["result"] == pytest.approx(1200 * 9.81 * 2000 / 1000)


@pytest.mark.asyncio
async def test_validate_formula_missing_variable(ctx):
    tool = ValidateFormulaTool()
    result = await tool.call(
        tool.input_model(formula="ECD = rho * g * TVD / 1000", variables={"rho": 1200, "g": 9.81}),
        ctx,
    )
    assert not result.success
    assert "TVD" in result.error


@pytest.mark.asyncio
async def test_query_knowledge_base_builtin(ctx):
    tool = QueryKnowledgeBaseTool()
    result = await tool.call(tool.input_model(query="ECD"), ctx)
    assert result.success
    assert "ECD" in result.content


@pytest.mark.skipif(
    importlib.util.find_spec("lxml") is None,
    reason="lxml not installed",
)
@pytest.mark.asyncio
async def test_parse_witsml(tmp_path, ctx):
    tool = ParseWitsmlTool()
    witsml = tmp_path / "well.xml"
    witsml.write_text(
        """<?xml version="1.0"?>
<wells xmlns="http://www.witsml.org/schemas/1series">
  <well>
    <name>Demo Well</name>
  </well>
</wells>
""",
        encoding="utf-8",
    )
    result = await tool.call(tool.input_model(file_path=str(witsml)), ctx)
    assert result.success
    assert "Demo Well" in result.content
