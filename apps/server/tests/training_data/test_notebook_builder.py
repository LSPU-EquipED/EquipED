"""Tests for filling a job's links into the notebook template."""

from __future__ import annotations

import json

import pytest
from server.modules.training_data.exceptions import NotebookTemplateError
from server.modules.training_data.notebook import TEMPLATE_PATH, build_job_notebook

DOWNLOAD = "https://app.example/api/v1/admin/training-data/jobs/j/download?token=aaa"
UPLOAD = "https://app.example/api/v1/admin/training-data/jobs/j/adapter?token=bbb"


def _links_cell(text: str) -> str:
    return "".join(json.loads(text)["cells"][1]["source"])


def test_fills_both_links_and_leaves_no_placeholder():
    cell = _links_cell(build_job_notebook(DOWNLOAD, UPLOAD))
    assert f'DOWNLOAD_URL = "{DOWNLOAD}"' in cell
    assert f'UPLOAD_URL = "{UPLOAD}"' in cell
    # the template's own guard text mentions "PASTE_", so check the placeholders
    assert "PASTE_DOWNLOAD_URL_HERE" not in cell
    assert "PASTE_UPLOAD_URL_HERE" not in cell


def test_every_other_cell_is_unchanged():
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    built = json.loads(build_job_notebook(DOWNLOAD, UPLOAD))
    assert len(built["cells"]) == len(template["cells"])
    for index, (a, b) in enumerate(zip(template["cells"], built["cells"])):
        if index != 1:
            assert a == b
    assert built["metadata"] == template["metadata"]


def test_output_is_valid_json_with_the_same_notebook_format():
    built = json.loads(build_job_notebook(DOWNLOAD, UPLOAD))
    assert built["nbformat"] == 4


def test_urls_with_quotes_are_escaped_not_injected():
    nasty = 'https://x/y?token="; import os #'
    cell = _links_cell(build_job_notebook(nasty, UPLOAD))
    compile(cell, "cell", "exec")  # still valid Python
    assert '\\"; import os #' in cell


def _write_template(tmp_path, source: str):
    path = tmp_path / "t.ipynb"
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": ["x"]},
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source.splitlines(keepends=True),
            },
        ],
    }
    path.write_text(json.dumps(nb), encoding="utf-8")
    return path


def test_missing_placeholder_fails_loudly(tmp_path):
    path = _write_template(tmp_path, 'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"\n')
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, template_path=path)


def test_duplicated_placeholder_fails_loudly(tmp_path):
    line = 'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"\n'
    path = _write_template(
        tmp_path, line + line + 'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"\n'
    )
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, template_path=path)


def test_unreadable_template_raises_template_error(tmp_path):
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, template_path=tmp_path / "missing.ipynb")


STATUS = "https://app.example/api/v1/admin/training-data/jobs/j/status?token=ccc"


def test_status_link_is_filled_when_given():
    cell = _links_cell(build_job_notebook(DOWNLOAD, UPLOAD, status_url=STATUS))
    assert f'STATUS_URL = "{STATUS}"' in cell


def test_status_link_stays_empty_when_not_given():
    cell = _links_cell(build_job_notebook(DOWNLOAD, UPLOAD))
    assert 'STATUS_URL = ""' in cell


def test_status_url_without_template_line_fails_loudly(tmp_path):
    path = _write_template(
        tmp_path,
        'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"\n'
        'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"\n',
    )
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, status_url=STATUS, template_path=path)
