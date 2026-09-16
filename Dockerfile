# Окружение для Telegram-бота (bot.py). CLI-версия (agent.py) запускается на хосте.
#
# Образ должен содержать три вещи, которых нет в стандартном python-образе:
#   * Node.js + глобальный @modelcontextprotocol/server-filesystem — mcp_client.py
#     запускает его подпроцессом, без него у бота отпадают все инструменты fs__*;
#   * шрифт с кириллицей — pdftools.py иначе молча откатывается на Helvetica;
#   * ca-certificates — весь инференс и веб-инструменты работают по HTTPS.

# Node берём из официального образа, чтобы не тянуть NodeSource в apt.
FROM node:22-bookworm-slim AS node

# Python 3.13, а не 3.14 как на хосте: под 3.13 есть готовые wheels для lxml,
# reportlab и numpy, поэтому компилятор в образе не нужен. Код 3.14 не требует.
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# fonts-dejavu-core даёт DejaVuSans.ttf и DejaVuSans-Bold.ttf в
# /usr/share/fonts/truetype/dejavu — именно там их ищет pdftools.FONT_DIRS.
# libstdc++6 нужен бинарнику node, скопированному ниже.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      fonts-dejavu-core \
      libstdc++6 \
 && rm -rf /var/lib/apt/lists/*

# Переносим рантайм Node вместе с самим npm.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/ /usr/local/lib/node_modules/
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && node -v && npm -v

# MCP-сервер ставим именно здесь, а не копируем готовым из стадии node:
# npm раскладывает зависимости глобального пакета по своей схеме, и ручное
# копирование её ломает. Заодно npm остаётся в образе — на него опирается
# основной путь резолвинга в mcp_client._resolve_command (`npm root -g`).
RUN npm install -g @modelcontextprotocol/server-filesystem \
 && test -f "$(npm root -g)/@modelcontextprotocol/server-filesystem/dist/index.js"

WORKDIR /app

# Зависимости отдельным слоем до кода, чтобы правки в .py не сбрасывали кэш.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# logger.py открывает FileHandler на /app/agent.log при импорте, поэтому
# рабочая директория обязана быть доступна на запись пользователю контейнера.
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /app/data /app/workspace \
 && chown -R app:app /app

USER app

# Портов не открываем: aiogram работает исходящим long polling, ничего не слушает.
CMD ["python", "bot.py"]
