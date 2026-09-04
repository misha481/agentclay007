"""CLI-версия агента: REPL в терминале поверх общего ядра (core.py)."""

import asyncio
import os

from dotenv import load_dotenv

import core
import memory


def print_tool(name, args, result):
    print(f"\n> Вызов инструмента: {name}({args})")
    print(f"< Результат: {result}")


async def main():
    load_dotenv()

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Ошибка: задайте OPENROUTER_API_KEY в .env (см. .env.example)")
        return

    store = memory.cli_store

    runtime = core.AgentRuntime()
    # В своём терминале работаем с корнем проекта (в боте — песочница).
    await runtime.start(root_dir=core.BASE_DIR, use_mcp=True)
    print()

    try:
        saved_history = store.load_history()
        messages = [core.build_system_message(store)] + saved_history
        if saved_history:
            print(f"Загружена история диалога ({len(saved_history)} сообщений). "
                  f"'/clear' — очистить память диалога.\n")

        print("Локальный агент запущен. Введите задачу (или 'exit' для выхода).\n")

        while True:
            try:
                user_input = await asyncio.to_thread(input, "Вы: ")
                user_input = user_input.strip()
            except (EOFError, KeyboardInterrupt):
                print("\nВыход.")
                break

            if user_input.lower() in ("exit", "quit", "выход"):
                break
            if user_input.lower() == "/clear":
                messages = [core.build_system_message(store)]
                store.clear_history()
                print("История диалога очищена.\n")
                continue
            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})

            try:
                answer = await runtime.run_turn(messages, store, on_tool=print_tool)
                print(f"\nАгент: {answer}\n")
            except Exception as e:
                print(f"Ошибка запроса к модели: {e}")

            store.save_history(messages[1:])
    finally:
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())
