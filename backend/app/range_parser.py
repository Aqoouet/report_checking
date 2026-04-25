"""Rule-based section range parser — no AI, pure regex.

Parses free-form strings such as "3.1", "раздел 3.1–3.4", "3.1, 3.3–3.5"
and returns a structured dict compatible with the AI-based validator output.
"""

from __future__ import annotations

import re


def parse_range_script(range_text: str) -> dict:
    """Parse *range_text* using regex rules only (no AI call).

    Returns:
        {
            "valid": bool,
            "type": "sections",
            "items": [{"start": str, "end": str}, ...],
            "display": str,
            "suggestion": str,
        }
    """
    text = range_text.strip()
    if not text:
        return {"valid": True, "type": "sections", "items": [], "display": "", "suggestion": ""}

    # Strip known keywords
    cleaned = re.sub(
        r'\b(разделы?|разд\.?|раздела?|section|глав[аыь]?|от|до|по)\b',
        ' ', text, flags=re.IGNORECASE,
    )

    # Normalize decimal comma → dot ("5,1" → "5.1")
    cleaned = re.sub(r'(\d+),(\d+)', lambda m: f"{m.group(1)}.{m.group(2)}", cleaned)
    cleaned = cleaned.strip()

    num = r'\d+(?:\.\d+)*'
    range_sep = r'\s*[-–—]\s*'

    token_pat = rf'(?:{num}){range_sep}(?:{num})|(?:{num})'
    tokens = re.findall(token_pat, cleaned)

    leftover = re.sub(token_pat, '', cleaned).replace(',', '').strip()
    if leftover or not tokens:
        return {
            "valid": False,
            "type": "sections",
            "items": [],
            "display": "",
            "suggestion": "Could not parse the range. Example: 3.1 or 3.2-3.5",
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

    label = "Раздел" if len(items) == 1 and items[0]["start"] == items[0]["end"] else "Разделы"
    display = f"{label}: {', '.join(_fmt(i) for i in items)}"

    return {"valid": True, "type": "sections", "items": items, "display": display, "suggestion": ""}
