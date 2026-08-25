import stat
import subprocess
import uuid
from unittest.mock import patch

import pytesseract
import pytest
from PIL import Image
from server.core.config import Settings
from server.modules.documents.exceptions import (
    ExtractionFailedError,
    OcrFailedError,
    OcrLimitExceededError,
)
from server.modules.documents.ingestion.ocr import (
    _is_visually_blank_image,
    clear_ocr_validation_cache,
    perform_ocr_on_page,
    validate_ocr_installation,
)
from server.modules.documents.ingestion.pipeline import (
    _extract_pages,
    ingest_document,
)


class MockRect:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height


class MockPage:
    def __init__(
        self,
        text: str,
        width: float = 612.0,
        height: float = 792.0,
        image: Image.Image | None = None,
    ):
        self.text = text
        self.rect = MockRect(width, height)
        self.image = image
        self.last_dpi: int | None = None

    def get_text(self) -> str:
        return self.text

    def get_pixmap(self, dpi: int = 200, colorspace: any = None, alpha: bool = False):
        self.last_dpi = dpi
        if self.image is not None:
            rgb = self.image.convert("RGB")

            class ImagePixmap:
                def __init__(self, img: Image.Image):
                    self.width = img.width
                    self.height = img.height
                    self.samples = img.tobytes()

            return ImagePixmap(rgb)

        page_width = self.rect.width
        page_height = self.rect.height

        class MockPixmap:
            def __init__(self):
                self.width = int(page_width * dpi / 72)
                self.height = int(page_height * dpi / 72)
                self.samples = b"\x00" * (self.width * self.height * 3)

        return MockPixmap()


class MockDoc:
    def __init__(self, pages: list[MockPage]):
        self.pages = pages
        self.is_encrypted = False

    def __iter__(self):
        return iter(self.pages)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture(autouse=True)
def reset_ocr_cache():
    clear_ocr_validation_cache()
    yield
    clear_ocr_validation_cache()


def test_ocr_validation_success() -> None:
    settings = Settings(tesseract_lang="eng+fil")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng", "fil", "osd"]),
    ):
        result = validate_ocr_installation(settings)
        assert result["ready"] is True
        assert "available_languages" in result
        assert result["version"] == "4.0.0"


def test_ocr_validation_missing_lang() -> None:
    settings = Settings(tesseract_lang="eng+fil")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        result = validate_ocr_installation(settings)
        assert result["ready"] is False
        assert "missing required language pack" in result["detail"]


def test_ocr_validation_executable_missing() -> None:
    settings = Settings(tesseract_lang="eng+fil")
    with patch(
        "pytesseract.get_tesseract_version",
        side_effect=pytesseract.TesseractNotFoundError(),
    ):
        result = validate_ocr_installation(settings)
        assert result["ready"] is False
        assert "not found" in result["detail"]


def test_perform_ocr_on_page_success() -> None:
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="", image=Image.new("RGB", (100, 100), (30, 30, 30)))
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="Extracted text content"),
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert outcome.is_blank is False
        assert outcome.text == "Extracted text content"


def test_perform_ocr_on_page_pure_white_blank() -> None:
    settings = Settings(tesseract_lang="eng")
    page = MockPage(text="", image=Image.new("RGB", (100, 100), (255, 255, 255)))
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string") as mock_tess,
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert outcome.is_blank is True
        assert outcome.text == ""
        mock_tess.assert_not_called()


def test_perform_ocr_on_page_off_white_blank() -> None:
    settings = Settings(tesseract_lang="eng")
    page = MockPage(text="", image=Image.new("RGB", (100, 100), (250, 250, 250)))
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string") as mock_tess,
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert outcome.is_blank is True
        assert outcome.text == ""
        mock_tess.assert_not_called()


def test_visual_classifier_boundaries() -> None:
    # Pure white & off-white conservative blanks
    pure_white = Image.new("RGB", (100, 100), (255, 255, 255))
    assert _is_visually_blank_image(pure_white) is True
    off_white = Image.new("RGB", (100, 100), (250, 250, 250))
    assert _is_visually_blank_image(off_white) is True

    # Light photograph
    photo = Image.new("RGB", (100, 100), (220, 220, 220))
    assert _is_visually_blank_image(photo) is False

    # Dark page
    dark = Image.new("RGB", (100, 100), (30, 30, 30))
    assert _is_visually_blank_image(dark) is False

    # Single visible line on white page
    line_img = Image.new("RGB", (100, 100), (255, 255, 255))
    for y in range(100):
        line_img.putpixel((50, y), (0, 0, 0))
    assert _is_visually_blank_image(line_img) is False

    # Edge shadow on white page
    shadow_img = Image.new("RGB", (100, 100), (255, 255, 255))
    for x in range(5):
        for y in range(100):
            shadow_img.putpixel((x, y), (180, 180, 180))
    assert _is_visually_blank_image(shadow_img) is False


def test_perform_ocr_on_page_nonblank_symbol_only_ocr() -> None:
    settings = Settings(tesseract_lang="eng")
    page = MockPage(text="", image=Image.new("RGB", (100, 100), (30, 30, 30)))
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="--- \n ... !!! @#$"),
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert outcome.is_blank is False
        assert outcome.text == ""


def test_perform_ocr_on_page_timeout() -> None:
    settings = Settings(tesseract_lang="eng", ocr_timeout_seconds=20)
    page = MockPage(text="")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            side_effect=subprocess.TimeoutExpired("tesseract", 20),
        ),
    ):
        with pytest.raises(OcrLimitExceededError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "timed out" in str(exc_info.value)


def test_perform_ocr_on_page_standard_letter_preserves_dpi() -> None:
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="", width=612.0, height=792.0)
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="Letter page text"),
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert page.last_dpi == 200
        assert outcome.is_blank is False
        assert outcome.text == "Letter page text"


def test_perform_ocr_on_page_adaptive_downscaling_oversized_page() -> None:
    # 2400x3200 pt at 200 DPI estimates ~59.2M pixels (> 8M cap)
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="", width=2400.0, height=3200.0)
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Photographed oversized syllabus page",
        ),
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert page.last_dpi is not None
        assert page.last_dpi < 200
        # Verify rendered dimensions stay strictly within 8M pixels
        raster_width = int(page.rect.width * page.last_dpi / 72)
        raster_height = int(page.rect.height * page.last_dpi / 72)
        assert raster_width * raster_height <= settings.ocr_max_pixels
        assert outcome.is_blank is False
        assert outcome.text == "Photographed oversized syllabus page"


def test_perform_ocr_on_page_pathological_actual_pixel_limit_exceeded() -> None:
    # Even at effective_dpi=1, 10000x10000 pt renders 138x138 = 19044 pixels > 1000 cap
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=1000)
    page = MockPage(text="", width=10000.0, height=10000.0)
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        with pytest.raises(OcrLimitExceededError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "Actual page pixel count" in str(exc_info.value)


def test_perform_ocr_on_page_nan_dimensions_fails_closed() -> None:
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="", width=float("nan"), height=792.0)
    with (
        patch(
            "pytesseract.get_tesseract_version", return_value="4.0.0"
        ) as mock_version,
        patch("pytesseract.get_languages", return_value=["eng"]) as mock_languages,
        patch.object(page, "get_pixmap") as mock_pixmap,
        patch("pytesseract.image_to_string") as mock_tess,
    ):
        with pytest.raises(OcrFailedError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "could not be read" in str(exc_info.value)
        assert "nan" not in str(exc_info.value).lower()
        mock_version.assert_not_called()
        mock_languages.assert_not_called()
        mock_pixmap.assert_not_called()
        mock_tess.assert_not_called()


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (float("inf"), 792.0),
        (612.0, float("inf")),
        (float("-inf"), 792.0),
        (0.0, 792.0),
        (612.0, 0.0),
        (-612.0, 792.0),
    ],
)
def test_perform_ocr_on_page_infinite_or_zero_dimensions_fails_closed(
    width: float, height: float
) -> None:
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="", width=width, height=height)
    with (
        patch(
            "pytesseract.get_tesseract_version", return_value="4.0.0"
        ) as mock_version,
        patch("pytesseract.get_languages", return_value=["eng"]) as mock_languages,
        patch.object(page, "get_pixmap") as mock_pixmap,
        patch("pytesseract.image_to_string") as mock_tess,
    ):
        with pytest.raises(OcrFailedError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "could not be read" in str(exc_info.value)
        assert "inf" not in str(exc_info.value).lower()
        mock_version.assert_not_called()
        mock_languages.assert_not_called()
        mock_pixmap.assert_not_called()
        mock_tess.assert_not_called()


def test_perform_ocr_on_page_enormous_overflow_fails_closed() -> None:
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="", width=1e200, height=1e200)
    with (
        patch(
            "pytesseract.get_tesseract_version", return_value="4.0.0"
        ) as mock_version,
        patch("pytesseract.get_languages", return_value=["eng"]) as mock_languages,
        patch.object(page, "get_pixmap") as mock_pixmap,
        patch("pytesseract.image_to_string") as mock_tess,
    ):
        with pytest.raises(OcrLimitExceededError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "processing limits" in str(exc_info.value)
        assert "1e" not in str(exc_info.value).lower()
        mock_version.assert_not_called()
        mock_languages.assert_not_called()
        mock_pixmap.assert_not_called()
        mock_tess.assert_not_called()


def test_ingest_document_scanned_success(monkeypatch) -> None:
    # Scanned document has no meaningful text
    page1 = MockPage(text="Weak overlay")  # len < 100, fails heuristic
    mock_doc = MockDoc([page1])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Actual OCR text content that is long enough",
        ),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        assert len(chunks) > 0
        assert chunks[0].is_ocr is True
        assert "Actual OCR text content" in chunks[0].text


def test_ingest_document_mixed_success(monkeypatch) -> None:
    # Mixed: Page 1 has meaningful selectable text, Page 2 needs OCR
    page1 = MockPage(
        text=(
            "This is page one text. It is selectable and definitely long "
            "enough to pass our heuristic text check of 100 characters "
            "and eight words."
        )
    )
    page2 = MockPage(text="Gibberish")  # needs OCR

    mock_doc = MockDoc([page1, page2])
    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Page two OCR text that is also long enough",
        ),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        # Verify chunks exist for both pages
        pages_extracted = {c.page_number for c in chunks}
        assert pages_extracted == {1, 2}

        chunk_ocr_flags = {c.page_number: c.is_ocr for c in chunks}
        assert chunk_ocr_flags[1] is False
        assert chunk_ocr_flags[2] is True


def test_ingest_document_blank_neighbor_and_readable_ocr(monkeypatch) -> None:
    # Page 1 is visually blank (pure white), Page 2 is nonblank image needing OCR
    page1 = MockPage(text="", image=Image.new("RGB", (100, 100), (255, 255, 255)))
    page2 = MockPage(
        text="Weak overlay",
        image=Image.new("RGB", (100, 100), (30, 30, 30)),
    )
    mock_doc = MockDoc([page1, page2])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Actual readable OCR text content from page two",
        ),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        assert len(chunks) > 0
        assert all(c.page_number == 2 for c in chunks)
        assert chunks[0].is_ocr is True
        assert "Actual readable OCR text" in chunks[0].text


def test_ingest_document_readable_photograph_emits_is_ocr_chunk(monkeypatch) -> None:
    # Photograph needing OCR
    photo_img = Image.new("RGB", (100, 100), (220, 220, 220))
    page1 = MockPage(text="", image=photo_img)
    mock_doc = MockDoc([page1])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Photographed syllabus contents for course",
        ),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        assert len(chunks) > 0
        assert chunks[0].page_number == 1
        assert chunks[0].is_ocr is True
        assert "Photographed syllabus contents" in chunks[0].text


def test_ingest_document_nonblank_symbol_only_ocr_fails_closed(monkeypatch) -> None:
    # Nonblank page where OCR returns only punctuation/symbols
    page1 = MockPage(text="", image=Image.new("RGB", (100, 100), (30, 30, 30)))
    mock_doc = MockDoc([page1])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="--- \n ... !!! @#$"),
    ):
        with pytest.raises(
            ExtractionFailedError, match="OCR extraction produced no text for page 1"
        ):
            ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))


def test_ingest_document_all_blank_pages_returns_empty(monkeypatch) -> None:
    # All pages visually blank
    page1 = MockPage(text="", image=Image.new("RGB", (100, 100), (255, 255, 255)))
    page2 = MockPage(text="", image=Image.new("RGB", (100, 100), (250, 250, 250)))
    mock_doc = MockDoc([page1, page2])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        assert chunks == []


def test_extract_pages_mixed_readable_blank_unreadable_fails_wholly(
    monkeypatch,
) -> None:
    # Page 1: Selectable text
    page1 = MockPage(
        text=(
            "This is page one text. It is selectable and definitely long "
            "enough to pass our heuristic text check of 100 characters "
            "and eight words."
        )
    )
    # Page 2: Visually blank (skipped)
    page2 = MockPage(text="", image=Image.new("RGB", (100, 100), (255, 255, 255)))
    # Page 3: Nonblank, but OCR returns empty (unreadable)
    page3 = MockPage(
        text="Needs OCR",
        image=Image.new("RGB", (100, 100), (30, 30, 30)),
    )

    mock_doc = MockDoc([page1, page2, page3])
    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=3)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="   "),
    ):
        with pytest.raises(
            ExtractionFailedError, match="OCR extraction produced no text for page 3"
        ):
            _extract_pages("dummy.pdf")


def test_ingest_document_blank_page(monkeypatch) -> None:
    # Nonblank page contains no selectable text, and OCR returns blank -> fails closed
    page1 = MockPage(text="", image=Image.new("RGB", (100, 100), (30, 30, 30)))
    mock_doc = MockDoc([page1])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="   "),
    ):
        with pytest.raises(
            ExtractionFailedError, match="OCR extraction produced no text for page 1"
        ):
            ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))


def test_extract_pages_mixed_ocr_empty_page_fails_closed(monkeypatch) -> None:
    # Page 1 has meaningful selectable text,
    # Page 2 is nonblank needing OCR and returns blank
    page1 = MockPage(
        text=(
            "This is page one text. It is selectable and definitely long "
            "enough to pass our heuristic text check of 100 characters "
            "and eight words."
        )
    )
    page2 = MockPage(
        text="Gibberish",
        image=Image.new("RGB", (100, 100), (30, 30, 30)),
    )

    mock_doc = MockDoc([page1, page2])
    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="   "),
    ):
        with pytest.raises(
            ExtractionFailedError, match="OCR extraction produced no text for page 2"
        ):
            _extract_pages("dummy.pdf")


def test_ingest_document_ocr_limit_exceeded(monkeypatch) -> None:
    # Max OCR pages is 1, but we have 2 pages needing OCR
    page1 = MockPage(text="needs ocr")
    page2 = MockPage(text="needs ocr too")
    mock_doc = MockDoc([page1, page2])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=1)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline.get_settings", lambda: settings
    )

    with pytest.raises(OcrLimitExceededError) as exc_info:
        ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
    assert "exceeds the maximum limit" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Blocker 1: Readiness sanitization tests
# ---------------------------------------------------------------------------


def test_ready_route_sanitization(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from server.core.config import Settings
    from server.main import create_app

    settings = Settings(
        database_url=None,
        session_cookie_name="equiped_session",
        session_ttl_hours=24,
        tesseract_lang="eng+fil",
        environment="production",  # Make OCR required
    )

    monkeypatch.setattr("server.main.get_settings", lambda: settings)

    # Force failure with a missing language pack to test detail sanitization
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):  # missing fil
        app = create_app()
        client = TestClient(app)

        resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"

        ocr_check = data["checks"]["ocr"]
        assert ocr_check["ready"] is False
        # Detail must not expose packs, paths, or exception text.
        assert "missing required language pack(s)" not in ocr_check["detail"]
        assert ocr_check["detail"] == (
            "OCR engine is unavailable or missing required language packs."
        )


def test_ready_route_sanitization_unexpected_error(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from server.core.config import Settings
    from server.main import create_app

    settings = Settings(
        database_url=None,
        session_cookie_name="equiped_session",
        session_ttl_hours=24,
        tesseract_lang="eng+fil",
        environment="production",
    )

    monkeypatch.setattr("server.main.get_settings", lambda: settings)

    # Force an unexpected exception to leak
    with patch(
        "server.modules.documents.ingestion.ocr.validate_ocr_installation",
        side_effect=PermissionError("/usr/bin/tesseract permission denied"),
    ):
        app = create_app()
        client = TestClient(app)

        resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        ocr_check = data["checks"]["ocr"]
        assert ocr_check["ready"] is False
        # Detail must not leak executable path or PermissionError details
        assert "/usr/bin" not in ocr_check["detail"]
        assert "permission denied" not in ocr_check["detail"]
        assert "PermissionError" not in ocr_check["detail"]
        assert ocr_check["detail"] == "OCR engine is unavailable or misconfigured."


# ---------------------------------------------------------------------------
# Blocker 2: Rasterization/Pillow sanitization tests
# ---------------------------------------------------------------------------


def test_rasterization_failure_raises_clean_ocr_failed_error() -> None:
    from server.modules.documents.exceptions import OcrFailedError

    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)

    # Create mock page that throws an exception during get_pixmap
    class FaultyPage(MockPage):
        def get_pixmap(
            self, dpi: int = 200, colorspace: any = None, alpha: bool = False
        ):
            raise ValueError(
                "Critical rendering context allocation failure in fitz wrapper"
            )

    page = FaultyPage(text="")

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        with pytest.raises(OcrFailedError) as exc_info:
            perform_ocr_on_page(page, settings)

        # Verify no raw exception info is interpolated
        assert "Critical rendering" not in str(exc_info.value)
        assert "allocation failure" not in str(exc_info.value)
        assert "ValueError" not in str(exc_info.value)
        assert str(exc_info.value) == (
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )


def test_pillow_conversion_failure_raises_clean_ocr_failed_error() -> None:
    from server.modules.documents.exceptions import OcrFailedError

    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)

    # Mock Pillow's Image.frombytes to throw an error
    page = MockPage(text="")

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "PIL.Image.frombytes",
            side_effect=RuntimeError(
                "Pillow buffer underflow or invalid mode conversion"
            ),
        ),
    ):
        with pytest.raises(OcrFailedError) as exc_info:
            perform_ocr_on_page(page, settings)

        # Verify no raw exception info is interpolated
        assert "Pillow buffer" not in str(exc_info.value)
        assert "underflow" not in str(exc_info.value)
        assert "RuntimeError" not in str(exc_info.value)
        assert str(exc_info.value) == (
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )


# ---------------------------------------------------------------------------
# Blocker 3: Upload cleanup and recovery tests
# ---------------------------------------------------------------------------


def test_cleanup_failed_upload_retries_and_cleanup_pending(
    monkeypatch, db_session
) -> None:
    import time
    from io import BytesIO

    from fastapi import UploadFile
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import create_document

    # Ingestion must only begin after a durable PENDING upload intent exists.
    def fail_ingestion_after_asserting_intent(*args, **kwargs):
        intent = (
            db_session.query(Document).filter_by(title="Faulty Cleaned Document").one()
        )
        assert intent.processing_status == "PENDING"
        raise OcrLimitExceededError("Forced limit exceeded")

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document",
        fail_ingestion_after_asserting_intent,
    )

    # Force unlink to raise OSError to exercise cleanup failure.
    unlinks_attempted = 0

    def faulty_unlink(self):
        nonlocal unlinks_attempted
        unlinks_attempted += 1
        raise OSError("Permission denied / file locked")

    monkeypatch.setattr("pathlib.Path.unlink", faulty_unlink)

    # Speed up sleep in retries
    monkeypatch.setattr(time, "sleep", lambda x: None)

    upload = UploadFile(filename="faulty.pdf", file=BytesIO(b"%PDF-1.4\nfaulty"))

    response = create_document(
        file=upload,
        source_type="slm",
        title="Faulty Cleaned Document",
        course_title=None,
        lesson_title=None,
        program="BSCS",
        uploaded_by=uuid.uuid4(),
        db=db_session,
    )

    # Deletion should have retried 3 times
    assert unlinks_attempted == 3
    # Status should be CLEANUP_PENDING
    assert response.processing_status == "CLEANUP_PENDING"

    # Confirm it is saved in DB with status CLEANUP_PENDING and no chunks are written
    db_doc = db_session.get(Document, response.document_id)
    assert db_doc is not None
    assert db_doc.processing_status == "CLEANUP_PENDING"
    assert (
        db_session.query(DocumentChunk)
        .filter_by(document_id=response.document_id)
        .count()
        == 0
    )


def test_recover_cleanup_pending_documents_success(monkeypatch, db_session) -> None:
    from pathlib import Path

    from server.modules.documents.journaling import recover_cleanup_pending_documents
    from server.modules.documents.models import Document

    doc_id = uuid.uuid4()
    temp_file = Path("/tmp/test_cleanup_pending_file.pdf")
    temp_file.write_bytes(b"dummy")

    # Seed a document in CLEANUP_PENDING status pointing to a file that exists
    db_doc = Document(
        document_id=doc_id,
        title="Cleanup Pending Doc",
        source_type="slm",
        file_path=str(temp_file),
        uploaded_by=uuid.uuid4(),
        processing_status="CLEANUP_PENDING",
    )
    db_session.add(db_doc)
    db_session.commit()

    assert temp_file.exists()

    # Run recovery (file path exists and is deletable)
    recovered = recover_cleanup_pending_documents(lambda: db_session)
    assert recovered == 1

    # Status should be updated to FAILED and file deleted
    db_doc_recovered = db_session.get(Document, doc_id)
    assert db_doc_recovered.processing_status == "FAILED"
    assert not temp_file.exists()


def test_recover_pending_document_upload_success(monkeypatch, db_session) -> None:
    from pathlib import Path

    from server.modules.documents.journaling import recover_cleanup_pending_documents
    from server.modules.documents.models import Document

    doc_id = uuid.uuid4()
    temp_file = Path("/tmp/test_pending_upload_file.pdf")
    temp_file.write_bytes(b"dummy")

    db_session.add(
        Document(
            document_id=doc_id,
            title="Interrupted Upload",
            source_type="slm",
            file_path=str(temp_file),
            uploaded_by=uuid.uuid4(),
            processing_status="PENDING",
        )
    )
    db_session.commit()

    assert recover_cleanup_pending_documents(lambda: db_session) == 1
    assert db_session.get(Document, doc_id).processing_status == "FAILED"
    assert not temp_file.exists()


def test_recover_no_database_upload_journal_removes_tracked_file(
    monkeypatch, tmp_path
) -> None:
    from server.modules.documents import journaling, paths

    upload_root = tmp_path / "uploads"
    journal_root = upload_root / ".upload-journal"
    file_path = upload_root / "interrupted.pdf"
    upload_root.mkdir()
    file_path.write_bytes(b"dummy")

    monkeypatch.setattr(paths, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(paths, "UPLOAD_JOURNAL_ROOT", journal_root)

    marker = journaling._create_upload_marker(uuid.uuid4(), file_path)

    assert journaling.recover_no_database_upload_journal() == 1
    assert not file_path.exists()
    assert not marker.exists()


def test_no_database_upload_marker_fsyncs_directory_entry(
    monkeypatch, tmp_path
) -> None:
    from server.modules.documents import journaling, paths

    upload_root = tmp_path / "uploads"
    journal_root = upload_root / ".upload-journal"
    file_path = upload_root / "interrupted.pdf"
    upload_root.mkdir()

    monkeypatch.setattr(paths, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(paths, "UPLOAD_JOURNAL_ROOT", journal_root)

    original_fsync = journaling.os.fsync
    fsynced_directories: list[bool] = []

    def record_fsync(descriptor: int) -> None:
        fsynced_directories.append(
            stat.S_ISDIR(journaling.os.fstat(descriptor).st_mode)
        )
        original_fsync(descriptor)

    monkeypatch.setattr(journaling.os, "fsync", record_fsync)

    journaling._create_upload_marker(uuid.uuid4(), file_path)

    assert any(fsynced_directories)
