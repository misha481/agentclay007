---
description: Остановить бота
allowed-tools: Bash(tasklist:*), PowerShell
---

Останови Telegram-бота.

Найди процессы: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`.

Покажи, что нашёл, **до** того как убивать. Убивай только те, у которых в `CommandLine` есть `bot.py` —
в системе могут крутиться другие python-процессы, включая мои диагностические.

Обычно их два и оба надо снять: стаб-лаунчер из `WindowsApps` и реальный интерпретатор из `Programs\Python`.
Отличить можно по времени старта — у пары от одного запуска оно совпадает до секунды.

```powershell
Get-Process -Id <PID> | Stop-Process -Force
```

После этого проверь, что процессов не осталось, и скажи об этом прямо.
