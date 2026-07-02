"""Drilling engineering domain tools for aibes-agent v0.4.0."""

from __future__ import annotations

import ast
import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from aibes_agent.tools.base import Tool, ToolContext, ToolResult


def _resolve_path(path: str, cwd: str) -> Path:
    raw_path = Path(path)
    if not raw_path.is_absolute():
        raw_path = Path(cwd) / raw_path
    return raw_path.expanduser().resolve()


class ParseWitsmlInput(BaseModel):
    file_path: str = Field(..., description="Path to the WITSML XML file")
    object_type: str = Field(
        "auto",
        description="WITSML object type to focus on: 'auto', 'well', 'wellbore', 'trajectory', 'log', 'formation'",
    )
    max_records: int = Field(50, description="Maximum number of data records to return")


class ParseWitsmlTool(Tool[ParseWitsmlInput]):
    name = "ParseWitsml"
    description = (
        "Parse a WITSML XML file and extract key drilling parameters such as well name, "
        "wellbore, trajectory, log curves, and formation tops. Requires the drilling extras."
    )
    input_model = ParseWitsmlInput

    def is_read_only(self, input: ParseWitsmlInput) -> bool:
        return True

    async def call(self, input: ParseWitsmlInput, context: ToolContext) -> ToolResult:
        try:
            from lxml import etree  # type: ignore[import-untyped]
        except ImportError:
            return ToolResult.fail(
                "lxml not found. Install the drilling extras: " "pip install aibes-agent[drilling]"
            )

        path = _resolve_path(input.file_path, context.cwd)
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")

        try:
            tree = etree.parse(str(path))
            root = tree.getroot()

            # Extract namespace if present
            ns_match = re.match(r"\{([^}]+)\}", root.tag)
            ns = {"witsml": ns_match.group(1)} if ns_match else {}

            result: Dict[str, Any] = {"file": str(path), "object_type": input.object_type}

            well_names = root.xpath("//witsml:well//witsml:name/text()", namespaces=ns)
            if not well_names:
                well_names = root.xpath("//witsml:name/text()", namespaces=ns)
            if well_names:
                result["well_names"] = list(dict.fromkeys(well_names))[: input.max_records]

            # Wellbore info
            wellbore_names = root.xpath("//witsml:wellbore//witsml:name/text()", namespaces=ns)
            if wellbore_names:
                result["wellbores"] = list(dict.fromkeys(wellbore_names))[: input.max_records]

            # Trajectory station info
            station_mds = root.xpath(
                "//witsml:trajectoryStation/witsml:md/witsml:value/text()", namespaces=ns
            )
            if station_mds:
                result["trajectory_mds"] = station_mds[: input.max_records]

            # Formation tops
            formation_names = root.xpath("//witsml:formation//witsml:name/text()", namespaces=ns)
            if formation_names:
                result["formations"] = list(dict.fromkeys(formation_names))[: input.max_records]

            # Log curve info
            curve_names = root.xpath("//witsml:logCurveInfo/witsml:mnemonic/text()", namespaces=ns)
            if not curve_names:
                curve_names = root.xpath("//witsml:mnemonic/text()", namespaces=ns)
            if curve_names:
                result["curve_mnemonics"] = list(dict.fromkeys(curve_names))[: input.max_records]

            # Measured depth values
            md_values = root.xpath("//witsml:md/text()", namespaces=ns)
            if md_values:
                result["measured_depths"] = md_values[: input.max_records]

            # Extract any data rows
            data_nodes = root.xpath("//witsml:data/text()", namespaces=ns)
            if data_nodes:
                result["data_records"] = data_nodes[: input.max_records]

            summary = json.dumps(result, ensure_ascii=False, indent=2)
            return ToolResult.ok(summary, records_found=len(data_nodes) if data_nodes else 0)
        except Exception as e:
            return ToolResult.fail(f"Failed to parse WITSML: {e}")


class AnalyzeDrillingLogInput(BaseModel):
    file_path: str = Field(..., description="Path to the drilling log CSV or JSON file")
    column: str = Field("ROP", description="Column/field to analyze (e.g. ROP, WOB, RPM)")
    threshold: Optional[float] = Field(
        None,
        description="Optional static threshold; if omitted, anomalies are detected via Z-score",
    )


class AnalyzeDrillingLogTool(Tool[AnalyzeDrillingLogInput]):
    name = "AnalyzeDrillingLog"
    description = (
        "Analyze a drilling log CSV or JSON file and detect anomalies in a selected column "
        "(e.g. ROP, WOB, RPM) using IQR or a static threshold."
    )
    input_model = AnalyzeDrillingLogInput

    def is_read_only(self, input: AnalyzeDrillingLogInput) -> bool:
        return True

    async def call(self, input: AnalyzeDrillingLogInput, context: ToolContext) -> ToolResult:
        path = _resolve_path(input.file_path, context.cwd)
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")

        try:
            if path.suffix.lower() == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict) and "data" in data:
                    rows = data["data"]
                else:
                    rows = [data]
            else:
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)

            if not rows:
                return ToolResult.fail("No data rows found in log file")

            values: List[float] = []
            for row in rows:
                if isinstance(row, dict) and input.column in row:
                    try:
                        values.append(float(row[input.column]))
                    except (ValueError, TypeError):
                        pass

            if len(values) < 2:
                return ToolResult.fail(f"Not enough numeric values for column '{input.column}'")

            sorted_values = sorted(values)
            n = len(sorted_values)
            q1_idx = (n - 1) * 0.25
            q3_idx = (n - 1) * 0.75
            q1_lower = int(math.floor(q1_idx))
            q1_upper = int(math.ceil(q1_idx))
            q3_lower = int(math.floor(q3_idx))
            q3_upper = int(math.ceil(q3_idx))
            q1 = (
                sorted_values[q1_lower]
                if q1_lower == q1_upper
                else sorted_values[q1_lower] * (q1_upper - q1_idx)
                + sorted_values[q1_upper] * (q1_idx - q1_lower)
            )
            q3 = (
                sorted_values[q3_lower]
                if q3_lower == q3_upper
                else sorted_values[q3_lower] * (q3_upper - q3_idx)
                + sorted_values[q3_upper] * (q3_idx - q3_lower)
            )
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(variance) if variance > 0 else 0.0

            anomalies: List[Dict[str, Any]] = []
            for idx, value in enumerate(values):
                flagged = False
                reason = ""
                if input.threshold is not None:
                    if value > input.threshold:
                        flagged = True
                        reason = f"exceeds threshold {input.threshold}"
                elif value < lower_bound or value > upper_bound:
                    flagged = True
                    if value < lower_bound:
                        reason = f"below IQR lower bound {lower_bound:.4f}"
                    else:
                        reason = f"above IQR upper bound {upper_bound:.4f}"

                if flagged:
                    anomalies.append(
                        {
                            "index": idx,
                            "value": value,
                            "reason": reason,
                        }
                    )

            result = {
                "column": input.column,
                "count": len(values),
                "mean": round(mean, 4),
                "std": round(std, 4),
                "q1": round(q1, 4),
                "q3": round(q3, 4),
                "iqr": round(iqr, 4),
                "lower_bound": round(lower_bound, 4),
                "upper_bound": round(upper_bound, 4),
                "anomalies": anomalies,
                "anomaly_count": len(anomalies),
            }
            return ToolResult.ok(json.dumps(result, ensure_ascii=False, indent=2), **result)
        except Exception as e:
            return ToolResult.fail(f"Failed to analyze drilling log: {e}")


class ValidateFormulaInput(BaseModel):
    formula: str = Field(
        "",
        description="Drilling formula expression to validate, e.g. 'ECD = rho * g * TVD / 1000'",
    )
    variables: Dict[str, float] = Field(
        default_factory=dict,
        description="Variable values to substitute when evaluating the formula",
    )
    expected_unit: str = Field("", description="Optional expected unit for the result")
    template: str = Field(
        "",
        description="Use a built-in formula template: 'ecd', 'annular_pressure', 'bit_hhp'",
    )
    convert_unit: str = Field(
        "",
        description="Convert result to another unit using built-in conversions: 'psi_to_pa', 'pa_to_psi', 'm_to_ft', 'ft_to_m', 'kg_m3_to_ppg', 'ppg_to_kg_m3'",
    )


class ValidateFormulaTool(Tool[ValidateFormulaInput]):
    name = "ValidateFormula"
    description = (
        "Validate a drilling hydraulics formula by parsing the expression and evaluating it "
        "with provided variable values. Supports basic math operators and functions."
    )
    input_model = ValidateFormulaInput

    def is_read_only(self, input: ValidateFormulaInput) -> bool:
        return True

    _FORMULAS = {
        "ecd": "rho * g * TVD / 1000",
        "annular_pressure": "rho * g * TVD",
        "bit_hhp": "delta_p * q / 1714",
    }

    _CONVERSIONS = {
        "psi_to_pa": 6894.757,
        "pa_to_psi": 1 / 6894.757,
        "m_to_ft": 3.28084,
        "ft_to_m": 1 / 3.28084,
        "kg_m3_to_ppg": 0.008345,
        "ppg_to_kg_m3": 1 / 0.008345,
    }

    async def call(self, input: ValidateFormulaInput, context: ToolContext) -> ToolResult:
        formula = input.formula.strip()

        if input.template:
            template_expr = self._FORMULAS.get(input.template.lower())
            if template_expr is None:
                return ToolResult.fail(f"Unknown template: {input.template}")
            formula = template_expr

        # Support formulas written as "LHS = RHS" by extracting RHS
        if "=" in formula:
            _, _, formula = formula.partition("=")
            formula = formula.strip()

        if not formula:
            return ToolResult.fail("No formula expression found")

        allowed_names = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
        }

        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError as e:
            return ToolResult.fail(f"Formula syntax error: {e}")

        # Validate only safe nodes
        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.Expression,
                    ast.BinOp,
                    ast.UnaryOp,
                    ast.Call,
                    ast.Name,
                    ast.Constant,
                    ast.Load,
                    ast.Add,
                    ast.Sub,
                    ast.Mult,
                    ast.Div,
                    ast.Pow,
                    ast.USub,
                    ast.UAdd,
                ),
            ):
                continue
            return ToolResult.fail(f"Unsupported expression node: {type(node).__name__}")

        # Collect referenced names
        referenced: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)

        missing = [
            name for name in referenced if name not in allowed_names and name not in input.variables
        ]
        if missing:
            return ToolResult.fail(
                f"Missing variable values: {', '.join(missing)}",
                content=f"Provide values for: {missing}",
            )

        eval_globals = {**allowed_names, **input.variables}
        try:
            result = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, eval_globals)
        except Exception as e:
            return ToolResult.fail(f"Formula evaluation failed: {e}")

        converted = None
        conversion_factor = None
        if input.convert_unit:
            conversion_factor = self._CONVERSIONS.get(input.convert_unit.lower())
            if conversion_factor is None:
                return ToolResult.fail(f"Unknown conversion: {input.convert_unit}")
            converted = result * conversion_factor

        response: Dict[str, Any] = {
            "formula": input.formula,
            "template": input.template or None,
            "expression": formula,
            "result": result,
            "expected_unit": input.expected_unit or "unspecified",
        }
        if converted is not None:
            response["converted"] = converted
            response["conversion_factor"] = conversion_factor

        return ToolResult.ok(json.dumps(response, ensure_ascii=False, indent=2), **response)


class QueryKnowledgeBaseInput(BaseModel):
    query: str = Field(
        ..., description="Keywords or question to search in the drilling knowledge base"
    )
    kb_path: str = Field(
        "",
        description="Path to a YAML or JSON knowledge base file. If empty, uses the built-in minimal KB.",
    )
    top_k: int = Field(5, description="Maximum number of entries to return")


class QueryKnowledgeBaseTool(Tool[QueryKnowledgeBaseInput]):
    name = "QueryKnowledgeBase"
    description = (
        "Query a drilling knowledge base for regulations, best practices, or incident cases. "
        "Supports a built-in minimal KB or a user-provided YAML/JSON file."
    )
    input_model = QueryKnowledgeBaseInput

    def is_read_only(self, input: QueryKnowledgeBaseInput) -> bool:
        return True

    @staticmethod
    def _built_in_kb() -> List[Dict[str, str]]:
        return [
            {
                "title": "ECD 计算",
                "content": "当量循环密度 ECD = (P_bottom / (g * TVD)) * 1000，单位 kg/m3。需校核井眼清洁和当量密度是否超过破裂压力。",
            },
            {
                "title": "井漏事故案例",
                "content": "发现返出流量异常降低、液面下降时，立即停泵关井，记录漏失量，评估是否进行堵漏作业。",
            },
            {
                "title": "卡钻预防",
                "content": "保持合理钻井液润滑性，控制井眼轨迹狗腿严重度，定期短起下钻破坏岩屑床。",
            },
            {
                "title": "SY/T 标准",
                "content": "钻井液性能测试应参考 SY/T 5621 等标准，包括密度、粘度、滤失量等关键参数。",
            },
        ]

    def _load_kb(self, path: Optional[Path]) -> List[Dict[str, str]]:
        if path is None or not path.exists():
            return self._built_in_kb()

        suffix = path.suffix.lower()
        try:
            with open(path, "r", encoding="utf-8") as f:
                if suffix == ".json":
                    data = json.load(f)
                else:
                    import yaml

                    data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load KB: {e}")

        if isinstance(data, list):
            return [
                {"title": str(item.get("title", "")), "content": str(item.get("content", ""))}
                for item in data
            ]
        if isinstance(data, dict) and "entries" in data:
            return [
                {"title": str(item.get("title", "")), "content": str(item.get("content", ""))}
                for item in data["entries"]
            ]
        return self._built_in_kb()

    async def call(self, input: QueryKnowledgeBaseInput, context: ToolContext) -> ToolResult:
        try:
            kb_path: Optional[Path] = None
            if input.kb_path:
                kb_path = _resolve_path(input.kb_path, context.cwd)

            kb = self._load_kb(kb_path)
            query_terms = [term.lower() for term in input.query.split() if term]

            scored: List[tuple] = []
            for entry in kb:
                text = f"{entry['title']} {entry['content']}".lower()
                score = sum(1 for term in query_terms if term in text)
                if score > 0:
                    scored.append((score, entry))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = [entry for _, entry in scored[: input.top_k]]

            if not top:
                return ToolResult.ok(
                    json.dumps(
                        {"query": input.query, "results": kb[: input.top_k]},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    fallback=True,
                )

            return ToolResult.ok(
                json.dumps({"query": input.query, "results": top}, ensure_ascii=False, indent=2),
                result_count=len(top),
            )
        except Exception as e:
            return ToolResult.fail(f"Knowledge base query failed: {e}")
