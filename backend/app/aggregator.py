"""Final error aggregation step.

Writes the collected checkpoint errors to a plain-text report file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.artifact_writer import write_artifact

if TYPE_CHECKING:
    from app.doc_models import DocData


def _build_summary(doc_data: "DocData", *, is_partial: bool = False) -> str:
    lines = ["=" * 40, "СВОДКА ПРОВЕРКИ", "=" * 40]
    if is_partial:
        lines.append(
            "Проверка прервана. В отчёте ниже — только разделы, обработанные до остановки.",
        )
    sections = doc_data.sections
    if sections:
        first = sections[0].number or sections[0].title
        last = sections[-1].number or sections[-1].title
        if first == last:
            lines.append(f"Диапазон выборки (документ): раздел {first}")
        else:
            lines.append(f"Диапазон выборки (документ): {first} – {last}")
    else:
        lines.append("Разделы: не определены")
    lines += ["=" * 40, ""]
    return "\n".join(lines)


def _build_prompt_block(check_prompt: str | None) -> str:
    if not check_prompt:
        return ""
    lines = ["=" * 40, "ПРОМПТ ПРОВЕРКИ", "=" * 40, check_prompt.strip(), "=" * 40, ""]
    return "\n".join(lines)


def aggregate(
    all_errors: list[dict],
    result_path: str,
    doc_data: "DocData | None" = None,
    *,
    is_partial: bool = False,
    check_prompt: str | None = None,
) -> None:
    """Write *all_errors* to *result_path* as a plain-text report."""
    preamble = _build_summary(doc_data, is_partial=is_partial) if doc_data is not None else ""
    prompt_block = _build_prompt_block(check_prompt)

    if not all_errors:
        _write(result_path, preamble + prompt_block + "Ошибок не найдено. Документ соответствует проверенным критериям.")
        return

    lines = ["=" * 40, "ДЕТАЛИ ПРОВЕРКИ", "=" * 40, ""]
    for item in all_errors:
        lines.append(f"[{item['checkpoint']}] {item['location']}")
        lines.append(item["error"])
        lines += ["", "---", ""]

    _write(result_path, preamble + prompt_block + "\n".join(lines))


def _write(path: str, text: str) -> None:
    write_artifact(path, text)


def write_summary(summary_text: str, path: str) -> None:
    _write(path, summary_text)
