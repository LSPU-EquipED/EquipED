from server.modules.documents.ingestion import pipeline


def test_canonical_page_offsets_use_identical_join_recipe(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "_extract_pages",
        lambda _path, **_: [
            pipeline.ExtractedPage(page_number=1, text=" first ", is_ocr=False),
            pipeline.ExtractedPage(page_number=2, text="  ", is_ocr=True),
            pipeline.ExtractedPage(page_number=3, text="second\nline ", is_ocr=True),
        ],
    )
    text, ranges = pipeline.prepare_canonical_source_pages("synthetic.pdf")
    assert text == pipeline.prepare_canonical_source("synthetic.pdf")
    assert text == "first\n\nsecond\nline"
    assert tuple(text[start:end] for _, start, end in ranges) == (
        "first",
        "",
        "second\nline",
    )
    assert tuple(page for page, _, _ in ranges) == (1, 2, 3)
    _, page_map = pipeline.prepare_canonical_source_with_page_map("synthetic.pdf")
    assert page_map[1]["is_ocr"]
    assert "blank_or_no_canonical_text" in page_map[1]["warnings"]
