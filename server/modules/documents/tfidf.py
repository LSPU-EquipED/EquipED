"""TF-IDF utilities for Layer 1 corpus weighting."""

from __future__ import annotations

from .exceptions import ExtractionFailedError
from .schemas import DocumentChunkData


def compute_tfidf_corpus(slm_chunks: list[DocumentChunkData]) -> dict[str, float]:
    """Compute corpus-level term weights across SLM chunks."""

    corpus_texts = [chunk.text for chunk in slm_chunks if chunk.text.strip()]
    if not corpus_texts:
        return {}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ModuleNotFoundError as exc:
        raise ExtractionFailedError("scikit-learn is not installed") from exc

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words=None,
    )
    vectorizer.fit(corpus_texts)
    terms = vectorizer.get_feature_names_out()
    return {
        term: float(weight)
        for term, weight in zip(terms, vectorizer.idf_, strict=False)
    }


__all__ = ["compute_tfidf_corpus"]
