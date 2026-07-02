"""aibes-agent Tool wrapper for the greeting plugin."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aibes_agent.tools.base import Tool, ToolContext, ToolResult

from .greeting import greet, list_styles


class GreetingInput(BaseModel):
    name: str = Field(..., description="Name to greet.")
    style: str = Field("formal", description="One of formal, casual, excited.")


class ListStylesInput(BaseModel):
    pass


class GreetingTool(Tool[GreetingInput]):
    name = "Greeting"
    description = "Return a greeting message for a given name and style."
    input_model = GreetingInput

    def is_read_only(self, input: GreetingInput) -> bool:
        return True

    async def call(self, input: GreetingInput, context: ToolContext) -> ToolResult:
        return ToolResult.ok(greet(input.name, input.style))


class ListGreetingStylesTool(Tool[ListStylesInput]):
    name = "ListGreetingStyles"
    description = "List the available greeting styles."
    input_model = ListStylesInput

    def is_read_only(self, input: ListStylesInput) -> bool:
        return True

    async def call(self, input: ListStylesInput, context: ToolContext) -> ToolResult:
        return ToolResult.ok(", ".join(list_styles()))
