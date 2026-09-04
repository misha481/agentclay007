"""Клиент для OpenRouter: Chat Completions и Embeddings (OpenAI-совместимый)."""

import os
import requests

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

DEFAULT_MODEL = "qwen/qwen3.5-9b"
DEFAULT_EMBED_MODEL = "qwen/qwen3-embedding-8b"

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

    resp = requests.post(CHAT_URL, headers=_headers(), json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter API вернул ошибку {resp.status_code}: {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]


def embed(texts, model=None):
    """Получить эмбеддинги для списка текстов. Возвращает список векторов
    в том же порядке, что и входные тексты."""
    if isinstance(texts, str):
        texts = [texts]
    if not texts:
        return []

    payload = {"model": model or embed_model(), "input": list(texts)}

    resp = requests.post(EMBEDDINGS_URL, headers=_headers(), json=payload, timeout=180)
    if resp.status_code != 200:
        raise RuntimeError(
            f"OpenRouter Embeddings вернул ошибку {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    # Порядок в ответе не гарантирован — сортируем по index.
    items = sorted(data["data"], key=lambda x: x.get("index", 0))
    return [item["embedding"] for item in items]
