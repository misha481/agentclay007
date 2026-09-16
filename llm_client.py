"""Клиент для OpenRouter: Chat Completions и Embeddings (OpenAI-совместимый)."""

import json
import os
import time

import requests

import logger as agent_logger

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

DEFAULT_MODEL = "qwen/qwen3.5-9b"
DEFAULT_EMBED_MODEL = "qwen/qwen3-embedding-8b"

# (сколько ждём соединения, сколько ждём очередную порцию байт).
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 90

# Общий потолок на запрос. Нужен отдельно от READ_TIMEOUT: таймаут requests
# отсчитывает паузу между байтами, а OpenRouter на долгих генерациях досылает
# в chunked-ответ служебные байты, чтобы прокси не рвали соединение. Каждый
# такой байт сбрасывает отсчёт, поэтому read timeout не наступает никогда —
# бот залипал в recv навсегда, оставаясь с виду живым.
CHAT_DEADLINE = 300
EMBED_DEADLINE = 600


def _post_json(url, payload, deadline, what):
    """POST с общим дедлайном по часам, а не только паузой между байтами."""
    start = time.monotonic()
    agent_logger.log_llm_call(what, payload.get("model"))

    resp = requests.post(
        url,
        headers=_headers(),
        json=payload,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        stream=True,
    )
    try:
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter вернул ошибку {resp.status_code}: {resp.text[:500]}"
            )

        chunks = []
        for chunk in resp.iter_content(8192):
            chunks.append(chunk)
            spent = time.monotonic() - start
            if spent > deadline:
                raise RuntimeError(
                    f"OpenRouter не прислал ответ целиком за {deadline} с "
                    f"(получено {sum(len(c) for c in chunks)} Б) — обрываем запрос"
                )
    finally:
        resp.close()

    body = b"".join(chunks)
    duration_ms = (time.monotonic() - start) * 1000
    agent_logger.log_llm_result(what, duration_ms, len(body))

    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OpenRouter прислал не-JSON ({e}): {body[:300]!r}")

# Обратная совместимость: раньше модуль экспортировал OPENROUTER_URL.
OPENROUTER_URL = CHAT_URL


def _api_key():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Не задана переменная окружения OPENROUTER_API_KEY")
    return api_key


def _headers():
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def chat_model():
    # Читаем окружение при вызове, а не на импорте: load_dotenv() выполняется
    # уже после импорта модуля.
    return os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL


def embed_model():
    return os.environ.get("OPENROUTER_EMBED_MODEL") or DEFAULT_EMBED_MODEL


def chat(messages, tools=None, model=None, temperature=0.3):
    payload = {
        "model": model or chat_model(),
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools

    data = _post_json(CHAT_URL, payload, CHAT_DEADLINE, "chat")
    return data["choices"][0]["message"]


def embed(texts, model=None):
    """Получить эмбеддинги для списка текстов. Возвращает список векторов
    в том же порядке, что и входные тексты."""
    if isinstance(texts, str):
        texts = [texts]
    if not texts:
        return []

    payload = {"model": model or embed_model(), "input": list(texts)}

    data = _post_json(EMBEDDINGS_URL, payload, EMBED_DEADLINE, "embed")
    # Порядок в ответе не гарантирован — сортируем по index.
    items = sorted(data["data"], key=lambda x: x.get("index", 0))
    return [item["embedding"] for item in items]
