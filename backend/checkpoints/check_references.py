"""Checkpoint 3 — Cross-references to tables and figures.

Uses the pre-built ``doc_data.fig_table_dict`` (populated by ``doc_parser``)
so that the dictionary is constructed once for the whole document regardless of
any range filter applied to sections.

For each table/figure entry the AI is asked to assess:
1. Whether there is at least one mention in the text.
2. Whether the context of each mention is semantically compatible with the caption.

Progress updates set ``checkpoint_sub_name`` to the current table/figure label so
the GUI can show it together with the AI response for the previous item.
"""

from __future__ import annotations

import ai_client
import jobs as job_store
from jobs import JobCancelledError
from checkpoints.base import BaseCheckpoint
from doc_parser import DocData, FigTableEntry

_AI_PROMPT = """Ты эксперт по проверке технических отчётов.
Тебе передана подпись к таблице или рисунку и список фрагментов текста, которые на неё ссылаются.

Поля входных данных:
  - "caption": полный текст подписи (например «Таблица 3.1-2 — Результаты испытаний»)
  - "section": раздел где находится подпись
  - "mentions": список объектов {context, section_number} — контекст каждого упоминания

Твоя задача:
1. Если mentions пуст — ошибка: объект не упомянут в тексте ни разу.
2. Для каждого упоминания оцени: соответствует ли контекст смыслу подписи? Если явно не соответствует — ошибка.

Ответ: краткий текст на русском языке. Начни с «Ошибок не найдено.» если всё в порядке.
Иначе — перечисли проблемы, начиная каждую с тире.
Максимум 300 токенов.
"""


class CheckReferences(BaseCheckpoint):
    name = "Перекрёстные ссылки на таблицы и рисунки"
    short_name = "Ссылки на таблицы и рисунки"
    supported_formats = ["docx", "pdf"]

    def run(self, doc_data: DocData, *, job_id: str | None = None) -> list[dict]:
        entries = doc_data.fig_table_dict
        if not entries:
            return []

        errors: list[dict] = []
        total = len(entries)

        for i, entry in enumerate(entries):
            sub_name = entry.label

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.checkpoint_sub_current = i + 1
                    job.checkpoint_sub_total = total
                    job.checkpoint_sub_location = entry.label
                    job.checkpoint_sub_name = sub_name
                    job_store.update_job(job)

            payload_text = _format_entry(entry)
            result = ai_client.check_text_chunk(payload_text, _AI_PROMPT)

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.previous_result = result.strip() if result else ""
                    job_store.update_job(job)
                    if job.cancelled:
                        raise JobCancelledError()

            if result and "ошибок не найдено" not in result.lower():
                errors.append({
                    "location": entry.label,
                    "error": result.strip(),
                })

        return errors


def _format_entry(entry: FigTableEntry) -> str:
    lines = [
        f"caption: {entry.caption}",
        f"section: {entry.section_number}",
        f"mentions ({len(entry.mentions)}):",
    ]
    for m in entry.mentions:
        lines.append(f"  - раздел {m.section_number}: {m.context[:300]}")
    return "\n".join(lines)
