import fitz  # PyMuPDF
from pdf_parser import PageData


def write_annotations(
    src_pdf_path: str,
    dst_pdf_path: str,
    page_comments: list[tuple[PageData, str]],
) -> None:
    """
    Open src_pdf_path, add a sticky note annotation for each (PageData, comment) pair,
    and save the result to dst_pdf_path.
    """
    doc = fitz.open(src_pdf_path)

    for page_data, comment in page_comments:
        page = doc[page_data.page_num]

        point = fitz.Point(page_data.annot_x, page_data.annot_y)

        annot = page.add_text_annot(point, comment, icon="Note")
        annot.set_info(title="AI Review")
        annot.update()

    doc.save(dst_pdf_path, garbage=4, deflate=True)
    doc.close()
