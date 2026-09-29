"""Offline checks for docs/colab/adapter_to_gguf_template.ipynb.

The notebook needs Colab (and the llama.cpp converter) to run for real; these
tests cover what can be checked offline: structure, that every code cell
parses, that the converter call has the agreed arguments, and the pure helper
functions in the helpers cell.
"""

from __future__ import annotations

import ast
import json
import re
import zipfile
from pathlib import Path

import pytest

NOTEBOOK = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "colab"
    / "adapter_to_gguf_template.ipynb"
)


def _load() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _code_sources() -> list[str]:
    return [
        "".join(cell["source"])
        for cell in _load()["cells"]
        if cell["cell_type"] == "code"
    ]


def _helpers(**config) -> dict:
    """Run the config cell (with optional overrides), then the helpers cell."""
    sources = _code_sources()
    config_source = next(src for src in sources if "ADAPTER_ZIP =" in src)
    source = next(src for src in sources if "def safe_extract" in src)
    namespace: dict = {}
    exec(compile(config_source, "<config-cell>", "exec"), namespace)
    namespace.update(config)
    exec(compile(source, "<helpers-cell>", "exec"), namespace)
    return namespace


def test_notebook_is_nbformat4_with_unique_cell_ids_and_intro():
    notebook = _load()
    assert notebook["nbformat"] == 4
    ids = [cell["id"] for cell in notebook["cells"]]
    assert len(ids) == len(set(ids)) == 8
    assert notebook["cells"][0]["cell_type"] == "markdown"


def test_every_code_cell_parses_as_python():
    for source in _code_sources():
        ast.parse(source)


def test_converter_call_overrides_base_and_writes_f16():
    joined = "\n".join(_code_sources())
    assert 'BASE_MODEL_ID = "unsloth/gemma-3-4b-it"' in joined
    assert "convert_lora_to_gguf.py" in joined
    assert '"--base-model-id", BASE_MODEL_ID' in joined
    assert '"--outtype", "f16"' in joined
    assert '"--outfile", OUTPUT_GGUF' in joined


def test_safe_extract_unpacks_a_normal_zip(tmp_path):
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("adapter_config.json", "{}")
        handle.writestr("sub/file.txt", "hi")
    _helpers()["safe_extract"](archive, tmp_path / "out")
    assert (tmp_path / "out" / "adapter_config.json").read_text() == "{}"
    assert (tmp_path / "out" / "sub" / "file.txt").read_text() == "hi"


@pytest.mark.parametrize("bad_name", ["../evil.txt", "sub/../../evil.txt", "/abs.txt"])
def test_safe_extract_rejects_paths_that_escape(tmp_path, bad_name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(bad_name, "x")
    with pytest.raises(ValueError, match="unsafe path"):
        _helpers()["safe_extract"](archive, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_sha256_of_matches_hashlib(tmp_path):
    import hashlib

    path = tmp_path / "blob.bin"
    path.write_bytes(b"abc" * 1000)
    assert _helpers()["sha256_of"](path) == hashlib.sha256(b"abc" * 1000).hexdigest()


GOOD_TENSORS = [
    ("blk.0.attn_q.weight.lora_a", (2560, 16)),
    ("blk.0.attn_q.weight.lora_b", (16, 2048)),
    ("blk.0.ffn_up.weight.lora_a", (2560, 16)),
    ("blk.0.ffn_up.weight.lora_b", (16, 10240)),
]


def test_check_lora_fields_accepts_a_valid_adapter():
    summary = _helpers()["check_lora_fields"](
        "adapter", "lora", 32.0, GOOD_TENSORS, 16, 32.0
    )
    assert summary == {"tensor_pairs": 2, "rank": 16, "alpha": 32.0}


def test_check_lora_fields_reports_every_problem():
    check = _helpers()["check_lora_fields"]
    with pytest.raises(ValueError) as caught:
        check("model", "other", 8.0, [("blk.0.x.weight.lora_a", (2560, 8))], 16, 32.0)
    message = str(caught.value)
    assert "general.type" in message
    assert "adapter.type" in message
    assert "alpha" in message
    assert "lora_b" in message
    assert "rank" in message


def test_check_lora_fields_rejects_an_adapter_with_no_tensors():
    with pytest.raises(ValueError, match="no lora_a"):
        _helpers()["check_lora_fields"]("adapter", "lora", 32.0, [], 16, 32.0)


# Mirrors the file-name rule in apps/server/modules/training_data/serving.py
# (parse_gguf_filename): the app matches loaded adapters to versions by it.
SERVING_NAME_RE = re.compile(r"^(?P<agent>[a-z]+)-v(?P<version>\d+)\.gguf$")


def test_notebook_still_has_eight_cells():
    assert len(_load()["cells"]) == 8


def test_config_cell_has_blank_agent_and_version_fields():
    source = next(src for src in _code_sources() if "ADAPTER_ZIP =" in src)
    assert 'AGENT_ID = ""' in source
    assert 'ADAPTER_VERSION = ""' in source


@pytest.mark.parametrize(
    ("agent_id", "version", "expected"),
    [
        ("sme", 3, "sme-v3.gguf"),
        ("sme", "4", "sme-v4.gguf"),
        ("SME", 1, None),
        ("sme", 0, None),
        ("sme", -1, None),
        ("", 1, None),
        ("sme-x", 1, None),
        ("sme", None, None),
        ("sme", "x", None),
        ("sme", True, None),
    ],
)
def test_gguf_output_name_table(agent_id, version, expected):
    assert _helpers()["gguf_output_name"](agent_id, version) == expected


def test_output_name_comes_from_agent_and_version_and_matches_serving_rule():
    ns = _helpers(AGENT_ID="gad", ADAPTER_VERSION="2")
    assert ns["OUTPUT_GGUF"] == "gad-v2.gguf"
    assert SERVING_NAME_RE.match(ns["OUTPUT_GGUF"])


@pytest.mark.parametrize(
    ("agent_id", "version"), [("", ""), ("gad", ""), ("", "2"), ("gad", "zero")]
)
def test_output_name_falls_back_with_a_warning(agent_id, version, capsys):
    ns = _helpers(AGENT_ID=agent_id, ADAPTER_VERSION=version)
    assert ns["OUTPUT_GGUF"] == "adapter-f16.gguf"
    out = capsys.readouterr().out
    assert "WARNING" in out and "<agent>-v<version>.gguf" in out


def test_download_cell_names_the_file_and_the_startup_flag():
    source = _code_sources()[-1]
    assert "--lora-scaled <FULL PATH>" in source
    assert "OUTPUT_GGUF" in source
