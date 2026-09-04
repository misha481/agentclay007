"""Общее ядро агента: цикл «модель ↔ инструменты».

Используется и CLI-версией (agent.py), и Telegram-ботом (bot.py).
Все блокирующие вызовы (requests к OpenRouter, локальные инструменты) уходят
в отдельный поток, чтобы не блокировать event loop при конкурентных запросах.
"""

import asyncio
import json
import os
import time

import knowledge
import llm_client
import logger as agent_logger
import memory
import tools
from mcp_client import MCPFilesystemClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = (
    "Ты — агент-помощник. "
    "У тебя есть инструменты: бросок кубиков (roll_dice), подсчёт суммы чисел (sum_numbers), "
    "калькулятор арифметических выражений (calculate), долговременная память "
    "(remember, recall_facts, forget_fact), поиск по базе знаний "
    "(search_knowledge) — архиву Telegram-канала «Афинская школа» о философии, "
    "а также файловые инструменты с префиксом "
    "fs__ (fs__read_file, fs__write_file, fs__list_directory и т.п.), предоставленные MCP-сервером "
    "@modelcontextprotocol/server-filesystem, ограниченным разрешённой директорией. "
    "Используй remember, когда пользователь просит что-то запомнить или сообщает важный факт "
    "о себе, который стоит помнить между сессиями. "
    "Если вопрос касается содержания канала «Афинская школа», философии или того, что писал "
    "автор канала — сначала вызови search_knowledge и отвечай, опираясь на найденные фрагменты, "
    "ссылаясь на номера сообщений. Если в базе ничего релевантного нет — скажи об этом прямо, "
    "не выдумывай. Используй инструменты, когда это нужно для задачи. "
    "Отвечай кратко и по делу."
)

MAX_TOOL_ITERATIONS = 12


def build_system_message(memory_store):
    """Системный промпт с актуальным профилем пользователя."""
    return {"role": "system", "content": SYSTEM_PROMPT + memory_store.profile_as_prompt()}


class AgentRuntime:
    """Инструменты и MCP-сессия, общие для всех пользователей."""

    def __init__(self):
        self.mcp_client = None
        self.base_tool_schemas = (
            tools.TOOL_SCHEMAS + memory.TOOL_SCHEMAS + knowledge.TOOL_SCHEMAS
        )
        self.tool_schemas = list(self.base_tool_schemas)
        # Одна MCP-сессия на всех — вызовы сериализуем.
        self._mcp_lock = asyncio.Lock()

    async def start(self, root_dir=None, use_mcp=True, verbose=True):
        root_dir = root_dir or BASE_DIR

        # Прогреваем индекс заранее: иначе конкурентные запросы наперегонки
        # полезут его собирать.
        if os.path.isfile(knowledge.KB_PATH):
            try:
                if not knowledge.index_is_fresh():
                    if verbose:
                        print("Индекс базы знаний отсутствует или устарел — собираю...")
                    await asyncio.to_thread(knowledge.build_index, verbose)
                else:
                    await asyncio.to_thread(knowledge._ensure_index, False)
                if verbose:
                    print("База знаний готова.")
            except Exception as e:
                if verbose:
                    print(f"Не удалось подготовить базу знаний: {e}")

        if use_mcp:
            os.makedirs(root_dir, exist_ok=True)
            self.mcp_client = MCPFilesystemClient(root_dir)
            if verbose:
                print("Запускаю MCP-сервер @modelcontextprotocol/server-filesystem...")
            try:
                await self.mcp_client.start()
                self.tool_schemas = self.base_tool_schemas + self.mcp_client.tool_schemas()
                if verbose:
                    print(f"MCP-сервер запущен, доступ ограничен: {root_dir}")
            except Exception as e:
                if verbose:
                    print(f"Не удалось запустить MCP-сервер: {e}")
                    print("Файловые инструменты будут недоступны.")
                self.mcp_client = None

    async def stop(self):
        if self.mcp_client:
            await self.mcp_client.stop()
            self.mcp_client = None

    def local_tool_functions(self, memory_store):
        return {
            **tools.TOOL_FUNCTIONS,
            **knowledge.TOOL_FUNCTIONS,
            **memory_store.tool_functions(),
        }

    async def _call_tool(self, tool_call, tool_functions):
        name = tool_call["function"]["name"]
        try:
            args = json.loads(tool_call["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}

        agent_logger.log_tool_call(name, args)
        start = time.perf_counter()

        try:
            if self.mcp_client and self.mcp_client.has_tool(name):
                async with self._mcp_lock:
                    result = await self.mcp_client.call_tool(name, args)
            else:
                func = tool_functions.get(name)
                if not func:
                    msg = f"Ошибка: неизвестный инструмент {name}"
                    agent_logger.log_tool_error(name, msg)
                    return name, args, msg
                result = await asyncio.to_thread(func, args)
        except Exception as e:
            agent_logger.log_tool_error(name, e)
            return name, args, f"Ошибка выполнения инструмента {name}: {e}"

        duration_ms = (time.perf_counter() - start) * 1000
        agent_logger.log_tool_result(name, duration_ms, result)
        return name, args, result

    async def run_turn(self, messages, memory_store, on_tool=None):
        """Прогнать один ход: цикл вызовов инструментов до финального ответа.

        messages изменяется на месте (messages[0] — системное сообщение).
        Возвращает текст финального ответа модели.
        """
        tool_functions = self.local_tool_functions(memory_store)

        for _ in range(MAX_TOOL_ITERATIONS):
            # Профиль мог измениться вызовом remember — пересобираем промпт.
            messages[0] = build_system_message(memory_store)

            message = await asyncio.to_thread(
                llm_client.chat, messages, self.tool_schemas
            )
            messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                return message.get("content") or ""

            for tc in tool_calls:
                name, args, result = await self._call_tool(tc, tool_functions)
                if on_tool:
                    maybe = on_tool(name, args, result)
                    if asyncio.iscoroutine(maybe):
                        await maybe
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(result),
                    }
                )

        return (
            "Превышен лимит вызовов инструментов за один ход — "
            "попробуйте переформулировать задачу."
        )
