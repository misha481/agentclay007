"""Общее ядро агента: цикл «модель ↔ инструменты».

Используется и CLI-версией (agent.py), и Telegram-ботом (bot.py).
Все блокирующие вызовы (requests к OpenRouter, локальные инструменты) уходят
в отдельный поток, чтобы не блокировать event loop при конкурентных запросах.
"""

import asyncio
import json
import os
import time

import books
import knowledge
import llm_client
import logger as agent_logger
import memory
import pdftools
import systools
import tools
import webtools
from mcp_client import MCPFilesystemClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = (
    "Ты — агент-помощник. Твои инструменты:\n"
    "— roll_dice, sum_numbers, calculate — кубик, сумма чисел, арифметика;\n"
    "— remember, recall_facts, forget_fact — долговременная память о пользователе;\n"
    "— search_knowledge — поиск по базе знаний, архиву Telegram-канала "
    "«Афинская школа» о философии;\n"
    "— web_search, fetch_url — поиск в интернете и чтение веб-страниц;\n"
    "— get_book_pdf, find_book — найти книгу по названию и прислать её текст в PDF;\n"
    "— convert_file_to_pdf, make_pdf_from_text — сделать PDF из файла или текста;\n"
    "— get_brightness, set_brightness — узнать и изменить яркость экрана компьютера;\n"
    "— fs__* (fs__read_file, fs__write_file, fs__list_directory и т.п.) — файлы "
    "в разрешённой директории через MCP-сервер.\n\n"
    "Правила:\n"
    "— Используй remember, когда пользователь просит что-то запомнить или сообщает "
    "важный факт о себе, который стоит помнить между сессиями.\n"
    "— Если вопрос о содержании канала «Афинская школа», философии или о том, что "
    "писал автор канала — сначала вызови search_knowledge и отвечай, опираясь на "
    "найденные фрагменты, со ссылками на номера сообщений. Если в базе ничего "
    "релевантного нет — скажи прямо, не выдумывай.\n"
    "— Для актуальных сведений, новостей и фактов, которых нет в базе знаний, "
    "используй web_search, при необходимости открывай страницы через fetch_url. "
    "Не выдумывай факты, которые можно проверить поиском.\n"
    "— Когда просят книгу или её текст, вызывай get_book_pdf: файл отправится "
    "пользователю сам. Доступна только классика в общественном достоянии "
    "(Викитека для русского, Project Gutenberg для английского); современные книги "
    "под авторским правом получить нельзя — в таком случае скажи об этом честно.\n"
    "— Сборка книги занимает до двух минут, это нормально.\n"
    "— Отвечай кратко и по делу."
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
            tools.TOOL_SCHEMAS
            + memory.TOOL_SCHEMAS
            + knowledge.TOOL_SCHEMAS
            + webtools.TOOL_SCHEMAS
            + pdftools.TOOL_SCHEMAS
            + books.TOOL_SCHEMAS
            + systools.TOOL_SCHEMAS
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

    def local_tool_functions(self, memory_store, artifacts=None):
        return {
            **tools.TOOL_FUNCTIONS,
            **knowledge.TOOL_FUNCTIONS,
            **webtools.TOOL_FUNCTIONS,
            **memory_store.tool_functions(),
            **pdftools.tool_functions(artifacts),
            **books.tool_functions(artifacts),
            **systools.TOOL_FUNCTIONS,
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

    async def run_turn(self, messages, memory_store, on_tool=None, artifacts=None):
        """Прогнать один ход: цикл вызовов инструментов до финального ответа.

        messages изменяется на месте (messages[0] — системное сообщение).
        artifacts (список) наполняется путями созданных файлов — бот отправляет
        их пользователю. Возвращает текст финального ответа модели.
        """
        tool_functions = self.local_tool_functions(memory_store, artifacts)

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
