"""Генерация PDF из текста (с поддержкой кириллицы) и конвертация текстовых файлов."""

import html
import os
import re

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Куда складываем результаты — та же песочница, что видят файловые инструменты.
OUTPUT_DIR = os.path.join(BASE_DIR, "workspace")

# Кириллица требует TTF-шрифта: встроенные шрифты PDF её не покрывают.
FONT_CANDIDATES = [
    ("DejaVuSans", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    ("Arial", "arial.ttf", "arialbd.ttf"),
    ("Verdana", "verdana.ttf", "verdanab.ttf"),
]
FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts",
    "/Library/Fonts",
]

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json",
    ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".py", ".js", ".ts",
    ".html", ".htm", ".css", ".sql", ".sh", ".bat", ".c", ".h", ".cpp",
    ".java", ".go", ".rs", ".rb", ".php", ".tex", "",
}

MAX_INPUT_CHARS = 3_000_000

_font_cache = {}


def _find_font_file(filename):
    for d in FONT_DIRS:
        path = os.path.join(d, filename)
        if os.path.isfile(path):
            return path
        # На Windows регистр в имени файла бывает разный (ARIAL.TTF).
        if os.path.isdir(d):
            for name in os.listdir(d):
                if name.lower() == filename.lower():
                    return os.path.join(d, name)
    return None


def register_font():
    """Зарегистрировать TTF-шрифт с кириллицей. Возвращает (regular, bold)."""
    if _font_cache:
        return _font_cache["regular"], _font_cache["bold"]

    for name, regular_file, bold_file in FONT_CANDIDATES:
        regular_path = _find_font_file(regular_file)
        if not regular_path:
            continue
        pdfmetrics.registerFont(TTFont(name, regular_path))
        bold_name = name
        bold_path = _find_font_file(bold_file)
        if bold_path:
            bold_name = f"{name}-Bold"
            pdfmetrics.registerFont(TTFont(bold_name, bold_path))
        _font_cache["regular"] = name
        _font_cache["bold"] = bold_name
        return name, bold_name

    # Последний рубеж: встроенный шрифт (латиница будет читаться, кириллица — нет).
    _font_cache["regular"] = "Helvetica"
    _font_cache["bold"] = "Helvetica-Bold"
    return "Helvetica", "Helvetica-Bold"


def safe_filename(name, default="document"):
    name = re.sub(r"[^\w\s\-.()]+", "", name or "", flags=re.UNICODE).strip()
    name = re.sub(r"\s+", "_", name)
    return (name or default)[:80]


def _paragraphs(text):
    """Разбить текст на абзацы, сохраняя пустые строки как разделители."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", "    ")
    blocks = re.split(r"\n\s*\n", text)
    out = []
    for block in blocks:
        block = block.strip()
        if block:
            out.append(block)
    return out or [""]


def text_to_pdf(text, title=None, out_path=None, author=None):
    """Собрать PDF из текста. Возвращает путь к файлу."""
    regular, bold = register_font()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not out_path:
        out_path = os.path.join(OUTPUT_DIR, safe_filename(title) + ".pdf")
    elif not os.path.isabs(out_path):
        out_path = os.path.join(OUTPUT_DIR, out_path)
    os.makedirs(os.path.dirname(out_path) or OUTPUT_DIR, exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title or "Document",
        author=author or "local agent",
    )

    body = ParagraphStyle(
        "body",
        fontName=regular,
        fontSize=11,
        leading=15.5,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        firstLineIndent=8 * mm,
    )
    heading = ParagraphStyle(
        "heading", fontName=bold, fontSize=15, leading=20, spaceBefore=12, spaceAfter=8
    )
    title_style = ParagraphStyle(
        "title", fontName=bold, fontSize=22, leading=28, spaceAfter=10, alignment=1
    )

    story = []
    if title:
        story.append(Paragraph(html.escape(title), title_style))
        if author:
            story.append(Paragraph(html.escape(author), heading))
        story.append(Spacer(1, 8 * mm))

    for block in _paragraphs(text):
        if block == "\x0c":
            story.append(PageBreak())
            continue
        # Markdown-заголовки и короткие строки вида «Глава I» оформляем крупнее.
        is_md_heading = block.startswith("#")
        looks_like_heading = (
            len(block) < 70
            and "\n" not in block
            and re.match(r"^(#{1,6}\s+|\s*(Глава|ГЛАВА|Часть|ЧАСТЬ|Chapter|CHAPTER|Part|PART)\b)", block)
        )
        cleaned = re.sub(r"^#{1,6}\s+", "", block) if is_md_heading else block
        safe = html.escape(cleaned).replace("\n", "<br/>")
        story.append(Paragraph(safe, heading if (is_md_heading or looks_like_heading) else body))

    doc.build(story)
    return out_path


def convert_file_to_pdf(path, title=None):
    """Конвертировать текстовый файл в PDF.

    Возвращает (сообщение_для_модели, путь_к_файлу | None) — путь нужен боту,
    чтобы отправить готовый документ пользователю.
    """
    if not path:
        return "Ошибка: не указан путь к файлу", None

    candidate = path if os.path.isabs(path) else os.path.join(OUTPUT_DIR, path)
    if not os.path.isfile(candidate):
        alt = os.path.join(BASE_DIR, path)
        if os.path.isfile(alt):
            candidate = alt
        else:
            return f"Ошибка: файл не найден: {path}", None

    ext = os.path.splitext(candidate)[1].lower()
    if ext == ".pdf":
        return f"Файл уже в формате PDF: {candidate}", candidate
    if ext not in TEXT_EXTENSIONS:
        return (
            f"Ошибка: {ext or 'файл без расширения'} не похож на текстовый формат. "
            "Поддерживаются txt, md, csv, json, html, исходный код и подобные."
        ), None

    try:
        with open(candidate, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_INPUT_CHARS)
    except Exception as e:
        return f"Ошибка чтения файла: {e}", None

    if not text.strip():
        return "Ошибка: файл пуст", None

    if ext in (".html", ".htm"):
        try:
            from bs4 import BeautifulSoup

            text = BeautifulSoup(text, "lxml").get_text("\n", strip=True)
        except Exception:
            pass

    stem = os.path.splitext(os.path.basename(candidate))[0]
    out_path = os.path.join(OUTPUT_DIR, safe_filename(stem) + ".pdf")
    try:
        text_to_pdf(text, title=title or stem, out_path=out_path)
    except Exception as e:
        return f"Ошибка генерации PDF: {e}", None

    size_kb = os.path.getsize(out_path) // 1024
    return (
        f"PDF готов: {out_path} ({size_kb} КБ). Файл будет отправлен пользователю.",
        out_path,
    )


def make_pdf_from_text(text, title=None):
    """Собрать PDF из переданного текста. Возвращает (сообщение, путь | None)."""
    if not text or not str(text).strip():
        return "Ошибка: текст пуст", None
    try:
        path = text_to_pdf(str(text), title=title or "Документ")
    except Exception as e:
        return f"Ошибка генерации PDF: {e}", None
    size_kb = os.path.getsize(path) // 1024
    return (
        f"PDF готов: {path} ({size_kb} КБ). Файл будет отправлен пользователю.",
        path,
    )


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "convert_file_to_pdf",
            "description": (
                "Конвертировать текстовый файл в PDF и отправить пользователю. "
                "Поддерживает txt, md, csv, json, html, исходный код и другие "
                "текстовые форматы. Кириллица поддерживается. "
                "Путь можно указать относительно рабочей папки."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к текстовому файлу"},
                    "title": {
                        "type": "string",
                        "description": "Заголовок на титуле PDF (по умолчанию имя файла)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_pdf_from_text",
            "description": (
                "Собрать PDF из переданного текста и отправить пользователю. "
                "Используй, когда нужно оформить в PDF текст, который ты написал "
                "сам или получил из другого инструмента."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст документа"},
                    "title": {"type": "string", "description": "Заголовок документа"},
                },
                "required": ["text"],
            },
        },
    },
]


def tool_functions(artifacts=None):
    """Инструменты PDF. Пути созданных файлов складываются в artifacts —
    оттуда бот берёт их, чтобы отправить пользователю."""

    def record(result):
        message, path = result
        if path and artifacts is not None and path not in artifacts:
            artifacts.append(path)
        return message

    return {
        "convert_file_to_pdf": lambda args: record(
            convert_file_to_pdf(args.get("path", ""), args.get("title"))
        ),
        "make_pdf_from_text": lambda args: record(
            make_pdf_from_text(args.get("text", ""), args.get("title"))
        ),
    }
