"""Локальные инструменты агента: кубик, сумма и калькулятор.

Файловые операции вынесены на MCP-сервер @modelcontextprotocol/server-filesystem
(см. mcp_client.py) и подключаются к агенту отдельно.
"""

import ast
import operator
import random

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Разрешены только числа")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Оператор не поддерживается: {op_type.__name__}")
        return _ALLOWED_OPERATORS[op_type](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Оператор не поддерживается: {op_type.__name__}")
        return _ALLOWED_OPERATORS[op_type](_eval_node(node.operand))
    raise ValueError(f"Недопустимое выражение: {type(node).__name__}")


def calculate(expression):
    if not isinstance(expression, str) or not expression.strip():
        return "Ошибка: expression должен быть непустой строкой"
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
    except ZeroDivisionError:
        return "Ошибка: деление на ноль"
    except Exception as e:
        return f"Ошибка вычисления выражения: {e}"

    if isinstance(result, float) and result == int(result):
        result = int(result)
    return f"{expression} = {result}"


def roll_dice(sides=6, count=1):
    sides = int(sides)
    count = int(count)
    if sides < 2:
        return "Ошибка: у кубика должно быть минимум 2 грани"
    if count < 1 or count > 100:
        return "Ошибка: количество кубиков должно быть от 1 до 100"

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls)
    return f"Броски (d{sides} x{count}): {rolls}, сумма: {total}"


def sum_numbers(numbers):
    try:
        values = [float(n) for n in numbers]
    except (TypeError, ValueError):
        return "Ошибка: numbers должен быть списком чисел"
    total = sum(values)
    if total == int(total):
        total = int(total)
    return f"Сумма: {total}"


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Бросить один или несколько кубиков с заданным числом граней и вернуть результаты и сумму.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sides": {"type": "integer", "description": "Число граней кубика (по умолчанию 6)"},
                    "count": {"type": "integer", "description": "Количество кубиков (по умолчанию 1)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sum_numbers",
            "description": "Посчитать сумму списка чисел.",
            "parameters": {
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Список чисел для суммирования",
                    }
                },
                "required": ["numbers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Вычислить арифметическое выражение (+, -, *, /, //, %, **, скобки).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Арифметическое выражение, например '2 * (3 + 4) / 7'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "roll_dice": lambda args: roll_dice(args.get("sides", 6), args.get("count", 1)),
    "sum_numbers": lambda args: sum_numbers(args.get("numbers", [])),
    "calculate": lambda args: calculate(args.get("expression", "")),
}
