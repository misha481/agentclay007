---
description: Снять стек зависшего бота — показать, на какой строке он залип
allowed-tools: Bash(tasklist:*), Bash(ls:*), Bash(grep:*), PowerShell
---

Бот не отвечает, но процесс жив. Сними стек и покажи, где именно он стоит.

1. Найди PID реального интерпретатора (не стаб из `WindowsApps`, а тот, что из `Programs\Python`, ~200 МБ):
   `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine, WorkingSetSize`

2. Сними дамп. `py-spy` ставится как исполняемый файл, модуля `py_spy` нет — запускать надо из `Scripts`:

   ```
   PYTHONIOENCODING=utf-8 "$HOME/AppData/Local/Programs/Python/Python314/Scripts/py-spy.exe" dump --pid <PID>
   ```

   Если не установлен: `python -m pip install py-spy`

3. Сделай **два дампа с паузой в несколько секунд**. Если стек не сдвинулся — это зависание, а не медленная работа.

Как читать результат:

- `recv_into ← read_chunked ← requests.post ← chat (llm_client.py)` — залип на ответе OpenRouter.
  Должен сработать дедлайн `CHAT_DEADLINE` (300 с) из `llm_client.py`. Если висит дольше — дедлайн не отрабатывает,
  разбирайся в `_post_json`.
- Стек в `books.py` или `pdftools.py` — сборка книги. Она законно долгая: в логах есть `get_book_pdf` на 216 с.
  Прежде чем звать это зависанием, сверься со временем старта.
- Все потоки idle, главный в `_run_once` — бот просто ждёт сообщений, всё нормально.

Назови конкретную строку, на которой стоит процесс, и объясни, почему он там застрял.
