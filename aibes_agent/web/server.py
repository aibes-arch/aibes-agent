"""FastAPI + SSE web UI for aibes_agent."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from loguru import logger

from aibes_agent.config import MinagentConfig
from aibes_agent.core.router import ModelRouter
from aibes_agent.core.session import FileSessionStore
from aibes_agent.skills import SkillBuilder, SkillLoader
from aibes_agent.planner import PlannerTool
from aibes_agent.tools import (
    AgentTool,
    AnalyzeDrillingLogTool,
    BashTool,
    CoverageTool,
    FileEditTool,
    FileReadTool,
    FileWriteTool,
    GitDiffTool,
    GlobTool,
    GrepTool,
    LintTool,
    MarkdownMergeTool,
    ParseWitsmlTool,
    PdfExtractTool,
    QueryKnowledgeBaseTool,
    TaskListTool,
    ValidateFormulaTool,
)
from aibes_agent.tools.base import Tool, ToolContext
from aibes_agent.web.runner import WebRunner

try:
    from aibes_agent.mcp.client import MCPClient
except ImportError:
    MCPClient = None  # type: ignore


HTML_PAGE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>aibes_agent Web UI</title>
    <style>
        body { font-family: sans-serif; margin: 2rem; }
        #log { border: 1px solid #ccc; padding: 1rem; height: 60vh; overflow-y: auto; }
        .event { margin-bottom: 0.5rem; font-family: monospace; white-space: pre-wrap; }
        .type { font-weight: bold; color: #3366cc; }
    </style>
</head>
<body>
    <h1>aibes_agent Web UI</h1>
    <p>Session: <code id="session-id"></code></p>
    <input id="task" type="text" size="80" placeholder="Enter a task...">
    <button id="send">Send</button>
    <div id="log"></div>
    <script>
        const sessionId = Math.random().toString(36).slice(2);
        document.getElementById('session-id').textContent = sessionId;
        const log = document.getElementById('log');
        const evtSource = new EventSource(`/api/events/${sessionId}`);
        evtSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            const div = document.createElement('div');
            div.className = 'event';
            div.innerHTML = `<span class="type">${data.type}</span> ${JSON.stringify(data).slice(0, 1000)}`;
            log.appendChild(div);
            log.scrollTop = log.scrollHeight;
        };
        document.getElementById('send').onclick = async () => {
            const task = document.getElementById('task').value;
            if (!task) return;
            await fetch(`/api/run/${sessionId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task}),
            });
        };
    </script>
</body>
</html>
""".strip()


class RunRequest(BaseModel):
    task: str


def _built_in_tool_pool() -> Dict[str, Tool]:
    return {
        "FileRead": FileReadTool(),
        "FileWrite": FileWriteTool(),
        "FileEdit": FileEditTool(),
        "Bash": BashTool(),
        "Grep": GrepTool(),
        "Glob": GlobTool(),
        "TaskList": TaskListTool(),
        "GitDiff": GitDiffTool(),
        "Lint": LintTool(),
        "Coverage": CoverageTool(),
        "ParseWitsml": ParseWitsmlTool(),
        "AnalyzeDrillingLog": AnalyzeDrillingLogTool(),
        "ValidateFormula": ValidateFormulaTool(),
        "QueryKnowledgeBase": QueryKnowledgeBaseTool(),
        "PdfExtract": PdfExtractTool(),
        "MarkdownMerge": MarkdownMergeTool(),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg: MinagentConfig = app.state.config
    tool_pool = _built_in_tool_pool()
    mcp_client: Optional[Any] = None
    mcp_tools: Dict[str, Tool] = {}

    if cfg.mcp_servers:
        if MCPClient is None:
            logger.warning("MCP servers configured but 'mcp' package is not installed")
        else:
            try:
                mcp_client = MCPClient(cfg.mcp_servers)
                await mcp_client.connect()
                mcp_tools = {name: tool for name, tool in (await mcp_client.get_tools()).items()}
                logger.info("Connected MCP servers: {}", list(cfg.mcp_servers.keys()))
            except Exception as exc:
                logger.warning("Failed to connect MCP servers: {}", exc)

    skills = SkillLoader(cfg.skills.paths).load_all() if cfg.skills.auto_load else []
    builder = SkillBuilder(skills, tool_pool, mcp_tools)
    agent_config, registry, profiles = builder.build()

    if profiles:
        registry.register(
            AgentTool(
                profiles=profiles,
                llm=cfg.to_llm_client(),
                tool_pool={**tool_pool, **mcp_tools},
                permission_engine=cfg.to_permission_engine(),
            )
        )

    router: Optional[ModelRouter] = None
    if cfg.router.default or cfg.router.rules:
        router = ModelRouter.from_config(cfg.router)

    session_store = cfg.to_session_store()
    tool_context = ToolContext(cwd=os.getcwd(), cache=cfg.to_tool_result_cache())

    registry.register(
        PlannerTool(
            llm=cfg.to_llm_client(),
            registry=registry,
            profiles=profiles,
            permission_engine=cfg.to_permission_engine(),
            tool_context=tool_context,
        )
    )

    app.state.runner = WebRunner(
        registry=registry,
        agent_config=agent_config,
        llm=cfg.to_llm_client(),
        permission_engine=cfg.to_permission_engine(),
        model_router=router,
        session_store=session_store,
        tool_context=tool_context,
    )
    logger.info("Web runner ready with {} tools", len(registry.list_tools()))
    yield
    if mcp_client is not None:
        await mcp_client.close()


def create_app(config: Optional[MinagentConfig] = None) -> FastAPI:
    app = FastAPI(title="aibes_agent", lifespan=lifespan)
    app.state.config = config or MinagentConfig.load()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return HTML_PAGE

    @app.get("/api/sessions")
    async def list_sessions() -> JSONResponse:
        sessions = await app.state.runner.session_store.list_sessions()
        return JSONResponse({"sessions": sessions})

    @app.get("/api/tools")
    async def list_tools() -> JSONResponse:
        return JSONResponse({"tools": app.state.runner.registry.list_tools()})

    @app.post("/api/run/{session_id}")
    async def run_task(session_id: str, request: RunRequest, background_tasks: BackgroundTasks):
        background_tasks.add_task(app.state.runner.submit, session_id, request.task)
        return {"session_id": session_id, "status": "started"}

    @app.get("/api/events/{session_id}")
    async def events(session_id: str, request: Request) -> EventSourceResponse:
        async def generator() -> AsyncIterator[Dict[str, Any]]:
            async for payload in app.state.runner.event_stream(session_id):
                yield payload

        return EventSourceResponse(generator())

    return app
