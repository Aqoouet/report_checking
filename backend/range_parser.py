"""Rule-based range parser — no AI, pure regex.

Parses free-form range strings such as "раздел 3.1–3.4" or "страница 5, 7"
and returns a structured dict compatible with the AI-based validator.
"""

from __future__ import annotations

import re


def parse_range_script(range_text: str, file_type: str) -> dict:
    """Parse *range_text* using regex rules only (no AI call).

    Returns the same shape as ``ai_client.validate_range()``:
        {
            "valid": bool,
            "type": "sections" | "pages" | "",
            "items": [{"start": str, "end": str}, ...],
            "display": str,
            "suggestion": str,
        }
    """
    text = range_text.strip()
    if not text:
        return {"valid": True, "type": "", "items": [], "display": "", "suggestion": ""}

    lower = text.lower()
    is_pdf = file_type.lower() == "pdf"

    # Override type by explicit keyword
    if re.search(r'\b(страниц[аыь]?|стр\.?|page)\b', lower):
        is_pdf = True
    elif re.search(r'\b(разделы?|разд\.?|section|глав[аыь]?)\b', lower):
        is_pdf = False

    kind = "pages" if is_pdf else "sections"
    label_single = "Страница" if is_pdf else "Раздел"
    label_multi = "Страницы" if is_pdf else "Разделы"
    example = "страница 5" if is_pdf else "раздел 5.1"

    # Strip known keywords and extra punctuation
    cleaned = re.sub(
        r'\b(разделы?|разд\.?|страниц[аыь]?|стр\.?|от|до|по|глав[аыь]?|section|pages?)\b',
        ' ', text, flags=re.IGNORECASE,
    )

    # For sections: normalize decimal comma → dot ("5,1" → "5.1")
    if not is_pdf:
        cleaned = re.sub(r'(\d+),(\d+)', lambda m: f"{m.group(1)}.{m.group(2)}", cleaned)

    cleaned = cleaned.strip()

    num = r'\d+(?:\.\d+)*' if not is_pdf else r'\d+'
    range_sep = r'\s*[-–—]\s*'

    # Tokenize: find all range-or-single tokens
    token_pat = rf'(?:{num}){range_sep}(?:{num})|(?:{num})'
    tokens = re.findall(token_pat, cleaned)

    # Check nothing unrecognised remains after removing tokens
    leftover = re.sub(token_pat, '', cleaned).replace(',', '').strip()
    if leftover or not tokens:
        return {
            "valid": False,
            "type": kind,
            "items": [],
            "display": "",
            "suggestion": f"Не удалось распознать. Пример: {example}",
        }

    items = []
    for tok in tokens:
        m = re.match(rf'^({num}){range_sep}({num})$', tok.strip())
        if m:
            items.append({"start": m.group(1), "end": m.group(2)})
        else:
            items.append({"start": tok.strip(), "end": tok.strip()})

    def _fmt(item: dict) -> str:
        return item["start"] if item["start"] == item["end"] else f"{item['start']}–{item['end']}"

    label = label_single if len(items) == 1 and items[0]["start"] == items[0]["end"] else label_multi
    display = f"{label}: {', '.join(_fmt(i) for i in items)}"

    return {"valid": True, "type": kind, "items": items, "display": display, "suggestion": ""}
