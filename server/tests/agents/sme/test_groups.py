from __future__ import annotations

from server.modules.agents.sme.grouped import groups
from server.modules.agents.sme.oracle.registry import REGISTERED_CODES


def test_group_codes_cover_every_registered_code_exactly_once():
    seen = []
    for codes in groups.GROUP_CODES.values():
        seen.extend(codes)
    assert sorted(seen) == sorted(REGISTERED_CODES)
    assert len(seen) == len(set(seen))


def test_code_to_group_is_the_exact_inverse_of_group_codes():
    for group_name, codes in groups.GROUP_CODES.items():
        for code in codes:
            assert groups.CODE_TO_GROUP[code] == group_name


def test_group_names_matches_group_codes_keys():
    assert set(groups.GROUP_NAMES) == set(groups.GROUP_CODES)


def test_assessment_alignment_group_codes():
    assert groups.GROUP_CODES["assessment_alignment"] == ("A-02", "A-05")


def test_task_execution_group_codes():
    assert groups.GROUP_CODES["task_execution"] == (
        "A-01",
        "A-03",
        "OP-02",
        "OP-03",
        "OP-05",
    )


def test_document_wide_group_codes():
    assert groups.GROUP_CODES["document_wide"] == ("OP-01", "OP-04", "A-04")


def test_slice_for_group_rejects_unknown_group():
    import pytest

    with pytest.raises(KeyError):
        groups.slice_for_group("not-a-group", "text")
