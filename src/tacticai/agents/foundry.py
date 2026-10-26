"""Foundry connection shared by every agent: one sync call, tool-call log, no retries."""
from __future__ import annotations

import asyncio
import functools
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Sequence

API_VERSION = "2024-10-21"
_VARS = ("FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY")


def configured() -> bool:
    return all(os.environ.get(v) for v in _VARS)


class ToolLog:
    """Wraps plain callables as model tools; every call gets an id (c1, c2...) and a log entry.

    The model receives {"call_id": "c4", **result} (a dict result) or {"call_id": "c4", "result": x}
    (anything else). Errors come back as {"call_id", "error"}; after `cap` calls the tool
    answers {"error": "tool call limit reached (N)"} without running.
    """

    def __init__(self, cap: int | None = None):
        self.cap = cap
        self.entries: list[dict] = []
        self._lock = threading.Lock()

    def call(self, name: str, fn: Callable, **kwargs) -> dict:
        """Run fn now (code-side call) and log it; returns the log entry."""
        with self._lock:
            if self.cap is not None and len(self.entries) >= self.cap:
                return {"call_id": None, "tool": name, "args": kwargs,
                        "response": {"error": f"tool call limit reached ({self.cap})"}}
            entry = {"call_id": f"c{len(self.entries) + 1}", "tool": name, "args": kwargs, "response": None}
            self.entries.append(entry)  # id reserved under the lock; fn runs outside it
        try:
            entry["response"] = fn(**kwargs)
        except Exception as e:
            entry["response"] = {"error": f"{type(e).__name__}: {e}"}
        return entry

    def wrap(self, fn: Callable, name: str | None = None) -> Callable:
        """The model-facing version of fn: same signature and docstring, logged."""
        tool_name = name or fn.__name__

        @functools.wraps(fn)
        def tool(**kwargs):
            entry = self.call(tool_name, fn, **kwargs)
            resp = entry["response"]
            out = resp if isinstance(resp, dict) else {"result": resp}
            return out if entry["call_id"] is None else {"call_id": entry["call_id"], **out}

        tool.__name__ = tool_name
        return tool

    def wrap_all(self, fns: Sequence[Callable]) -> list[Callable]:
        return [self.wrap(f) for f in fns]

    def write(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for e in self.entries:
                f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")


async def _run(instructions, message, tools, response_format, max_tool_calls, max_output_tokens):
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatCompletionClient
    from openai import AsyncAzureOpenAI

    oai = AsyncAzureOpenAI(azure_endpoint=os.environ["FOUNDRY_ENDPOINT"], api_key=os.environ["FOUNDRY_API_KEY"],
                           api_version=API_VERSION, max_retries=0)  # no SDK retries
    try:
        client = OpenAIChatCompletionClient(model=os.environ["FOUNDRY_DEPLOYMENT"], async_client=oai)
        if max_tool_calls is not None:
            client.function_invocation_configuration["max_function_calls"] = max_tool_calls
        options: dict[str, Any] = {"temperature": 0}
        if max_output_tokens:
            options["max_tokens"] = max_output_tokens
        if response_format is not None:
            options["response_format"] = response_format
        agent = Agent(client, instructions, tools=list(tools) or None, default_options=options)
        return await agent.run(message)
    finally:
        await oai.close()


def run(instructions: str, message: str, *, tools: Sequence[Callable] = (), response_format=None,
        timeout_s: float, max_tool_calls: int | None = None, max_output_tokens: int | None = None):
    """One agent run, synchronous. Returns a Pydantic instance (response_format) or the text. Raises on failure."""
    async def go():
        r = await asyncio.wait_for(
            _run(instructions, message, tools, response_format, max_tool_calls, max_output_tokens), timeout_s)
        if response_format is not None:
            if r.value is None:
                raise ValueError("model returned no structured output")
            return r.value
        return r.text

    return asyncio.run(go())
