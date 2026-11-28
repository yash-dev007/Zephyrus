"""Keep imported PDFs on the ordinary document prompt path."""

from src.pdf_form_doc import is_form_backed_document, render_plain_pdf_markdown


UPLOAD_ID = "0123456789abcdef0123456789abcdef"


def test_plain_pdf_import_is_not_a_fillable_form():
    content = render_plain_pdf_markdown(UPLOAD_ID, "Report", "Some extracted text")
    assert not is_form_backed_document(content)


def test_valid_form_marker_is_a_fillable_form():
    assert is_form_backed_document(f'<!-- pdf_form_source upload_id="{UPLOAD_ID}" fields="2" -->')


def test_invalid_form_marker_is_not_a_fillable_form():
    assert not is_form_backed_document('<!-- pdf_form_source upload_id="../other.pdf" -->')
