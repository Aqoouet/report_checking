from dataclasses import dataclass
from typing import Optional
import fitz  # PyMuPDF


@dataclass
class PageData:
    page_num: int       # 0-based index
    page_label: int     # 1-based number shown to user
    text: str
    annot_x: float
    annot_y: float


def parse_pages(pdf_path: str, pages_to_check: set[int]) -> list[PageData]:
    """
    Extract text and annotation coordinates from specified pages.
    pages_to_check: set of 1-based page numbers.
    """
    result: list[PageData] = []
    doc = fitz.open(pdf_path)

    for page_label in sorted(pages_to_check):
        page_num = page_label - 1  # convert to 0-based
        if page_num < 0 or page_num >= len(doc):
            continue

        page = doc[page_num]
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

        text_blocks = [b for b in blocks if b[6] == 0 and b[4].strip()]

        full_text = "\n".join(b[4].strip() for b in text_blocks)

        if not full_text.strip():
            continue

        if text_blocks:
            annot_x = text_blocks[0][0]
            annot_y = text_blocks[0][1]
        else:
            annot_x, annot_y = 20.0, 20.0

        result.append(PageData(
            page_num=page_num,
            page_label=page_label,
            text=full_text,
            annot_x=annot_x,
            annot_y=annot_y,
        ))

    doc.close()
    return result


def parse_page_range(pages_str: str) -> set[int]:
    """
    Parse a page range string like '5-30' or '1, 3, 5-10' into a set of 1-based page numbers.
    """
    pages: set[int] = set()
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start, end = int(bounds[0].strip()), int(bounds[1].strip())
                pages.update(range(start, end + 1))
            except ValueError:
                pass
        else:
            try:
                pages.add(int(part))
            except ValueError:
                pass
    return pages
