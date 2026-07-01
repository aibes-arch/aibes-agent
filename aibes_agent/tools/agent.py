"""子 Agent 工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from aibes_agent.core.llm import LLMClient
from aibes_agent.permissions.engine import PermissionEngine
from aibes_agent.tools.base import Tool, ToolContext, ToolResult

if TYPE_CHECKING:
    from aibes_agent.core.engine import AgentConfig, AgentLoop
    from aibes_agent.core.tool_registry import ToolRegistry


@dataclass
class AgentProfile:
    """子 Agent 配置。"""

    name: str
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    max_turns: int = 10
    model: Optional[str] = None


class AgentInput(BaseModel):
    """AgentTool 输入。"""

    task: str = Field(..., description="Sub-task to delegate to the sub-agent")
    agent_profile: str = Field(
        "default",
        description="Name of the agent profile to use",
    )


class AgentTool(Tool[AgentInput]):
    """把子任务委派给另一个具有独立 prompt 和工具集的子 Agent。"""

    name = "Agent"
    description = (
        "Delegate a sub-task to a specialized sub-agent with its own "
        "system prompt and tool set. Returns the sub-agent's final answer."
    )
    input_model = AgentInput

    def __init__(
        self,
        profiles: Dict[str, AgentProfile],
        llm: LLMClient,
        tool_pool: Dict[str, Tool],
        permission_engine: Optional[PermissionEngine] = None,
    ) -> None:
        super().__init__()
        if "default" not in profiles:
            raise ValueError("AgentTool requires a 'default' profile")
        self.profiles = profiles
        self.llm = llm
        self.tool_pool = tool_pool
        self.permission_engine = permission_engine

    def is_read_only(self, input: AgentInput) -> bool:
        return False

    def _build_registry(self, profile: AgentProfile) -> "ToolRegistry":
        """根据 profile 挑选工具构建注册表。"""
        from aibes_agent.core.tool_registry import ToolRegistry

        registry = ToolRegistry()
        tool_names = profile.tools or list(self.tool_pool.keys())
        for name in tool_names:
            tool = self.tool_pool.get(name)
            if tool is None:
                raise ValueError(f"Tool '{name}' not found in tool pool")
            registry.register(tool)
        return registry

    async def call(self, input: AgentInput, context: ToolContext) -> ToolResult:
        from aibes_agent.core.engine import AgentConfig, AgentLoop

        profile = self.profiles.get(input.agent_profile)
        if profile is None:
            return ToolResult.fail(f"Agent profile '{input.agent_profile}' not found")

        registry = self._build_registry(profile)

        # 复用父 Agent 的 endpoint/key/timeout，模型可被 profile 覆盖
        if profile.model and profile.model != self.llm.model:
            sub_llm = LLMClient(
                base_url=self.llm.base_url,
                api_key=self.llm.api_key,
                model=profile.model,
                timeout=self.llm.timeout,
            )
        else:
            sub_llm = self.llm

        config = AgentConfig(
            system_prompt=profile.system_prompt,
            max_turns=profile.max_turns,
        )

        agent = AgentLoop(
            llm=sub_llm,
            registry=registry,
            config=config,
            permission_engine=self.permission_engine,
            tool_context=context,
        )

        final_content = ""
        tool_calls_count = 0
        turn_count = 0
        try:
            async for event in agent.run(input.task):
                if event["type"] == "llm_response":
                    turn_count = event["turn"]
                    if event.get("tool_calls"):
                        tool_calls_count += len(event["tool_calls"])
                elif event["type"] == "final":
                    final_content = event["content"]
        except Exception as exc:
            return ToolResult.fail(f"Sub-agent failed: {exc}")

        return ToolResult.ok(
            final_content,
            agent_profile=profile.name,
            turns=turn_count,
            tool_calls=tool_calls_count,
        )
