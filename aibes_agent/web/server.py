"""FastAPI + SSE web UI for aibes_agent."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
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
from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.tools.base import Tool, ToolContext
from aibes_agent.web.openai_compat import (
    ChatCompletionRequest,
    DONE_SENTINEL,
    make_chat_completion_response,
    make_content_chunk,
    make_stop_chunk,
    _completion_id,
    _now,
)
from aibes_agent.web.runner import WebRunner

try:
    from aibes_agent.mcp.client import MCPClient
except ImportError:
    MCPClient = None  # type: ignore


HTML_PAGE = """
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>aibes_agent · Agent Chat</title>
    <style>
        :root {
            --bg: #f5f6f8;
            --panel: #ffffff;
            --user-bubble: #e3f2fd;
            --assistant-bubble: #ffffff;
            --tool-bubble: #fff8e1;
            --tool-result-bubble: #e8f5e9;
            --error-bubble: #ffebee;
            --system-bubble: #f3e5f5;
            --text: #222;
            --muted: #666;
            --border: #ddd;
            --accent: #3366cc;
            --radius: 14px;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: var(--panel);
            border-bottom: 1px solid var(--border);
            padding: 0.75rem 1.25rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            flex-shrink: 0;
        }
        header h1 { font-size: 1.1rem; margin: 0; color: var(--accent); }
        header .working {
            font-size: 0.75rem;
            color: #2e7d32;
            margin-left: 0.5rem;
            font-weight: 500;
        }
        header .meta { font-size: 0.8rem; color: var(--muted); }
        header button {
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.35rem 0.75rem;
            cursor: pointer;
            font-size: 0.85rem;
        }
        header button:hover { background: var(--bg); }
        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        .empty-state {
            text-align: center;
            color: var(--muted);
            margin-top: 20vh;
        }
        .message-row { display: flex; }
        .message-row.user { justify-content: flex-end; }
        .message-row.assistant { justify-content: flex-start; }
        .message-row.system { justify-content: center; }
        .bubble {
            max-width: 80%;
            padding: 0.85rem 1rem;
            border-radius: var(--radius);
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            line-height: 1.55;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .bubble.user { background: var(--user-bubble); border-bottom-right-radius: 4px; }
        .bubble.assistant { background: var(--assistant-bubble); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
        .bubble.error { background: var(--error-bubble); border: 1px solid #ef9a9a; }
        .bubble.system { background: var(--system-bubble); font-size: 0.8rem; color: var(--muted); padding: 0.4rem 0.8rem; }
        .bubble .label {
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--muted);
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .thinking {
            display: flex;
            align-items: center;
            gap: 0.35rem;
            color: var(--muted);
            font-size: 0.85rem;
            margin-top: 0.5rem;
        }
        .dot {
            width: 6px; height: 6px;
            background: var(--accent);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        .tool-call, .tool-result {
            margin-top: 0.5rem;
            padding: 0.65rem 0.85rem;
            border-radius: 10px;
            font-size: 0.85rem;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }
        .tool-call { background: var(--tool-bubble); border: 1px solid #ffe082; }
        .tool-result { background: var(--tool-result-bubble); border: 1px solid #a5d6a7; }
        .tool-call summary, .tool-result summary {
            cursor: pointer;
            font-weight: 600;
            list-style: none;
        }
        .tool-call summary::-webkit-details-marker, .tool-result summary::-webkit-details-marker { display: none; }
        .tool-call .args, .tool-result .content {
            margin-top: 0.4rem;
            padding-top: 0.4rem;
            border-top: 1px dashed rgba(0,0,0,0.1);
            white-space: pre-wrap;
            color: var(--text);
        }
        .input-area {
            background: var(--panel);
            border-top: 1px solid var(--border);
            padding: 0.85rem 1.25rem;
            display: flex;
            gap: 0.6rem;
            flex-shrink: 0;
        }
        #task {
            flex: 1;
            padding: 0.7rem 1rem;
            border: 1px solid var(--border);
            border-radius: 10px;
            font-size: 0.95rem;
            outline: none;
        }
        #task:focus { border-color: var(--accent); }
        #send {
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0 1.25rem;
            font-size: 0.95rem;
            cursor: pointer;
        }
        #send:disabled { opacity: 0.6; cursor: not-allowed; }
        #send:hover:not(:disabled) { background: #254e9e; }
        code {
            background: rgba(0,0,0,0.04);
            padding: 0.1rem 0.35rem;
            border-radius: 4px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <header>
        <h1>aibes_agent <span id="working" class="working" style="display:none;">● 运行中</span></h1>
        <div class="meta">Session: <code id="session-id"></code></div>
        <button id="clear">清空会话</button>
    </header>
    <div id="messages">
        <div class="empty-state">在下方输入任务，开始与 Agent 对话</div>
    </div>
    <div class="input-area">
        <input id="task" type="text" placeholder="输入任务，按 Enter 发送..." autocomplete="off">
        <button id="send">发送</button>
    </div>
    <script>
        const sessionId = Math.random().toString(36).slice(2);
        document.getElementById('session-id').textContent = sessionId;
        const messagesEl = document.getElementById('messages');
        const taskInput = document.getElementById('task');
        const sendBtn = document.getElementById('send');
        const clearBtn = document.getElementById('clear');

        let activeTasks = 0;
        let currentAssistantBubble = null;
        let currentAssistantContent = null;
        let currentAssistantTools = null;
        let thinkingEl = null;

        const evtSource = new EventSource(`/api/events/${sessionId}`);
        const workingEl = document.getElementById('working');

        function removeEmptyState() {
            const empty = messagesEl.querySelector('.empty-state');
            if (empty) empty.remove();
        }

        function scrollToBottom() {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function createRow(className) {
            removeEmptyState();
            const row = document.createElement('div');
            row.className = `message-row ${className}`;
            messagesEl.appendChild(row);
            return row;
        }

        function createBubble(className, label) {
            const row = createRow(className);
            const bubble = document.createElement('div');
            bubble.className = `bubble ${className}`;
            if (label) {
                const labelEl = document.createElement('div');
                labelEl.className = 'label';
                labelEl.textContent = label;
                bubble.appendChild(labelEl);
            }
            row.appendChild(bubble);
            return bubble;
        }

        function addUserMessage(content) {
            const bubble = createBubble('user', '你');
            bubble.appendChild(document.createTextNode(content));
            scrollToBottom();
        }

        function ensureAssistantBubble() {
            if (currentAssistantBubble) return currentAssistantBubble;
            currentAssistantBubble = createBubble('assistant', 'Agent');
            currentAssistantContent = document.createElement('div');
            currentAssistantContent.className = 'assistant-content';
            currentAssistantTools = document.createElement('div');
            currentAssistantTools.className = 'assistant-tools';
            currentAssistantBubble.appendChild(currentAssistantContent);
            currentAssistantBubble.appendChild(currentAssistantTools);

            thinkingEl = document.createElement('div');
            thinkingEl.className = 'thinking';
            thinkingEl.innerHTML = '<span>思考中</span><span class="dot"></span><span class="dot"></span><span class="dot"></span>';
            currentAssistantBubble.appendChild(thinkingEl);
            scrollToBottom();
            return currentAssistantBubble;
        }

        function finishAssistant() {
            if (thinkingEl) {
                thinkingEl.remove();
                thinkingEl = null;
            }
            currentAssistantBubble = null;
            currentAssistantContent = null;
            currentAssistantTools = null;
            scrollToBottom();
        }

        function formatArgs(args) {
            try {
                return JSON.stringify(typeof args === 'string' ? JSON.parse(args) : args, null, 2);
            } catch {
                return String(args);
            }
        }

        function addToolCall(toolCall) {
            const bubble = ensureAssistantBubble();
            const fn = toolCall.function || {};
            const details = document.createElement('details');
            details.className = 'tool-call';
            details.open = true;
            const summary = document.createElement('summary');
            summary.textContent = `🔧 调用工具: ${fn.name || 'unknown'}`;
            const args = document.createElement('div');
            args.className = 'args';
            args.textContent = formatArgs(fn.arguments);
            details.appendChild(summary);
            details.appendChild(args);
            currentAssistantTools.appendChild(details);
            scrollToBottom();
        }

        function addToolResult(result) {
            const bubble = ensureAssistantBubble();
            const details = document.createElement('details');
            details.className = 'tool-result';
            details.open = false;
            const summary = document.createElement('summary');
            summary.textContent = `✅ 工具结果: ${result.name || 'unknown'}`;
            const content = document.createElement('div');
            content.className = 'content';
            content.textContent = result.content || '';
            details.appendChild(summary);
            details.appendChild(content);
            currentAssistantTools.appendChild(details);
            scrollToBottom();
        }

        function addSystemNotice(text) {
            const bubble = createBubble('system', '');
            bubble.textContent = text;
            scrollToBottom();
        }

        function addError(message) {
            finishAssistant();
            const bubble = createBubble('error', '错误');
            bubble.appendChild(document.createTextNode(message));
            scrollToBottom();
        }

        function updateActiveTasks(delta) {
            activeTasks = Math.max(0, activeTasks + delta);
            workingEl.style.display = activeTasks > 0 ? 'inline' : 'none';
        }

        evtSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            switch (data.type) {
                case 'user_task':
                    // user message is already added on send
                    break;
                case 'llm_response':
                    ensureAssistantBubble();
                    if (data.content) {
                        currentAssistantContent.textContent = data.content;
                    }
                    if (data.tool_calls && data.tool_calls.length) {
                        data.tool_calls.forEach(addToolCall);
                    }
                    scrollToBottom();
                    break;
                case 'tool_result':
                    addToolResult(data);
                    break;
                case 'final':
                    ensureAssistantBubble();
                    if (data.content) {
                        currentAssistantContent.textContent = data.content;
                    }
                    finishAssistant();
                    updateActiveTasks(-1);
                    break;
                case 'error':
                    addError(data.message || 'Unknown error');
                    updateActiveTasks(-1);
                    break;
                case 'compact':
                    addSystemNotice('💾 上下文已压缩');
                    break;
                case 'permission_denied':
                    addSystemNotice('⛔ 工具调用被拒绝');
                    break;
                case 'stats':
                    // silently ignore stats
                    break;
            }
        };

        evtSource.onerror = () => {
            addError('SSE 连接中断');
            updateActiveTasks(-activeTasks);
        };

        async function sendTask() {
            const task = taskInput.value.trim();
            if (!task) return;
            addUserMessage(task);
            taskInput.value = '';
            updateActiveTasks(1);
            try {
                await fetch(`/api/run/${sessionId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({task}),
                });
            } catch (err) {
                addError('发送失败: ' + err.message);
                updateActiveTasks(-1);
            }
        }

        sendBtn.onclick = sendTask;
        taskInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendTask();
        });

        clearBtn.onclick = () => {
            messagesEl.innerHTML = '<div class="empty-state">在下方输入任务，开始与 Agent 对话</div>';
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

    @app.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest):
        runner = app.state.runner

        if not request.messages:
            raise HTTPException(status_code=400, detail="messages cannot be empty")

        task = request.messages[-1].content
        session_id = request.session_id or uuid.uuid4().hex
        completion_id = _completion_id()
        created = _now()
        model = request.model or runner.llm.model or "aibes-agent"

        config = AgentConfig(
            system_prompt=runner.agent_config.system_prompt,
            max_turns=runner.agent_config.max_turns,
            max_tokens_per_turn=request.max_tokens or runner.agent_config.max_tokens_per_turn,
            temperature=request.temperature if request.temperature is not None else runner.agent_config.temperature,
            auto_compact=runner.agent_config.auto_compact,
        )

        tool_context = ToolContext(
            cwd=runner.tool_context.cwd,
            env=dict(runner.tool_context.env),
            metadata={},
            cache=runner.tool_context.cache,
        )

        async def _agent_events():
            agent = AgentLoop(
                llm=runner.llm,
                registry=runner.registry,
                config=config,
                permission_engine=runner.permission_engine,
                tool_context=tool_context,
                model_router=runner.model_router,
                session_store=runner.session_store,
            )
            async for event in agent.run(task, session_id=session_id):
                yield event

        if request.stream:
            async def _stream_chunks() -> AsyncIterator[Dict[str, Any]]:
                async for event in _agent_events():
                    if event.get("type") == "final":
                        content = event.get("content") or ""
                        stats = event.get("stats") or {}
                        usage = {
                            "prompt_tokens": stats.get("total_prompt_tokens", 0),
                            "completion_tokens": stats.get("total_completion_tokens", 0),
                            "total_tokens": stats.get("total_tokens", 0),
                        }
                        yield make_content_chunk(completion_id, created, model, content)
                        yield make_stop_chunk(completion_id, created, model, usage)
                        yield {"data": DONE_SENTINEL}
                        return
                    if event.get("type") == "error":
                        yield make_stop_chunk(completion_id, created, model)
                        yield {"data": DONE_SENTINEL}
                        return

            return EventSourceResponse(_stream_chunks())

        # Non-streaming path
        final_content = ""
        final_stats: Dict[str, Any] = {}
        async for event in _agent_events():
            if event.get("type") == "final":
                final_content = event.get("content") or ""
                final_stats = event.get("stats") or {}
                break
            if event.get("type") == "error":
                raise HTTPException(status_code=500, detail=event.get("message", "Agent run failed"))

        usage = {
            "prompt_tokens": final_stats.get("total_prompt_tokens", 0),
            "completion_tokens": final_stats.get("total_completion_tokens", 0),
            "total_tokens": final_stats.get("total_tokens", 0),
        }
        response = make_chat_completion_response(
            completion_id=completion_id,
            created=created,
            model=model,
            content=final_content,
            usage=usage,
        )
        return JSONResponse(response.model_dump())

    return app
