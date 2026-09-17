"""Telegram-версия агента на aiogram 3 поверх общего ядра (core.py).

Модель безопасности:
  * доступ только для user_id из TELEGRAM_ALLOWED_USERS;
  * файловые инструменты MCP ограничены песочницей workspace/, поэтому .env
    с ключами, код и чужие профили недоступны через fs__*;
  * у каждого пользователя своя память в data/<user_id>/.
"""

import asyncio
import datetime
import faulthandler
import os
import socket
import sys
import threading
import time
import traceback

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BotCommand, FSInputFile, Message
from dotenv import load_dotenv

import books
import core
import knowledge
import llm_client
import logger as agent_logger
import memory
import pdftools

TELEGRAM_MAX_CHARS = 4096
TYPING_REFRESH_SECONDS = 4
# Лимит Telegram на отправку документа ботом.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

WORKSPACE_DIR = os.path.join(core.BASE_DIR, "workspace")
CRASH_LOG_PATH = os.path.join(core.BASE_DIR, "crash.log")

# Держим файл открытым на всё время работы: faulthandler пишет в него уже из
# аварийного обработчика, где открывать что-либо поздно.
_crash_file = None


def setup_crash_logging():
    """Поймать то, чего не видно в agent.log.

    Бот исчезал молча: ни трейсбэка, ни строки о перезапуске поллинга. Значит,
    падение шло мимо except-ов — жёсткий сбой интерпретатора, неперехваченное
    исключение вне хендлера или ошибка в фоновой задаче. Каждый из этих трёх
    случаев теперь оставляет след в crash.log.
    """
    global _crash_file
    _crash_file = open(CRASH_LOG_PATH, "a", encoding="utf-8", buffering=1)
    _crash_file.write(
        f"\n=== старт {datetime.datetime.now():%Y-%m-%d %H:%M:%S} pid={os.getpid()} ===\n"
    )
    # Segfault, переполнение стека, abort в C-расширении.
    faulthandler.enable(file=_crash_file)

    def on_uncaught(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        agent_logger.log_crash("uncaught", exc)
        traceback.print_exception(exc_type, exc, tb, file=_crash_file)

    sys.excepthook = on_uncaught

    def on_thread_exception(args):
        if args.exc_value is not None:
            agent_logger.log_crash(f"thread {args.thread.name}", args.exc_value)
            traceback.print_exception(
                args.exc_type, args.exc_value, args.exc_traceback, file=_crash_file
            )

    threading.excepthook = on_thread_exception


def note_exit(reason):
    """Отметить, чем закончился процесс: штатно или нет."""
    stamp = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}"
    agent_logger.logger.info("BOT_EXIT %s", reason)
    if _crash_file:
        _crash_file.write(f"=== выход {stamp}: {reason} ===\n")

HELP_TEXT = (
    "Я агент на Qwen через OpenRouter. Умею:\n"
    "• отвечать на вопросы и считать (калькулятор, кубик)\n"
    "• искать в интернете и читать веб-страницы\n"
    "• присылать книги в PDF по названию — на русском и английском "
    "(классика в общественном достоянии)\n"
    "• конвертировать текстовые файлы в PDF — пришли файл, и я верну PDF\n"
    "• искать по базе знаний канала «Афинская школа»\n"
    "• запоминать факты о тебе между сессиями («запомни, что ...»)\n\n"
    "Команды:\n"
    "/book <название> — прислать книгу в PDF\n"
    "/clear — очистить историю диалога (профиль сохранится)\n"
    "/profile — показать, что я о тебе помню\n"
    "/status — как я себя чувствую\n"
    "/id — показать твой Telegram id\n"
    "/help — эта справка\n\n"
    "Всё это можно и просто словами — команды нужны только для скорости."
)

# Меню Telegram: по нему клиент подсказывает команды при первом обращении,
# без него кнопка «/» в чате пустая и о командах можно узнать только из справки.
BOT_COMMANDS = [
    BotCommand(command="book", description="Прислать книгу в PDF"),
    BotCommand(command="profile", description="Что я о тебе помню"),
    BotCommand(command="clear", description="Очистить историю диалога"),
    BotCommand(command="status", description="Как я себя чувствую"),
    BotCommand(command="id", description="Твой Telegram id"),
    BotCommand(command="help", description="Что я умею"),
]

STARTED_AT = None

runtime = core.AgentRuntime()
dp = Dispatcher()

# Память и блокировка на пользователя: параллельные сообщения одного человека
# не должны переплетать историю.
_stores = {}
_locks = {}


def allowed_users():
    raw = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def is_allowed(user_id):
    return user_id in allowed_users()


def store_for(user_id):
    if user_id not in _stores:
        _stores[user_id] = memory.store_for_user(user_id)
    return _stores[user_id]


def lock_for(user_id):
    if user_id not in _locks:
        _locks[user_id] = asyncio.Lock()
    return _locks[user_id]


def split_message(text):
    """Разбить длинный ответ на части в пределах лимита Telegram."""
    text = text or ""
    if len(text) <= TELEGRAM_MAX_CHARS:
        return [text] if text else []

    parts = []
    while text:
        if len(text) <= TELEGRAM_MAX_CHARS:
            parts.append(text)
            break
        window = text[:TELEGRAM_MAX_CHARS]
        cut = window.rfind("\n\n")
        if cut < TELEGRAM_MAX_CHARS // 2:
            cut = window.rfind("\n")
        if cut < TELEGRAM_MAX_CHARS // 2:
            cut = window.rfind(" ")
        if cut < TELEGRAM_MAX_CHARS // 2:
            cut = TELEGRAM_MAX_CHARS
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts


async def send_long(message, text):
    parts = split_message(text)
    if not parts:
        await message.answer("(пустой ответ модели)")
        return
    for part in parts:
        await message.answer(part)


async def keep_typing(bot, chat_id, stop_event):
    """Индикатор «печатает» истекает через ~5 с — обновляем, пока работаем."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=TYPING_REFRESH_SECONDS)
        except asyncio.TimeoutError:
            pass


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await message.answer(f"Привет! {HELP_TEXT}")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await message.answer(HELP_TEXT)


@dp.message(Command("id"))
async def cmd_id(message: Message):
    # Доступен всем: иначе новый пользователь не узнает свой id.
    await message.answer(f"Твой Telegram id: {message.from_user.id}")


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)
    store_for(message.from_user.id).clear_history()
    await message.answer("История диалога очищена. Профиль (что я о тебе помню) сохранён.")


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await message.answer(store_for(message.from_user.id).recall_facts())


@dp.message(Command("book"))
async def cmd_book(message: Message, command: CommandObject):
    if not is_allowed(message.from_user.id):
        return await deny(message)

    query = (command.args or "").strip()
    if not query:
        return await message.answer(
            "Напиши название после команды, например:\n"
            "/book Гранатовый браслет Куприн\n\n"
            "Доступна классика в общественном достоянии: Викитека для русского, "
            "Project Gutenberg для английского."
        )

    # Сборка идёт мимо модели: книгу собирает тот же инструмент, что и в диалоге,
    # но без лишнего хода к LLM — быстрее и нечему залипать на ответе OpenRouter.
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        keep_typing(message.bot, message.chat.id, stop_typing)
    )
    await message.answer(f"Ищу «{query}». Сборка занимает до пары минут.")

    artifacts = []
    try:
        build = books.tool_functions(artifacts)["get_book_pdf"]
        text = await asyncio.to_thread(build, {"title": query})
    except Exception as e:
        agent_logger.log_crash("cmd_book", e)
        text = f"Не удалось собрать книгу: {e}"
    finally:
        stop_typing.set()
        await typing_task

    try:
        await send_long(message, text)
        if artifacts:
            await send_artifacts(message, artifacts)
    except Exception as e:
        agent_logger.log_crash("cmd_book_send", e)


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)

    if STARTED_AT is None:
        uptime = "неизвестно"
    else:
        seconds = int(time.monotonic() - STARTED_AT)
        hours, rest = divmod(seconds, 3600)
        uptime = f"{hours} ч {rest // 60} мин" if hours else f"{rest // 60} мин"

    lines = [
        f"Работаю: {uptime}",
        f"Модель: {llm_client.chat_model()}",
        f"Файловые инструменты: {'доступны' if runtime.mcp_client else 'недоступны'}",
        f"База знаний: {'готова' if os.path.isfile(knowledge.INDEX_PATH) else 'не собрана'}",
        f"Инструментов подключено: {len(runtime.tool_schemas)}",
    ]
    await message.answer("\n".join(lines))


async def deny(message: Message):
    await message.answer(
        "Доступ к этому боту ограничен.\n"
        f"Твой id: {message.from_user.id}\n"
        "Попроси владельца добавить его в TELEGRAM_ALLOWED_USERS."
    )


async def send_artifacts(message, paths):
    """Отправить файлы, созданные инструментами за этот ход."""
    for path in paths:
        try:
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            if size > MAX_UPLOAD_BYTES:
                await message.answer(
                    f"Файл {os.path.basename(path)} слишком большой для Telegram "
                    f"({size // 1024 // 1024} МБ, лимит 50 МБ)."
                )
                continue
            await message.answer_document(FSInputFile(path))
        except Exception as e:
            agent_logger.log_tool_error("send_document", e)
            await message.answer(f"Не удалось отправить файл {os.path.basename(path)}: {e}")


async def process_turn(message, user_text):
    """Один ход диалога: прогон через ядро, ответ и отправка файлов."""
    user_id = message.from_user.id
    store = store_for(user_id)
    lock = lock_for(user_id)

    if lock.locked():
        await message.answer("Ещё думаю над предыдущим сообщением — секунду.")
        return

    async with lock:
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(
            keep_typing(message.bot, message.chat.id, stop_typing)
        )

        artifacts = []
        try:
            messages = [core.build_system_message(store)] + store.load_history()
            messages.append({"role": "user", "content": user_text})

            answer = await runtime.run_turn(messages, store, artifacts=artifacts)
            store.save_history(messages[1:])
        except Exception as e:
            agent_logger.log_tool_error("telegram_turn", e)
            answer = f"Ошибка при обработке запроса: {e}"
        finally:
            stop_typing.set()
            await typing_task

        # Отправка тоже ходит в сеть и тоже может оборваться. Раньше исключение
        # отсюда улетало из хендлера наружу.
        try:
            await send_long(message, answer)
            if artifacts:
                await send_artifacts(message, artifacts)
        except Exception as e:
            agent_logger.log_crash("send_answer", e)


@dp.message(F.text)
async def handle_text(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)

    text = (message.text or "").strip()
    if not text:
        return
    await process_turn(message, text)


@dp.message(F.document)
async def handle_document(message: Message):
    """Присланный файл скачиваем в песочницу и передаём агенту."""
    if not is_allowed(message.from_user.id):
        return await deny(message)

    doc = message.document
    if doc.file_size and doc.file_size > MAX_UPLOAD_BYTES:
        return await message.answer("Файл слишком большой (лимит 50 МБ).")

    incoming_dir = os.path.join(WORKSPACE_DIR, "incoming")
    os.makedirs(incoming_dir, exist_ok=True)
    filename = pdftools.safe_filename(
        os.path.splitext(doc.file_name or "file")[0]
    ) + os.path.splitext(doc.file_name or "")[1]
    dest = os.path.join(incoming_dir, filename or "file")

    try:
        await message.bot.download(doc, destination=dest)
    except Exception as e:
        agent_logger.log_tool_error("download_document", e)
        return await message.answer(f"Не удалось скачать файл: {e}")

    caption = (message.caption or "").strip()
    rel = os.path.relpath(dest, WORKSPACE_DIR).replace("\\", "/")
    task = caption or "Конвертируй этот файл в PDF и пришли мне."
    await process_turn(message, f"{task}\n\n(файл сохранён как: {rel})")


@dp.message()
async def handle_other(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await message.answer("Пока понимаю текст и файлы.")


async def main():
    load_dotenv()

    # Ошибка в фоновой задаче (например, в keep_typing) иначе тонет в stderr.
    def on_loop_error(loop, context):
        exc = context.get("exception")
        if exc is not None:
            agent_logger.log_crash("event_loop", exc)
        else:
            agent_logger.logger.error("CRASH event_loop: %s", context.get("message"))

    asyncio.get_running_loop().set_exception_handler(on_loop_error)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Ошибка: задайте TELEGRAM_BOT_TOKEN в .env (см. .env.example)")
        return
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Ошибка: задайте OPENROUTER_API_KEY в .env")
        return

    users = allowed_users()
    if users:
        print(f"Разрешённые пользователи: {sorted(users)}")
    else:
        print("ВНИМАНИЕ: TELEGRAM_ALLOWED_USERS пуст — бот никого не пустит.")
        print("Напиши боту /id, добавь свой id в .env и перезапусти.")

    # Песочница для файловых инструментов: .env и код вне доступа fs__*.
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    await runtime.start(root_dir=WORKSPACE_DIR, use_mcp=True)

    # DNS отдаёт для api.telegram.org и IPv6, и IPv4, но маршрут по IPv6 здесь
    # нерабочий: запрос по нему падает мгновенно, тогда как IPv4 отвечает
    # нормально. Без этой настройки aiohttp ходил по IPv6 и валился с
    # "getaddrinfo failed" и таймаутами — из-за этого бот и падал.
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET

    bot = Bot(token=token, session=session, default=DefaultBotProperties(parse_mode=None))
    me = await bot.get_me()

    # Без этого кнопка «/» в чате пустая: Telegram подсказывает команды только
    # из зарегистрированного меню. Не критично для работы — если не прошло,
    # продолжаем, команды всё равно действуют и перечислены в /help.
    try:
        await bot.set_my_commands(BOT_COMMANDS)
        print(f"Меню команд зарегистрировано: {len(BOT_COMMANDS)} шт.")
    except Exception as e:
        print(f"Не удалось зарегистрировать меню команд: {e}")
        agent_logger.log_tool_error("set_my_commands", e)

    global STARTED_AT
    STARTED_AT = time.monotonic()
    print(f"\nБот @{me.username} запущен. Ctrl+C для остановки.\n")

    # Сеть до api.telegram.org здесь нестабильна: длинный long-poll рвётся,
    # и без этой обёртки процесс просто падал. Перезапускаем поллинг.
    try:
        attempt = 0
        while True:
            try:
                await dp.start_polling(bot, polling_timeout=20, handle_signals=False)
                break  # штатная остановка
            except asyncio.CancelledError:
                raise
            except Exception as e:
                attempt += 1
                delay = min(5 * attempt, 60)
                print(f"Поллинг оборвался ({type(e).__name__}: {e}). "
                      f"Перезапуск через {delay} с (попытка {attempt}).")
                agent_logger.log_tool_error("polling", e)
                await asyncio.sleep(delay)
    finally:
        await runtime.stop()
        await bot.session.close()


if __name__ == "__main__":
    setup_crash_logging()
    try:
        asyncio.run(main())
        note_exit("штатная остановка")
    except KeyboardInterrupt:
        note_exit("Ctrl+C")
        print("\nОстановлен.")
    except BaseException as e:
        # SystemExit и MemoryError сюда тоже попадают — их и не хватало в логах.
        agent_logger.log_crash("main", e)
        traceback.print_exc(file=_crash_file)
        note_exit(f"падение: {type(e).__name__}: {e}")
        raise
