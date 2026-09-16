"""Поиск книг по (приблизительному) названию и выдача их текста в PDF.

Источники — только общественное достояние:
  * русский: ru.wikisource.org (Викитека) — классика и переводы;
  * английский: Project Gutenberg через API gutendex.com.

Книги, защищённые авторским правом (современные издания), здесь недоступны —
это ограничение источников, а не недоработка.

Особенности, выясненные на практике:
  * TextExtracts (prop=extracts) на Викитеке возвращает пустой текст —
    нужен action=parse&prop=text с последующей чисткой HTML;
  * list=allpages Wikimedia отдаёт 403 по robot policy — подстраницы
    перечисляем через action=parse&prop=links;
  * gutenberg.org/ebooks/search недоступен из этой сети, но скачивание
    text/plain с www.gutenberg.org работает.
"""

import os
import re

from bs4 import BeautifulSoup

import pdftools
from webtools import HEADERS, _request

GUTENDEX_URL = "https://gutendex.com/books"
WIKISOURCE_API = "https://{lang}.wikisource.org/w/api.php"

MAX_SUBPAGES = 120
MAX_BOOK_CHARS = 2_000_000

CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)


def detect_language(title):
    """Русское название — ищем в Викитеке, иначе на Gutenberg."""
    return "ru" if CYRILLIC_RE.search(title or "") else "en"


# --------------------------- Викитека (русский) ---------------------------


def _ws_api(lang, params):
    url = WIKISOURCE_API.format(lang=lang)
    resp = _request("GET", url, params={**params, "format": "json"}, headers=HEADERS)
    return resp.json()


def _ws_search(lang, query, limit=8):
    data = _ws_api(
        lang,
        {"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "srnamespace": 0},
    )
    return [item["title"] for item in data.get("query", {}).get("search", [])]


def _ws_page_html(lang, title):
    data = _ws_api(lang, {"action": "parse", "page": title, "prop": "text"})
    if "error" in data:
        return None
    return data.get("parse", {}).get("text", {}).get("*")


def _ws_page_links(lang, title):
    data = _ws_api(lang, {"action": "parse", "page": title, "prop": "links"})
    if "error" in data:
        return []
    return [
        link["*"]
        for link in data.get("parse", {}).get("links", [])
        if link.get("ns") == 0 and "exists" in link
    ]


def _clean_wikisource_html(html_text):
    soup = BeautifulSoup(html_text, "lxml")
    drop_selectors = [
        ".mw-editsection", "style", "script", "table", "sup.reference",
        ".ws-noexport", ".mw-references-wrap", ".reflist", ".navbox",
        "#toc", ".toc", ".mw-jump-link", ".printfooter", ".catlinks",
        ".mw-parser-output > div.thumb", ".header_notes", ".licensetpl",
    ]
    for sel in drop_selectors:
        for tag in soup.select(sel):
            tag.decompose()
    body = soup.select_one(".mw-parser-output") or soup
    return body.get_text("\n", strip=True)


def _natural_key(title):
    """Сортировка глав: римские и арабские номера в человеческом порядке."""
    roman = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

    def roman_to_int(s):
        total, prev = 0, 0
        for ch in reversed(s.upper()):
            val = roman.get(ch, 0)
            total += -val if val < prev else val
            prev = max(prev, val)
        return total

    parts = []
    for token in re.split(r"[/\s,]+", title):
        if token.isdigit():
            parts.append((1, int(token)))
        elif token and re.fullmatch(r"[IVXLCDM]+", token.upper()):
            parts.append((1, roman_to_int(token)))
        else:
            parts.append((0, token.lower()))
    return parts


def _ws_collect_text(lang, title):
    """Собрать текст произведения: сама страница + подстраницы-главы."""
    pieces = []

    main_html = _ws_page_html(lang, title)
    main_text = _clean_wikisource_html(main_html) if main_html else ""

    links = _ws_page_links(lang, title)
    subpages = sorted({l for l in links if l.startswith(title + "/")}, key=_natural_key)

    if subpages:
        # Страница-оглавление: её собственный текст не нужен, берём главы.
        for sub in subpages[:MAX_SUBPAGES]:
            html_text = _ws_page_html(lang, sub)
            if not html_text:
                continue
            chapter = _clean_wikisource_html(html_text)
            if not chapter.strip():
                continue
            heading = sub[len(title) + 1:]
            pieces.append(f"{heading}\n\n{chapter}")
            if sum(len(p) for p in pieces) > MAX_BOOK_CHARS:
                break
    elif main_text.strip():
        pieces.append(main_text)

    return "\n\n".join(pieces), len(subpages)


MAX_RESOLVE_CANDIDATES = 5


def _normalize_title(s):
    s = re.sub(r"\([^)]*\)", " ", s or "")  # убрать «(Автор)»
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip().lower()


def _title_relevance(query, candidate):
    """2 — название совпало, 1 — совпали отдельные слова, 0 — не относится."""
    q = _normalize_title(query)
    c = _normalize_title(candidate)
    if not q or not c:
        return 0
    if q == c:
        return 3
    if q in c or c in q:
        return 2
    q_words = set(q.split())
    c_words = set(c.split())
    if q_words and len(q_words & c_words) / len(q_words) >= 0.6:
        return 1
    return 0


def _ws_resolve(lang, query):
    """Найти страницу произведения по неточному названию.

    Тонкость: по запросу «Преступление и наказание» Викитека выдаёт и роман
    Достоевского, и одноимённые статьи (Дорошевич, Страхов, Марков). Просто
    взять первую ссылку нельзя — выберется статья вместо романа. Поэтому:
      * из результатов-подстраниц («…(Достоевский)/Эпилог/I») выводим страницу
        самого произведения — это самый сильный сигнал;
      * кандидатов ранжируем по числу подстраниц-глав: у романа их десятки,
        у статьи — ни одной.
    """
    results = _ws_search(lang, query)
    if not results:
        return None, []

    candidates = []

    def add(title):
        # Пускаем только релевантные названию: иначе посторонняя подстраница
        # вроде «РБС/ВТ/Захарбеков…» затащит в кандидаты весь справочник «РБС».
        if title and title not in candidates and _title_relevance(query, title) > 0:
            candidates.append(title)

    # Страницы произведений, выведенные из найденных подстраниц-глав.
    for r in results:
        if "/" in r:
            add(r.split("/")[0])
    # Затем сами результаты, которые не являются подстраницами.
    for r in results:
        if "/" not in r:
            add(r)

    # Разворачиваем дизамбиг: ссылки вида «Название (Автор)».
    if candidates:
        try:
            for link in _ws_page_links(lang, candidates[0]):
                if "/" not in link:
                    add(link)
        except Exception:
            pass

    if not candidates:
        return results[0], results

    # Ранжируем: сначала соответствие названию, потом число глав, потом объём.
    # Без проверки названия сборник вроде «О сочинениях Платона» перевесил бы
    # искомый «Евтифрон» просто потому, что у него больше подстраниц.
    scored = []
    for cand in candidates[:MAX_RESOLVE_CANDIDATES]:
        try:
            links = _ws_page_links(lang, cand)
            n_subpages = sum(1 for l in links if l.startswith(cand + "/"))
            text_len = 0
            if n_subpages == 0:
                html_text = _ws_page_html(lang, cand)
                text_len = len(_clean_wikisource_html(html_text)) if html_text else 0
            scored.append((_title_relevance(query, cand), n_subpages, text_len, cand))
        except Exception:
            continue

    if not scored:
        return results[0], results

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return scored[0][3], results


# --------------------- Project Gutenberg (английский) ---------------------


def _gutenberg_search(query, limit=5):
    resp = _request("GET", GUTENDEX_URL, params={"search": query}, headers=HEADERS, timeout=60)
    data = resp.json()
    return data.get("results", [])[:limit]


def _gutenberg_text(book):
    urls = [
        url
        for key, url in book.get("formats", {}).items()
        if key.startswith("text/plain")
    ]
    # .txt.utf-8 предпочтительнее zip-архивов.
    urls.sort(key=lambda u: (u.endswith(".zip"), "utf-8" not in u))
    for url in urls:
        if url.endswith(".zip"):
            continue
        try:
            resp = _request("GET", url, headers=HEADERS, timeout=90)
        except Exception:
            continue
        text = resp.text
        if text.strip():
            return _strip_gutenberg_boilerplate(text)
    return ""


def _strip_gutenberg_boilerplate(text):
    """Убрать юридическую обвязку Gutenberg, оставив само произведение."""
    start = re.search(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", text, re.I)
    if start:
        text = text[start.end():]
    end = re.search(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", text, re.I)
    if end:
        text = text[:end.start()]
    return text.strip()


# ------------------------------ инструменты ------------------------------


def find_book(title, lang=None):
    """Поискать книгу в источниках и показать, что нашлось."""
    if not title or not str(title).strip():
        return "Ошибка: не указано название книги"
    title = str(title).strip()
    lang = (lang or detect_language(title)).lower()

    lines = []
    if lang == "ru":
        try:
            resolved, candidates = _ws_resolve("ru", title)
            if not candidates:
                return f"В Викитеке ничего не найдено по запросу «{title}»."
            lines.append(f"Викитека (ru), варианты по запросу «{title}»:")
            for c in candidates[:8]:
                mark = " ← лучший вариант" if c == resolved else ""
                lines.append(f"  - {c}{mark}")
            if resolved and resolved not in candidates:
                lines.append(f"  - {resolved} ← лучший вариант (страница произведения)")
        except Exception as e:
            return f"Ошибка поиска в Викитеке: {e}"
    else:
        try:
            books = _gutenberg_search(title)
            if not books:
                return f"На Project Gutenberg ничего не найдено по запросу «{title}»."
            lines.append(f"Project Gutenberg, варианты по запросу «{title}»:")
            for b in books:
                authors = ", ".join(a["name"] for a in b.get("authors", [])) or "автор неизвестен"
                lines.append(f"  - {b['title'][:80]} — {authors} (id {b['id']})")
        except Exception as e:
            return f"Ошибка поиска на Project Gutenberg: {e}"

    lines.append("\nЧтобы получить PDF, вызови get_book_pdf с этим названием.")
    return "\n".join(lines)


def get_book_pdf(title, lang=None):
    """Найти книгу по названию, собрать её текст и сделать PDF.

    Возвращает (сообщение_для_модели, путь_к_PDF | None).
    """
    if not title or not str(title).strip():
        return "Ошибка: не указано название книги", None

    title = str(title).strip()
    lang = (lang or detect_language(title)).lower()

    try:
        if lang == "ru":
            resolved, candidates = _ws_resolve("ru", title)
            if not resolved:
                return (
                    f"В Викитеке не нашлось произведения «{title}». "
                    "Викитека содержит только тексты в общественном достоянии — "
                    "современные книги под авторским правом там отсутствуют."
                ), None
            text, n_subpages = _ws_collect_text("ru", resolved)
            book_title = resolved
            source = f"Викитека — https://ru.wikisource.org/wiki/{resolved.replace(' ', '_')}"
            author = None
            match = re.search(r"\(([^)]+)\)\s*$", resolved)
            if match:
                author = match.group(1)
        else:
            books = _gutenberg_search(title, limit=5)
            if not books:
                return (
                    f"На Project Gutenberg не нашлось «{title}». Там только книги "
                    "в общественном достоянии; современные издания недоступны."
                ), None
            book = books[0]
            text = _gutenberg_text(book)
            book_title = book["title"]
            author = ", ".join(a["name"] for a in book.get("authors", [])) or None
            source = f"Project Gutenberg — https://www.gutenberg.org/ebooks/{book['id']}"
            n_subpages = 0
    except Exception as e:
        return f"Ошибка получения текста книги: {e}", None

    if not text or len(text.strip()) < 500:
        return (
            f"Текст «{title}» найти не удалось — страница нашлась, но текста в ней "
            "почти нет. Попробуй уточнить название (например, добавить автора)."
        ), None

    text = text[:MAX_BOOK_CHARS]
    footer = f"\n\n\nИсточник: {source}"

    try:
        out_path = pdftools.text_to_pdf(
            text + footer,
            title=book_title,
            author=author,
            out_path=pdftools.safe_filename(book_title) + ".pdf",
        )
    except Exception as e:
        return f"Ошибка генерации PDF: {e}", None

    size_kb = os.path.getsize(out_path) // 1024
    detail = f", глав: {n_subpages}" if n_subpages else ""
    message = (
        f"PDF готов: {out_path}\n"
        f"Книга: {book_title}"
        + (f"\nАвтор: {author}" if author else "")
        + f"\nСимволов текста: {len(text)}{detail}\nРазмер: {size_kb} КБ\n"
        f"{source}\n"
        "Файл будет отправлен пользователю."
    )
    return message, out_path


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_book_pdf",
            "description": (
                "Найти книгу по названию (можно приблизительному) и прислать её полный "
                "текст в виде PDF. Работает с русскими и английскими названиями: "
                "русские ищутся в Викитеке, английские — на Project Gutenberg. "
                "Доступны только произведения в общественном достоянии (классика); "
                "современные книги под авторским правом получить нельзя. "
                "Используй этот инструмент, когда пользователь просит книгу, текст "
                "произведения или PDF с книгой."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Название книги, можно с автором: «Преступление и наказание Достоевский»",
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["ru", "en"],
                        "description": "Язык книги. Если не указан, определяется по названию",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_book",
            "description": (
                "Проверить, какие варианты книги есть в источниках, не скачивая текст. "
                "Полезно, если название неточное и надо уточнить у пользователя."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Название книги"},
                    "lang": {"type": "string", "enum": ["ru", "en"]},
                },
                "required": ["title"],
            },
        },
    },
]

def tool_functions(artifacts=None):
    """Инструменты книг. Путь готового PDF попадает в artifacts, откуда бот
    берёт файл для отправки пользователю."""

    def record(result):
        message, path = result
        if path and artifacts is not None and path not in artifacts:
            artifacts.append(path)
        return message

    return {
        "get_book_pdf": lambda args: record(
            get_book_pdf(args.get("title", ""), args.get("lang"))
        ),
        "find_book": lambda args: find_book(args.get("title", ""), args.get("lang")),
    }
