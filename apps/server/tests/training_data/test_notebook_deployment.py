"""Static checks that the server image carries the notebook template."""

from __future__ import annotations

from pathlib import Path

from server.modules.training_data.notebook import TEMPLATE_PATH

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_RELATIVE = "docs/colab/dpo_training_template.ipynb"


def test_template_path_is_the_project_root_docs_colab_file():
    assert TEMPLATE_PATH == REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"
    assert TEMPLATE_PATH.is_file()


def test_dockerfile_copies_the_template_to_where_the_code_looks():
    dockerfile = (REPO_ROOT / "apps" / "server" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    # WORKDIR is /app and the code resolves the project root as /app, so the
    # template must land at /app/docs/colab/dpo_training_template.ipynb.
    assert "WORKDIR /app\n" in dockerfile
    assert f"COPY {TEMPLATE_RELATIVE} ./{TEMPLATE_RELATIVE}" in dockerfile
    base_stage = dockerfile.split("FROM base AS dev")[0]
    assert f"COPY {TEMPLATE_RELATIVE}" in base_stage  # inherited by dev and prod


def test_the_template_is_not_dockerignored():
    ignore = REPO_ROOT / ".dockerignore"
    if ignore.exists():
        text = ignore.read_text(encoding="utf-8")
        assert "docs" not in text and "*.ipynb" not in text
