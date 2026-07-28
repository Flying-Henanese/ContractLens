from io import BytesIO

from pypdf import PdfReader, PdfWriter

from pdf_parser.ingestion.pdf import iter_pdf_pages


def test_iter_pdf_pages_returns_standalone_pdfs(tmp_path):
    source = tmp_path / "three-pages.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=595, height=842)
    with source.open("wb") as stream:
        writer.write(stream)

    pages = list(iter_pdf_pages(source))

    assert [page_num for page_num, _ in pages] == [1, 2, 3]
    assert all(len(PdfReader(BytesIO(data)).pages) == 1 for _, data in pages)
