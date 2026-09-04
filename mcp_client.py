"""Клиент MCP: запускает @modelcontextprotocol/server-filesystem по stdio
и превращает его инструменты в OpenAI-совместимые схемы для tool-calling."""

import json
import os
import shutil
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_TOOL_PREFIX = "fs__"


def _find_js_entry():
    """Найти dist/index.js установленного пакета через npm root -g,
    чтобы вызвать его напрямую через node (без .cmd-обёртки npx/npm,
    которая на Windows ломает asyncio-subprocess и пишет служебные
    сообщения в stdout, повреждая JSON-RPC поток)."""
    import subprocess

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"], capture_output=True, text=True, timeout=15, shell=True
        ).stdout.strip()
    except Exception:
        return None
    entry = os.path.join(npm_root, "@modelcontextprotocol", "server-filesystem", "dist", "index.js")
    return entry if os.path.isfile(entry) else None


def _resolve_command():
    """Определить, чем запускать MCP filesystem-сервер."""
    node = shutil.which("node")
    entry = _find_js_entry()
    if node and entry:
        return node, [entry]

    name = "mcp-server-filesystem.cmd" if sys.platform == "win32" else "mcp-server-filesystem"
    path = shutil.which(name) or shutil.which("mcp-server-filesystem")
    if path:
        return path, []

    npx = shutil.which("npx.cmd") if sys.platform == "win32" else shutil.which("npx")
    return npx or "npx", ["-y", "--", "@modelcontextprotocol/server-filesystem"]


class MCPFilesystemClient:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self._stack = AsyncExitStack()
        self.session = None
        self._raw_tools = []

    async def start(self):
        command, base_args = _resolve_command()
        params = StdioServerParameters(
            command=command,
            args=base_args + [self.root_dir],
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

        result = await self.session.list_tools()
        self._raw_tools = result.tools

    async def stop(self):
        await self._stack.aclose()

    def tool_schemas(self):
        schemas = []
        for t in self._raw_tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": f"{MCP_TOOL_PREFIX}{t.name}",
                        "description": t.description or "",
                        "parameters": getattr(t, "input_schema", None)
                        or getattr(t, "inputSchema", None)
                        or {"type": "object", "properties": {}},
                    },
                }
            )
        return schemas

    def has_tool(self, name):
        return name.startswith(MCP_TOOL_PREFIX)

    async def call_tool(self, name, args):
        real_name = name[len(MCP_TOOL_PREFIX):]
        try:
            result = await self.session.call_tool(real_name, args)
        except Exception as e:
            return f"Ошибка MCP-инструмента {real_name}: {e}"

        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                parts.append(str(content))
        text = "\n".join(parts) if parts else "(пустой результат)"
        is_error = getattr(result, "is_error", None)
        if is_error is None:
            is_error = getattr(result, "isError", False)
        if is_error:
            return f"Ошибка MCP-инструмента {real_name}: {text}"
        return text
