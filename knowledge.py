"""RAG по базе знаний: экспорт Telegram-канала «Афинская школа».

Векторный поиск на эмбеддингах qwen/qwen3-embedding-8b через OpenRouter.
Индекс кэшируется на диск и пересобирается, если исходник изменился.
"""

import json
import os

import numpy as np

import llm_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, "knowledge")
KB_PATH = os.path.join(KB_DIR, "athens_channel.json")
INDEX_PATH = os.path.join(KB_DIR, "index.npz")
CHUNKS_PATH = os.path.join(KB_DIR, "chunks.json")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
BATCH_SIZE = 32

# Совсем короткие посты («База», «Как же иначе)») не несут искомой информации,
# но у коротких текстов эмбеддинги вырожденные и дают высокое сходство с любым
# запросом — поэтому такие чанки в индекс не попадают.
MIN_CHUNK_CHARS = 80

# Qwen3-Embedding обучена на асимметричной схеме: запрос сопровождается
# инструкцией, документы индексируются как есть.
QUERY_INSTRUCTION = (
    "Instruct: Given a search query, retrieve relevant passages from a "
    "philosophy Telegram channel\nQuery: "
)

_cache = {"vectors": None, "chunks": None}


def _message_text(msg):
    """Собрать текст сообщения: text_entities надёжнее, чем text
    (который бывает и строкой, и списком фрагментов)."""
    entities = msg.get("text_entities")
    if isinstance(entities, list) and entities:
        text = "".join(e.get("text", "") for e in entities if isinstance(e, dict))
        if text.strip():
            return text

    raw = msg.get("text")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "".join(x if isinstance(x, str) else x.get("text", "") for x in raw)
    return ""


def _split_text(text):
    """Порезать длинный текст на куски с перехлёстом, стараясь рвать
    по границам абзацев/предложений."""
    text = text.strip()
    if len(text) <= CHUNK_SIZE:
        return [text]

    parts = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            window = text[start:end]
            # Ищем границу абзаца, затем конец предложения, в последней трети куска.
            floor = int(CHUNK_SIZE * 0.6)
            cut = window.rfind("\n\n")
            if cut < floor:
                cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
                if cut >= floor:
                    cut += 1
            if cut >= floor:
                end = start + cut
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [p for p in parts if p]


def load_chunks():
    """Разобрать экспорт канала в список чанков с метаданными."""
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    channel = data.get("name", "")
    chunks = []
    for msg in data.get("messages", []):
        if msg.get("type") != "message":
            continue
        text = _message_text(msg)
        if not text.strip():
            continue

        pieces = [p for p in _split_text(text) if len(p) >= MIN_CHUNK_CHARS]
        for i, piece in enumerate(pieces):
            chunks.append(
                {
                    "text": piece,
                    "msg_id": msg.get("id"),
                    "date": (msg.get("date") or "")[:10],
                    "forwarded_from": msg.get("forwarded_from"),
                    "part": f"{i + 1}/{len(pieces)}" if len(pieces) > 1 else None,
                    "channel": channel,
                }
            )
    return chunks


def _normalize(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_index(verbose=True):
    """Посчитать эмбеддинги для всех чанков и сохранить индекс на диск."""
    chunks = load_chunks()
    if verbose:
        print(f"Чанков к индексации: {len(chunks)}")

    vectors = []
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = [c["text"] for c in chunks[start:start + BATCH_SIZE]]
        vectors.extend(llm_client.embed(batch))
        if verbose:
            print(f"  проиндексировано {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)}")

    matrix = _normalize(np.asarray(vectors, dtype=np.float32))

    os.makedirs(KB_DIR, exist_ok=True)
    np.savez_compressed(INDEX_PATH, vectors=matrix)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"source_mtime": os.path.getmtime(KB_PATH), "chunks": chunks},
            f,
            ensure_ascii=False,
        )

    _cache["vectors"] = matrix
    _cache["chunks"] = chunks
    if verbose:
        print(f"Индекс сохранён: {matrix.shape[0]} векторов, размерность {matrix.shape[1]}")
    return len(chunks)


def index_is_fresh():
    """Индекс существует и собран по актуальной версии базы."""
    if not (os.path.isfile(INDEX_PATH) and os.path.isfile(CHUNKS_PATH)):
        return False
    try:
        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("source_mtime") == os.path.getmtime(KB_PATH)
    except Exception:
        return False


def _ensure_index(verbose=True):
    if _cache["vectors"] is not None and _cache["chunks"] is not None:
        return

    if not index_is_fresh():
        if verbose:
            print("Индекс базы знаний отсутствует или устарел — собираю...")
        build_index(verbose=verbose)
        return

    with np.load(INDEX_PATH) as npz:
        _cache["vectors"] = npz["vectors"]
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        _cache["chunks"] = json.load(f)["chunks"]


def search_knowledge(query, top_k=5):
    if not isinstance(query, str) or not query.strip():
        return "Ошибка: query должен быть непустой строкой"
    if not os.path.isfile(KB_PATH):
        return f"Ошибка: база знаний не найдена: {KB_PATH}"

    try:
        top_k = max(1, min(int(top_k), 20))
    except (TypeError, ValueError):
        top_k = 5

    try:
        _ensure_index()
        q = np.asarray(
            llm_client.embed([QUERY_INSTRUCTION + query.strip()])[0], dtype=np.float32
        )
    except Exception as e:
        return f"Ошибка поиска по базе знаний: {e}"

    q /= np.linalg.norm(q) or 1.0
    scores = _cache["vectors"] @ q
    order = np.argsort(-scores)[:top_k]

    chunks = _cache["chunks"]
    blocks = []
    for rank, idx in enumerate(order, 1):
        c = chunks[int(idx)]
        head = f"[{rank}] score={scores[int(idx)]:.3f} | сообщение #{c['msg_id']} | {c['date']}"
        if c.get("part"):
            head += f" | часть {c['part']}"
        if c.get("forwarded_from"):
            head += f" | переслано от: {c['forwarded_from']}"
        blocks.append(f"{head}\n{c['text']}")

    return "\n\n---\n\n".join(blocks) if blocks else "Ничего не найдено"


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Семантический поиск по базе знаний — архиву Telegram-канала "
                "«Афинская школа» (посты о философии: Платон, Декарт, философские "
                "трактаты, рассуждения автора канала). Используй этот инструмент для "
                "любых вопросов о содержании канала, о том, что автор писал или думает "
                "по какой-либо теме. Возвращает наиболее релевантные фрагменты постов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на естественном языке",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Сколько фрагментов вернуть (по умолчанию 5, максимум 20)",
                    },
                },
                "required": ["query"],
            },
        },
    }
]

TOOL_FUNCTIONS = {
    "search_knowledge": lambda args: search_knowledge(
        args.get("query", ""), args.get("top_k", 5)
    ),
}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
    build_index()
