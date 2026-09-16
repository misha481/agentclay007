"""Логирование вызовов инструментов агента."""

import logging
import os
import traceback

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")

logger = logging.getLogger("local_agent")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)


def log_tool_call(name, args):
    logger.info("TOOL_CALL %s args=%s", name, args)


def log_tool_result(name, duration_ms, result):
    preview = str(result)
    if len(preview) > 500:
        preview = preview[:500] + "...[truncated]"
    logger.info("TOOL_RESULT %s duration_ms=%.1f result=%s", name, duration_ms, preview)


def log_tool_error(name, error):
    logger.error("TOOL_ERROR %s error=%s", name, error)


def log_crash(where, error):
    """Неперехваченная ошибка — пишем с полным стеком, а не одной строкой."""
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    logger.error("CRASH %s: %s\n%s", where, error, tb)


def log_llm_call(what, model):
    """Обращения к модели раньше не логировались вовсе — из-за этого зависание
    в ожидании ответа OpenRouter было не видно в agent.log."""
    logger.info("LLM_CALL %s model=%s", what, model)


def log_llm_result(what, duration_ms, body_bytes):
    logger.info("LLM_RESULT %s duration_ms=%.1f bytes=%d", what, duration_ms, body_bytes)
