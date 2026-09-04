"""Логирование вызовов инструментов агента."""

import logging
import os

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
