import pytest
from server.modules.documents import paths
from server.modules.documents.exceptions import DocumentsError


def test_resolve_document_pdf_path_accepts_owned_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / "owned.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    monkeypatch.setattr(paths, "UPLOAD_ROOT", tmp_path)

    assert paths.resolve_document_pdf_path(pdf) == pdf.resolve()


@pytest.mark.parametrize(
    "value", [None, "", "missing.pdf", "file.txt", "../escape.pdf"]
)
def test_resolve_document_pdf_path_rejects_invalid_sources(
    tmp_path, monkeypatch, value
):
    monkeypatch.setattr(paths, "UPLOAD_ROOT", tmp_path)
    with pytest.raises(DocumentsError, match="^invalid document source$") as error:
        paths.resolve_document_pdf_path(value)
    assert str(tmp_path) not in str(error.value)


def test_resolve_document_pdf_path_rejects_absolute_outside_and_non_file(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(paths, "UPLOAD_ROOT", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"pdf")
    with pytest.raises(DocumentsError):
        paths.resolve_document_pdf_path(outside)
    with pytest.raises(DocumentsError):
        paths.resolve_document_pdf_path(tmp_path / "uploads")


def test_resolve_document_pdf_path_rejects_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"pdf")
    (root / "linked.pdf").symlink_to(outside)
    monkeypatch.setattr(paths, "UPLOAD_ROOT", root)

    with pytest.raises(DocumentsError, match="^invalid document source$"):
        paths.resolve_document_pdf_path(root / "linked.pdf")
