"""Выход в интернет: поиск и чтение страниц.

Сеть в этом окружении нестабильна (обрывы соединений), поэтому каждый запрос
идёт с ретраями. Часть сервисов недоступна: gutenberg.org/ebooks/search и
html.duckduckgo.com отдают пустой ответ, поэтому используем lite-версию DDG.
"""

import time

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "LocalAgentBot/1.0 (+https://github.com/misha481/agentclay007)"
HEADERS = {"User-Agent": USER_AGENT}

# DuckDuckGo отвечает 202 (анти-бот) на неброузерный User-Agent, поэтому для
# поиска представляемся браузером. Wikimedia, наоборот, требует описательный UA.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.9",
}

DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"

REQUEST_TIMEOUT = 30
RETRIES = 3
MAX_PAGE_CHARS = 20_000


def _request(method, url, **kwargs):
    """HTTP-запрос с ретраями: сеть периодически рвёт соединения."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("follow_redirects", True)

    last_error = None
    for attempt in range(RETRIES):
        try:
            # local_address="0.0.0.0" принуждает к IPv4: маршрут по IPv6 в этой
            # сети нерабочий, и без этого часть запросов падала на ровном месте.
            with httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0")) as client:
                resp = client.request(method, url, **kwargs)
            if resp.status_code == 200:
                return resp
            last_error = f"HTTP {resp.status_code}"
            # 4xx повторять смысла нет, кроме 429.
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                break
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
        if attempt < RETRIES - 1:
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Запрос не удался ({url}): {last_error}")


def web_search(query, max_results=5):
    """Поиск в интернете через DuckDuckGo (lite-версия)."""
    if not query or not str(query).strip():
        return "Ошибка: пустой поисковый запрос"

    try:
        max_results = max(1, min(int(max_results), 10))
    except (TypeError, ValueError):
        max_results = 5

    try:
        resp = _request(
            "POST", DDG_LITE_URL, data={"q": str(query).strip()}, headers=BROWSER_HEADERS
        )
    except Exception as e:
        return f"Ошибка поиска: {e}"

    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.select("a.result-link")
    if not links:
        return "По запросу ничего не найдено."

    # Описания лежат в отдельных ячейках таблицы результатов.
    snippets = [td.get_text(" ", strip=True) for td in soup.select("td.result-snippet")]

    lines = []
    for i, a in enumerate(links[:max_results]):
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        snippet = snippets[i] if i < len(snippets) else ""
        block = f"[{i + 1}] {title}\n{href}"
        if snippet:
            block += f"\n{snippet[:300]}"
        lines.append(block)

    return "\n\n".join(lines)


def fetch_url(url, max_chars=MAX_PAGE_CHARS):
    """Прочитать веб-страницу и вернуть её текст."""
    if not url or not str(url).strip():
        return "Ошибка: не указан URL"

    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        max_chars = max(500, min(int(max_chars), MAX_PAGE_CHARS))
    except (TypeError, ValueError):
        max_chars = MAX_PAGE_CHARS

    try:
        resp = _request("GET", url)
    except Exception as e:
        return f"Ошибка загрузки страницы: {e}"

    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype and "json" not in ctype:
        return f"Страница не текстовая (content-type: {ctype or 'неизвестен'})"

    if "html" in ctype:
        soup = BeautifulSoup(resp.text, "lxml")
        for sel in ["script", "style", "nav", "header", "footer", "noscript", "aside"]:
            for tag in soup.select(sel):
                tag.decompose()
        main = soup.select_one("article") or soup.select_one("main") or soup.body or soup
        text = main.get_text("\n", strip=True)
        title = soup.title.get_text(strip=True) if soup.title else ""
    else:
        text = resp.text
        title = ""

    if not text.strip():
        return "Страница пуста или её содержимое не удалось извлечь."

    truncated = len(text) > max_chars
    text = text[:max_chars]
    head = f"Источник: {url}\n"
    if title:
        head += f"Заголовок: {title}\n"
    tail = "\n\n[...текст обрезан...]" if truncated else ""
    return f"{head}\n{text}{tail}"


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Поиск в интернете. Используй для актуальных сведений, новостей, "
                "фактов, которых нет в базе знаний, и чтобы найти адрес нужной "
                "страницы. Возвращает список результатов со ссылками и описаниями."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "max_results": {
                        "type": "integer",
                        "description": "Сколько результатов вернуть (1-10, по умолчанию 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Открыть веб-страницу по ссылке и получить её текст. Используй после "
                "web_search, чтобы прочитать найденную страницу целиком."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Адрес страницы"},
                },
                "required": ["url"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "web_search": lambda args: web_search(args.get("query", ""), args.get("max_results", 5)),
    "fetch_url": lambda args: fetch_url(args.get("url", "")),
}
