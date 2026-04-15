"""Final error aggregation step.

Takes the raw list of errors collected from all checkpoints, sends them to
the AI to merge duplicates and produce a structured report, and writes the
result to a plain-text file.
"""

from __future__ import annotations

import ai_client

_SYSTEM_PROMPT = """Ты эксперт по проверке технических отчётов.
Тебе передан список ошибок, найденных в документе несколькими независимыми проверками.
Каждая ошибка содержит:
  - checkpoint: название выполненной проверки
  - location: место в документе (страница, параграф, подпись и т.д.)
  - error: описание найденной проблемы

Твоя задача:
1. Объединить дублирующиеся или очень похожие ошибки в одну запись.
2. Сгруппировать ошибки по типам (стиль и изложение / физические величины / ссылки).
3. Внутри каждой группы отсортировать по месту в документе.
4. Сформулировать итоговый отчёт в виде чёткого структурированного текста на русском языке.
5. В конце добавить краткое резюме: общее количество уникальных проблем по каждой группе.

Отвечай только на русском языке. Не включай в ответ XML, JSON или Markdown-разметку — только читаемый текст.
"""


def aggregate(all_errors: list[dict], result_path: str) -> None:
    """Aggregate *all_errors* via AI and write the report to *result_path*.

    Each element of *all_errors* must have keys:
        checkpoint (str), location (str), error (str)
    """
    if not all_errors:
        report = "Ошибок не найдено. Документ соответствует проверенным критериям."
        _write(result_path, report)
        return

    lines = []
    for item in all_errors:
        lines.append(
            f"[{item['checkpoint']}] {item['location']}\n{item['error']}\n"
        )
    errors_text = "\n---\n".join(lines)

    report = ai_client.aggregate_errors(errors_text, _SYSTEM_PROMPT)
    _write(result_path, report)


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
