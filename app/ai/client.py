import json
import re
from difflib import SequenceMatcher
from typing import Any

from google import genai

from app.core.config import get_settings


class AIProcessor:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = None
        if settings.google_genai_api_key:
            self.client = genai.Client(api_key=settings.google_genai_api_key)

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[Any],
        input_schema: type[Any],
    ) -> Any:
        _ = input_schema
        _ = output_schema
        _ = prompt

        return {
            "status": "not_implemented",
            "message": (
                "AI scaffolding is ready. Add model, schema, and "
                "prompt logic later."
            ),
        }

    def choose_theme_name(
        self,
        title: str,
        description: str,
        themes: list[str],
    ) -> str:
        if not self.client:
            return "Разное"

        themes_text = "\n".join(f"- {name}" for name in themes)
        prompt = (
            "Определи тему короткого видео YouTube. "
            "Темы трактуй как теги рубрик канала, чтобы было понятно, "
            "о чем в целом публикуется контент. "
            "Выбери одну существующую тему из списка, если подходит. "
            "Если подходящей нет, предложи новую тему. "
            "Старайся не придумывать лишние новые темы."
            "Отвечай JSON-объектом: "
            '{"theme_name": "..."}. '
            "Название темы должно быть на русском и коротким. "
            "Избегай слишком общих тем вроде: Покушение, Новости, "
            "Политика. Нужны предметные теги, например: "
            "Диверсии Украины. "
            "В большинстве случаев тема из одного слова — плохое решение."
            "Если похожая тема уже есть в списке, используй именно ее "
            "без перефразирования.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            "Существующие темы:\n"
            f"{themes_text if themes_text else '- (пусто)'}"
        )

        try:
            response = self.client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
            )
            print(response)
            parsed = self._parse_theme_name(getattr(response, "text", ""))
            if parsed:
                return self._reconcile_with_existing(parsed, themes)
        except Exception:
            return "Разное"

        return "Разное"

    def _reconcile_with_existing(
        self,
        chosen_name: str,
        themes: list[str],
    ) -> str:
        if not themes:
            return chosen_name

        normalized_chosen = self._normalize_theme_name(chosen_name)
        for name in themes:
            if self._normalize_theme_name(name) == normalized_chosen:
                return name

        best_score = 0.0
        best_match = ""
        for name in themes:
            score = SequenceMatcher(
                a=normalized_chosen,
                b=self._normalize_theme_name(name),
            ).ratio()
            if score > best_score:
                best_score = score
                best_match = name

        if best_score >= 0.9:
            return best_match

        return chosen_name

    def _normalize_theme_name(self, value: str) -> str:
        compact = " ".join(value.strip().split())
        return compact.casefold()

    def _parse_theme_name(self, value: str) -> str:
        if not value:
            return ""

        cleaned = value.strip()
        cleaned = cleaned.removeprefix("```json")
        cleaned = cleaned.removesuffix("```")
        cleaned = cleaned.strip()

        try:
            payload = json.loads(cleaned)
            name = str(payload.get("theme_name", "")).strip()
        except Exception:
            return ""

        if not name:
            return ""
        if not re.search(r"[А-Яа-яЁё]", name):
            return "Разное"
        return name
