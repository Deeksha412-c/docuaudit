import fitz  # PyMuPDF
from dataclasses import dataclass

@dataclass
class PageInfo:
    page_num: int
    text: str

def ingest_invoice(pdf_path: str) -> list[PageInfo]:
    doc = fitz.open(pdf_path)
    return [PageInfo(i, page.get_text()) for i, page in enumerate(doc)]

def full_text(pages: list[PageInfo]) -> str:
    return "\n".join(p.text for p in pages)