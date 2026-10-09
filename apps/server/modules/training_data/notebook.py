"""apps/server/modules/training_data/notebook.py"""

from __future__ import annotations

import json
from pathlib import Path

from server.modules.training_data.exceptions import NotebookTemplateError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_PATH = _PROJECT_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"

_LINKS_CELL = 1
_DOWNLOAD_PLACEHOLDER = 'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"'
_UPLOAD_PLACEHOLDER = 'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"'


def _fill(source: str, placeholder: str, name: str, value: str) -> str:
    if source.count(placeholder) != 1:
        raise NotebookTemplateError(
            f"the {name} placeholder must appear exactly once in the template"
        )
    return source.replace(placeholder, f"{name} = {json.dumps(value)}")


def build_job_notebook(
    download_url: str, upload_url: str, *, template_path: Path = TEMPLATE_PATH
) -> str:
    """Return the template notebook (JSON text) with this job's links filled in.

    Nothing is written to disk. The links hold one-time tokens, so the result
    must only be sent to the admin who just created the job.
    """
    try:
        notebook = json.loads(template_path.read_text(encoding="utf-8"))
        cell = notebook["cells"][_LINKS_CELL]
        source = "".join(cell["source"])
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise NotebookTemplateError("the notebook template could not be read") from exc

    source = _fill(source, _DOWNLOAD_PLACEHOLDER, "DOWNLOAD_URL", download_url)
    source = _fill(source, _UPLOAD_PLACEHOLDER, "UPLOAD_URL", upload_url)
    cell["source"] = source.splitlines(keepends=True)
    return json.dumps(notebook, indent=1)


__all__ = ["TEMPLATE_PATH", "NotebookTemplateError", "build_job_notebook"]
