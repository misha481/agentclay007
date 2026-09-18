"""Инструменты управления системой: яркость экрана.

Работает через WMI (root/wmi, WmiMonitorBrightness), поэтому доступно на
ноутбуках со встроенной матрицей. Внешние мониторы по DDC/CI этот интерфейс
обычно не отдают — там вернётся понятная ошибка, а не молчание.
"""

import subprocess

_PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
_TIMEOUT = 15


def _run_ps(script):
    result = subprocess.run(
        _PS + [script],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "неизвестная ошибка PowerShell")
    return result.stdout.strip()


def get_brightness():
    try:
        out = _run_ps(
            "(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness"
            " -ErrorAction Stop).CurrentBrightness"
        )
    except subprocess.TimeoutExpired:
        return "Ошибка: запрос яркости не ответил за 15 секунд"
    except Exception as e:
        return f"Не удалось прочитать яркость: {e}. Обычно это внешний монитор — WMI им не управляет."
    values = [line.strip() for line in out.splitlines() if line.strip().isdigit()]
    if not values:
        return "Не удалось прочитать яркость: система не вернула значение"
    if len(values) == 1:
        return f"Текущая яркость: {values[0]}%"
    return "Текущая яркость по экранам: " + ", ".join(f"{v}%" for v in values)


def set_brightness(level):
    try:
        level = int(level)
    except (TypeError, ValueError):
        return "Ошибка: level должен быть целым числом от 0 до 100"
    if not 0 <= level <= 100:
        return "Ошибка: яркость задаётся в процентах, от 0 до 100"
    try:
        # Именно Invoke-CimMethod: у объекта из Get-CimInstance методы напрямую
        # не вызываются — это не WMI-объект старого образца.
        _run_ps(
            "Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods"
            " -ErrorAction Stop | Invoke-CimMethod -MethodName WmiSetBrightness"
            f" -Arguments @{{Timeout=0; Brightness={level}}} | Out-Null"
        )
    except subprocess.TimeoutExpired:
        return "Ошибка: смена яркости не ответила за 15 секунд"
    except Exception as e:
        return f"Не удалось изменить яркость: {e}. Обычно это внешний монитор — WMI им не управляет."
    return f"Яркость выставлена на {level}%"


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_brightness",
            "description": "Узнать текущую яркость экрана компьютера в процентах.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Изменить яркость экрана компьютера. Уровень задаётся в процентах, 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "description": "Яркость в процентах, от 0 до 100",
                    }
                },
                "required": ["level"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_brightness": lambda args: get_brightness(),
    "set_brightness": lambda args: set_brightness(args.get("level")),
}
