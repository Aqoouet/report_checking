"""Final error aggregation step.

Takes the raw list of errors collected from all checkpoints, sends them to
the AI to merge duplicates and produce a structured report, and writes the
result to a plain-text file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ai_client

if TYPE_CHECKING:
    from doc_parser import DocData

_SYSTEM_PROMPT = """Ты эксперт по проверке технических отчётов.
Тебе передан список ошибок, найденных в документе.

Напиши ОДИН краткий абзац на русском языке: сколько и каких категорий ошибок найдено
(стиль / физические величины / ссылки на таблицы и рисунки), без перечисления деталей.
Максимум 200 токенов. Только читаемый текст, без Markdown и XML.
"""


def _build_summary(doc_data: "DocData") -> str:
    """Build a static preamble with checked sections, tables and figures."""
    lines = ["=" * 40, "СВОДКА ПРОВЕРКИ", "=" * 40]

    sections = doc_data.sections
    if sections:
        first = sections[0].number
        last = sections[-1].number
        if doc_data.fmt == "pdf":
            if first == last:
                lines.append(f"Проверены страницы: {first}")
            else:
                lines.append(f"Проверены страницы: {first} – {last}")
        else:
            if first == last:
                lines.append(f"Проверены разделы: {first}")
            else:
                lines.append(f"Проверены разделы: {first} – {last}")
    else:
        lines.append("Разделы: не определены")

    fig_table = doc_data.fig_table_dict
    tables = [e for e in fig_table if e.label.lower().startswith("таблица")]
    figures = [e for e in fig_table if e.label.lower().startswith("рисунок")]

    if tables:
        first_t = tables[0].label
        last_t = tables[-1].label
        lines.append(
            f"Таблиц найдено: {len(tables)}  (с {first_t!r} по {last_t!r})"
        )
    else:
        lines.append("Таблиц найдено: 0")

    if figures:
        first_f = figures[0].label
        last_f = figures[-1].label
        lines.append(
            f"Рисунков найдено: {len(figures)}  (с {first_f!r} по {last_f!r})"
        )
    else:
        lines.append("Рисунков найдено: 0")

    lines.append("=" * 40)
    lines.append("")
    return "\n".join(lines)


def aggregate(all_errors: list[dict], result_path: str, doc_data: "DocData | None" = None) -> None:
    """Aggregate *all_errors* via AI and write the report to *result_path*.

    Each element of *all_errors* must have keys:
        checkpoint (str), location (str), error (str)

    If *doc_data* is provided a static summary preamble is prepended to the
    report listing the checked sections, tables and figures.
    """
    preamble = _build_summary(doc_data) if doc_data is not None else ""

    if not all_errors:
        report = preamble + "Ошибок не найдено. Документ соответствует проверенным критериям."
        _write(result_path, report)
        return

    lines = []
    for item in all_errors:
        lines.append(
            f"[{item['checkpoint']}] {item['location']}\n{item['error']}\n"
        )
    errors_text = "\n---\n".join(lines)

    ai_report = ai_client.aggregate_errors(errors_text, _SYSTEM_PROMPT)

    details_lines = ["=" * 40, "ДЕТАЛИ ПРОВЕРКИ", "=" * 40, ""]
    for item in all_errors:
        details_lines.append(f"[{item['checkpoint']}] {item['location']}")
        details_lines.append(item["error"])
        details_lines.append("")
        details_lines.append("---")
        details_lines.append("")
    details_section = "\n".join(details_lines)

    summary_block = "=" * 40 + "\nИТОГОВОЕ РЕЗЮМЕ\n" + "=" * 40 + "\n" + ai_report + "\n\n"
    _write(result_path, preamble + summary_block + details_section)


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
