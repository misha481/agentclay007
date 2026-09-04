"""Telegram-версия агента на aiogram 3 поверх общего ядра (core.py).

Модель безопасности:
  * доступ только для user_id из TELEGRAM_ALLOWED_USERS;
  * файловые инструменты MCP ограничены песочницей workspace/, поэтому .env
    с ключами, код и чужие профили недоступны через fs__*;
  * у каждого пользователя своя память в data/<user_id>/.
"""

import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

import core
import logger as agent_logger
import memory

TELEGRAM_MAX_CHARS = 4096
TYPING_REFRESH_SECONDS = 4

WORKSPACE_DIR = os.path.join(core.BASE_DIR, "workspace")

HELP_TEXT = (
    "Я агент на Qwen через OpenRouter. Умею:\n"
    "• отвечать на вопросы и считать (калькулятор, кубик)\n"
    "• искать по базе знаний канала «Афинская школа»\n"
    "• запоминать факты о тебе между сессиями («запомни, что ...»)\n"
    "• работать с файлами в своей песочнице workspace/\n\n"
    "Команды:\n"
    "/clear — очистить историю диалога (профиль сохранится)\n"
    "/profile — показать, что я о тебе помню\n"
    "/id — показать твой Telegram id\n"
    "/help — эта справка"
)

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


async def deny(message: Message):
    await message.answer(
        "Доступ к этому боту ограничен.\n"
        f"Твой id: {message.from_user.id}\n"
        "Попроси владельца добавить его в TELEGRAM_ALLOWED_USERS."
    )


@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    if not is_allowed(user_id):
        return await deny(message)

    text = (message.text or "").strip()
    if not text:
        return

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

        try:
            messages = [core.build_system_message(store)] + store.load_history()
            messages.append({"role": "user", "content": text})

            answer = await runtime.run_turn(messages, store)
            store.save_history(messages[1:])
        except Exception as e:
            agent_logger.log_tool_error("telegram_turn", e)
            answer = f"Ошибка при обработке запроса: {e}"
        finally:
            stop_typing.set()
            await typing_task

        await send_long(message, answer)


@dp.message()
async def handle_other(message: Message):
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await message.answer("Пока понимаю только текст.")


async def main():
    load_dotenv()

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

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=None))
    me = await bot.get_me()
    print(f"\nБот @{me.username} запущен. Ctrl+C для остановки.\n")

    try:
        await dp.start_polling(bot)
    finally:
        await runtime.stop()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановлен.")
