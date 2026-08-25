"""Local OCR processing orchestration and startup validation using pytesseract."""

from __future__ import annotations

import logging
import math
import os
import subprocess
import threading
from dataclasses import dataclass
from typing import Any

import fitz
import pytesseract
from PIL import Image
from server.core.config import Settings
from server.modules.documents.exceptions import (
    OcrFailedError,
    OcrLimitExceededError,
    OcrUnavailableError,
)

logger = logging.getLogger(__name__)

# Conservative visual blank classification constants
_BLANK_MIN_LUMINANCE: int = 245
_BLANK_WHITE_PIXEL_RATIO: float = 0.999
_BLANK_ABSOLUTE_MIN_LUMINANCE: int = 230
_BLANK_MAX_LUMINANCE_SPREAD: int = 15

# Global validation cache
_ocr_validation_cache: dict[str, Any] | None = None
# Concurrency Semaphore for OCR execution
_ocr_semaphore: threading.Semaphore | None = None
_ocr_semaphore_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class OcrPageOutcome:
    text: str
    is_blank: bool


def _is_visually_blank_image(image: Image.Image) -> bool:
    """Classify whether a PIL image is visually blank using histogram evidence.

    Classifies as blank ONLY when all strict visual evidence agrees:
    1. The absolute minimum luminance is >= _BLANK_ABSOLUTE_MIN_LUMINANCE.
    2. The luminance spread (max - min) is <= _BLANK_MAX_LUMINANCE_SPREAD.
    3. The fraction of near-white pixels (>= _BLANK_MIN_LUMINANCE) is >=
       _BLANK_WHITE_PIXEL_RATIO.

    Ambiguous pages are classified as nonblank (returns False).
    """
    total_pixels = image.width * image.height
    if total_pixels == 0:
        return True

    gray = image.convert("L")
    min_val, max_val = gray.getextrema()
    if min_val < _BLANK_ABSOLUTE_MIN_LUMINANCE:
        return False
    if (max_val - min_val) > _BLANK_MAX_LUMINANCE_SPREAD:
        return False

    hist = gray.histogram()
    white_pixels = sum(hist[_BLANK_MIN_LUMINANCE:])
    if (white_pixels / total_pixels) < _BLANK_WHITE_PIXEL_RATIO:
        return False

    return True


def get_ocr_semaphore(settings: Settings) -> threading.Semaphore:
    global _ocr_semaphore
    with _ocr_semaphore_lock:
        if _ocr_semaphore is None:
            _ocr_semaphore = threading.Semaphore(settings.ocr_concurrency)
        return _ocr_semaphore


def clear_ocr_validation_cache() -> None:
    global _ocr_validation_cache
    _ocr_validation_cache = None


def _tessdata_dir_config(settings: Settings) -> str:
    # pytesseract runs `config` through shlex.split() in POSIX mode, which
    # treats backslash as an escape character and silently mangles Windows
    # paths (e.g. "C:\Users\..." -> "C:Users..."). Forward slashes avoid
    # that entirely and Tesseract/Windows both accept them; a quoted path
    # isn't an option either way since shlex would still see the escaped
    # backslashes inside the quotes.
    if settings.tessdata_prefix:
        posix_path = settings.tessdata_prefix.replace("\\", "/")
        return f"--tessdata-dir {posix_path}"
    return ""


def validate_ocr_installation(settings: Settings) -> dict[str, Any]:
    """Validate Tesseract installation and presence of configured language packs.

    Performs check once and caches the result.
    """
    global _ocr_validation_cache
    if _ocr_validation_cache is not None:
        return _ocr_validation_cache

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages(config=_tessdata_dir_config(settings))

        required_langs = [
            lang_code.strip()
            for lang_code in settings.tesseract_lang.split("+")
            if lang_code.strip()
        ]
        missing_langs = [lang for lang in required_langs if lang not in langs]

        if missing_langs:
            missing_langs_str = ", ".join(missing_langs)
            err_detail = (
                f"Tesseract missing required language pack(s): {missing_langs_str}"
            )
            result = {
                "ready": False,
                "detail": err_detail,
                "version": str(version),
                "available_languages": langs,
            }
        else:
            result = {
                "ready": True,
                "detail": "Tesseract OCR is available and fully configured",
                "version": str(version),
                "available_languages": langs,
            }
    except pytesseract.TesseractNotFoundError as exc:
        result = {
            "ready": False,
            "detail": f"Tesseract executable not found: {exc}",
            "version": None,
            "available_languages": [],
        }
    except Exception as exc:
        result = {
            "ready": False,
            "detail": f"Tesseract initialization failed: {str(exc)}",
            "version": None,
            "available_languages": [],
        }

    _ocr_validation_cache = result
    return result


def perform_ocr_on_page(page: fitz.Page, settings: Settings) -> OcrPageOutcome:
    """Perform OCR on a single PDF page using PyMuPDF, Pillow, and Pytesseract.

    Respects limits on resolution, pixels, concurrency, and time.
    """
    # 1. Validate page dimensions before probing or allocating OCR resources.
    if (
        not math.isfinite(page.rect.width)
        or not math.isfinite(page.rect.height)
        or page.rect.width <= 0
        or page.rect.height <= 0
    ):
        raise OcrFailedError(
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )

    estimated_width = page.rect.width * settings.ocr_dpi / 72
    estimated_height = page.rect.height * settings.ocr_dpi / 72
    estimated_pixels = estimated_width * estimated_height
    if not math.isfinite(estimated_pixels):
        raise OcrLimitExceededError(
            "Estimated page pixel count exceeds processing limits."
        )

    # 2. Validate Tesseract availability.
    ocr_status = validate_ocr_installation(settings)
    if not ocr_status["ready"]:
        raise OcrUnavailableError(f"OCR engine is unavailable: {ocr_status['detail']}")

    # 3. Compute effective DPI within the pixel budget.
    effective_dpi = settings.ocr_dpi
    if estimated_pixels > settings.ocr_max_pixels:
        scale = math.sqrt(settings.ocr_max_pixels / estimated_pixels)
        effective_dpi = max(1, int(settings.ocr_dpi * scale * 0.99))
        logger.info(
            "Adapting OCR DPI for oversized page: "
            "requested_dpi=%d, effective_dpi=%d, width=%.1f, height=%.1f",
            settings.ocr_dpi,
            effective_dpi,
            page.rect.width,
            page.rect.height,
        )

    # 4. Rasterize page (alpha=False and RGB colorspace)
    try:
        pixmap = page.get_pixmap(dpi=effective_dpi, colorspace=fitz.csRGB, alpha=False)
    except Exception as exc:
        logger.exception("Failed to rasterize page during OCR")
        err_msg = (
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )
        raise OcrFailedError(err_msg) from exc

    # 4. Check actual pixel bounds
    actual_pixels = pixmap.width * pixmap.height
    if actual_pixels > settings.ocr_max_pixels:
        raise OcrLimitExceededError(
            f"Actual page pixel count ({actual_pixels}) exceeds the maximum "
            f"limit of {settings.ocr_max_pixels} pixels."
        )

    # 5. Convert to PIL Image
    try:
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    except Exception as exc:
        logger.exception("Failed to convert page pixmap to PIL Image during OCR")
        err_msg = (
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )
        raise OcrFailedError(err_msg) from exc

    # 6. Conservative visual blank classification (rasterize once, reuse PIL image)
    if _is_visually_blank_image(image):
        return OcrPageOutcome(text="", is_blank=True)

    # 7. Acquire semaphore
    semaphore = get_ocr_semaphore(settings)
    acquired = semaphore.acquire(timeout=settings.ocr_semaphore_timeout_seconds)
    if not acquired:
        raise OcrLimitExceededError(
            f"Timeout of {settings.ocr_semaphore_timeout_seconds} seconds exceeded "
            f"while waiting to acquire OCR concurrency worker slot."
        )

    # 8. Run pytesseract with OMP_THREAD_LIMIT=1 and timeout bounds
    original_omp_thread_limit = os.environ.get("OMP_THREAD_LIMIT")
    os.environ["OMP_THREAD_LIMIT"] = "1"

    try:
        text = pytesseract.image_to_string(
            image,
            lang=settings.tesseract_lang,
            timeout=settings.ocr_timeout_seconds,
            config=_tessdata_dir_config(settings),
        )
    except (subprocess.TimeoutExpired, TimeoutError) as exc:
        logger.warning(
            "Tesseract execution timed out",
            extra={"timeout": settings.ocr_timeout_seconds},
        )
        raise OcrLimitExceededError("OCR execution timed out") from exc
    except RuntimeError as exc:
        # pytesseract wraps timeouts as RuntimeError("Tesseract processing timeout")
        if "timeout" in str(exc).lower():
            logger.warning(
                "Tesseract execution reported timeout via RuntimeError",
                extra={"error": str(exc)},
            )
            raise OcrLimitExceededError("OCR execution timed out") from exc
        logger.error(f"Tesseract execution failed: {exc}", exc_info=True)
        raise OcrFailedError(f"OCR execution failed: {exc}") from exc
    except Exception as exc:
        logger.error(f"Tesseract execution failed unexpectedly: {exc}", exc_info=True)
        raise OcrFailedError(f"OCR execution failed: {exc}") from exc
    finally:
        # Restore environment variable
        if original_omp_thread_limit is not None:
            os.environ["OMP_THREAD_LIMIT"] = original_omp_thread_limit
        else:
            os.environ.pop("OMP_THREAD_LIMIT", None)
        semaphore.release()

    cleaned_text = text.strip()
    if any(c.isalnum() for c in cleaned_text):
        return OcrPageOutcome(text=cleaned_text, is_blank=False)

    return OcrPageOutcome(text="", is_blank=False)
