"""Память агента: история диалога и профиль пользователя.

Состояние вынесено в MemoryStore с собственной директорией, чтобы у каждого
пользователя Telegram была своя память, а CLI продолжал работать с файлами
в корне проекта.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MAX_HISTORY_MESSAGES = 200


class MemoryStore:
    """История диалога и профиль в одной директории."""

    def __init__(self, dir_path):
        self.dir_path = dir_path
        self.history_path = os.path.join(dir_path, "memory_history.json")
        self.profile_path = os.path.join(dir_path, "profile.json")

    def _ensure_dir(self):
        os.makedirs(self.dir_path, exist_ok=True)

    # --- история диалога ---

    def load_history(self):
        if not os.path.isfile(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_history(self, messages):
        try:
            self._ensure_dir()
            trimmed = messages[-MAX_HISTORY_MESSAGES:]
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(trimmed, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear_history(self):
        if os.path.isfile(self.history_path):
            os.remove(self.history_path)

    # --- профиль (долговременные факты) ---

    def load_profile(self):
        if not os.path.isfile(self.profile_path):
            return {}
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_profile(self, profile):
        try:
            self._ensure_dir()
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def profile_as_prompt(self):
        """Профиль в виде текста для вставки в системный промпт."""
        profile = self.load_profile()
        if not profile:
            return ""
        lines = "\n".join(f"- {k}: {v}" for k, v in profile.items())
        return f"\n\nИзвестные факты о пользователе (долговременная память):\n{lines}"

    def remember(self, key, value):
        if not key:
            return "Ошибка: key не должен быть пустым"
        profile = self.load_profile()
        profile[key] = value
        self._save_profile(profile)
        return f"Запомнил: {key} = {value}"

    def recall_facts(self, key=None):
        profile = self.load_profile()
        if not profile:
            return "Память пуста"
        if key:
            if key in profile:
                return f"{key} = {profile[key]}"
            return f"Факт с ключом '{key}' не найден"
        return "\n".join(f"{k} = {v}" for k, v in profile.items())

    def forget_fact(self, key):
        profile = self.load_profile()
        if key in profile:
            del profile[key]
            self._save_profile(profile)
            return f"Забыл: {key}"
        return f"Факт с ключом '{key}' не найден"

    def tool_functions(self):
        """Инструменты памяти, замкнутые на этот store — так вызов remember
        всегда пишет в память нужного пользователя."""
        return {
            "remember": lambda args: self.remember(args.get("key", ""), args.get("value", "")),
            "recall_facts": lambda args: self.recall_facts(args.get("key")),
            "forget_fact": lambda args: self.forget_fact(args.get("key", "")),
        }


def store_for_user(user_id):
    """Память отдельного пользователя Telegram."""
    return MemoryStore(os.path.join(BASE_DIR, "data", str(user_id)))


# Память CLI-версии — файлы в корне проекта (сохраняет уже накопленные данные).
cli_store = MemoryStore(BASE_DIR)


# Схемы от пользователя не зависят, поэтому остаются модульными.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Сохранить факт о пользователе в долговременную память (profile.json, сохраняется между запусками).",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Ключ факта, например 'имя_пользователя'"},
                    "value": {"type": "string", "description": "Значение факта"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_facts",
            "description": "Вспомнить сохранённый факт по ключу или все факты, если ключ не указан.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Ключ факта (опционально)"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "Удалить сохранённый факт по ключу.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Ключ факта для удаления"}},
                "required": ["key"],
            },
        },
    },
]
