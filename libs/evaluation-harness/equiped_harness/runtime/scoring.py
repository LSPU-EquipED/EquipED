"""Generic score validation helpers."""


def validate_score_band(score: int) -> int:
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
        raise ValueError("criterion score out of bounds")
    return score


__all__ = ["validate_score_band"]
