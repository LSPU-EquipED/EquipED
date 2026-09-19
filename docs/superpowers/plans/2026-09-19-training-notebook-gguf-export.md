# Training Notebook GGUF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the person pastes `DOWNLOAD_URL` and `UPLOAD_URL` and clicks Run all, the DPO training notebook trains and uploads the adapter and then also produces a verified GGUF LoRA, its SHA-256 and a small metadata file for download.

**Architecture:** Append seven cells (11-17) after the existing upload cell of `docs/colab/dpo_training_template.ipynb`; cells 0-10 are not touched. The llama.cpp converter and the GGUF reader run inside a separate virtual environment so the pinned training libraries are undisturbed. The copied helpers (`run`, `sha256_of`, `check_lora_fields`) stay identical to the standalone conversion notebook, which is also left unchanged.

**Tech Stack:** Jupyter notebook JSON (Colab), Python standard library (`venv`/`virtualenv`, `subprocess`), llama.cpp `convert_lora_to_gguf.py` and its `gguf` package, pytest (offline tests with stand-ins).

**Spec:** `docs/superpowers/specs/2026-09-19-training-notebook-gguf-export-design.md`

## Global Constraints

- Nothing under `apps/` changes. The GGUF is not uploaded to the backend and is not placed inside the adapter zip.
- Notebook cells 0-10 of `docs/colab/dpo_training_template.ipynb` are not modified (append only), and `docs/colab/adapter_to_gguf_template.ipynb` is not modified.
- The converter runs in a separate virtual environment (`converter-venv`): both the converter call and the `pip install -r` of its requirements use the venv's interpreter, never `sys.executable`. GGUF verification also runs in the venv; only the pure `check_lora_fields` runs in the training process.
- llama.cpp: default branch (`LLAMA_CPP_REF = None`); the exact commit is printed and recorded in `adapter-f16.gguf.json`.
- The upload cell (10) runs before any conversion cell, so a conversion failure never loses the trained adapter. Cells 13-17 run inside `with conversion_step(...)`, which prints that the adapter is safe and how to re-convert, then re-raises.
- Outputs: `adapter-f16.gguf`, `adapter-f16.gguf.sha256` (one line `<hash>  adapter-f16.gguf`, same format as the standalone notebook), `adapter-f16.gguf.json` (fields: `llama_cpp_commit`, `llama_cpp_ref`, `converter`, `outtype`, `base_model_id`, `lora_rank`, `lora_alpha`, `tensor_pairs`, `gguf_sha256`, `gguf_bytes`, `adapter_zip_sha256`).
- The converter arguments are exactly `--base-model-id <BASE_MODEL_NAME> --outfile adapter-f16.gguf --outtype f16 <adapter dir>`.
- No automatic deployment; the host still loads the GGUF by hand.
- The notebook file is serialised as `json.dumps(nb, indent=1, ensure_ascii=False)` with CRLF line endings and no trailing newline.
- Console output in the new cells is plain ASCII.
- Commits: **do not add `Co-Authored-By` or `Claude-Session` trailers** (repo rule in CLAUDE.md). Commit only when the controller has confirmed the user allowed commits this turn; otherwise leave the tree dirty and say so.
- Test commands. Training tests, from the repo root: `python -m pytest training/tests -q`. Notebook contract tests: `cd apps && uv run --project server pytest server/tests/training_data/test_dpo_colab_contract.py -q`.
- Baselines before this plan: `python -m pytest training/tests -q` reports 126 passed; the contract test file reports 46 passed; the training notebook has 11 cells.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `docs/colab/dpo_training_template.ipynb` | append cells 11-17 | header, config and helpers, read adapter, prepare converter venv, convert, verify and write outputs, download |
| `training/tests/test_dpo_notebook_gguf_cells.py` | create | offline tests for the new cells |
| `training/serving-lora-adapter.md` | modify (one paragraph) | tell the host owner the training notebook now produces the files |

Task 3 is manual and needs the user (a real Colab run). Tasks 1-2 need neither GPU nor network.

---

### Task 1: Append the GGUF export cells to the training notebook

**Files:**
- Create: `training/tests/test_dpo_notebook_gguf_cells.py`
- Modify: `docs/colab/dpo_training_template.ipynb` (append cells 11-17 through a one-off script)

**Interfaces:**
- Consumes: from the existing training cells: `BASE_MODEL_NAME` (cell 6), `ADAPTER_DIR` (`"./trained_adapter"`, cell 7), `ADAPTER_ZIP_PATH` (`"trained_adapter.zip"`, cell 10), and the optional `trainer` / `model` variables (cell 7 / cell 6). The saved adapter directory holds `adapter_config.json` and `adapter_model.safetensors`. From the standalone notebook (`docs/colab/adapter_to_gguf_template.ipynb`): the functions `run`, `sha256_of`, `check_lora_fields`, whose source the new helper cell copies exactly.
- Produces: cell 12 defines `GGUF_BASE_MODEL_ID`, `OUTPUT_GGUF`, `GGUF_OUTPUT_FILES`, `LLAMA_CPP_REPO`, `LLAMA_CPP_REF`, `CONVERTER_VENV`, `GGUF_DUMP_SCRIPT`, `run`, `sha256_of`, `check_lora_fields`, `conversion_step(name)` (context manager), `venv_python() -> str`, `read_gguf_fields(gguf_path, python=None) -> dict` (keys `general_type`, `adapter_type`, `alpha`, `tensors` as `[[name, [dims...]], ...]`), and `build_gguf_metadata(*, llama_cpp_commit, llama_cpp_ref, base_model_id, lora_rank, lora_alpha, tensor_pairs, gguf_sha256, gguf_bytes, adapter_zip_sha256) -> dict`. Cell 13 sets `LORA_RANK` (int) and `LORA_ALPHA` (float); cell 14 sets `LLAMA_CPP_COMMIT` (str). Cell indices: header 11, config and helpers 12, read adapter 13, prepare converter 14, convert 15, verify 16, download 17.

- [ ] **Step 1: Write the failing tests**

Create `training/tests/test_dpo_notebook_gguf_cells.py`:

```python
"""Offline tests for the GGUF export cells at the end of the DPO training notebook.

The cells need Colab (GPU training, llama.cpp, network) to run for real. These
tests cover what can be checked offline: where the cells sit, that they parse,
that the converter is run from the isolated virtual environment with the same
arguments as the standalone conversion notebook, that the copied helpers have not
drifted from the standalone notebook's, and the behaviour of the new helpers and
of the verify and download cells against stand-ins.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

DOCS_COLAB = Path(__file__).resolve().parents[2] / "docs" / "colab"
TRAINING_NOTEBOOK = DOCS_COLAB / "dpo_training_template.ipynb"
STANDALONE_NOTEBOOK = DOCS_COLAB / "adapter_to_gguf_template.ipynb"

FIRST_NEW_CELL = 11
UPLOAD_CELL = 10
HEADER, CONFIG, READ_ADAPTER, PREPARE, CONVERT, VERIFY, DOWNLOAD = range(11, 18)
COPIED_HELPERS = ("run", "sha256_of", "check_lora_fields")


def _cells(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def _source(index: int, path: Path = TRAINING_NOTEBOOK) -> str:
    return "".join(_cells(path)[index]["source"])


def _new_code_sources() -> list[str]:
    return [
        "".join(cell["source"])
        for cell in _cells(TRAINING_NOTEBOOK)[FIRST_NEW_CELL:]
        if cell["cell_type"] == "code"
    ]


def _run_cell(index: int, namespace: dict | None = None) -> dict:
    namespace = {} if namespace is None else namespace
    exec(compile(_source(index), f"<cell-{index}>", "exec"), namespace)  # noqa: S102
    return namespace


def _helpers(base_model_name: str = "unsloth/gemma-3-4b-it") -> dict:
    return _run_cell(CONFIG, {"BASE_MODEL_NAME": base_model_name})


# --- structure ------------------------------------------------------------------


def test_new_cells_follow_the_untouched_training_cells():
    cells = _cells(TRAINING_NOTEBOOK)
    assert len(cells) == 18
    assert cells[HEADER]["cell_type"] == "markdown"
    assert all(cells[i]["cell_type"] == "code" for i in range(CONFIG, DOWNLOAD + 1))
    # cell 10 is still the upload cell the earlier tests pin
    assert "UPLOAD_URL" in _source(UPLOAD_CELL)


def test_every_new_code_cell_parses_as_python():
    for source in _new_code_sources():
        ast.parse(source)


def test_conversion_happens_after_the_upload_and_download_after_verification():
    assert "requests.post(" in _source(UPLOAD_CELL)
    assert UPLOAD_CELL < PREPARE < CONVERT < VERIFY < DOWNLOAD
    assert "convert_lora_to_gguf.py" in _source(CONVERT)
    assert "check_lora_fields(" in _source(VERIFY)
    assert "files.download" in _source(DOWNLOAD)


def _run_calls(source: str) -> list[list[ast.expr]]:
    """The element lists of every run([...]) call in the source."""
    calls = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run"
            and node.args
            and isinstance(node.args[0], ast.List)
        ):
            calls.append(node.args[0].elts)
    return calls


def _is_venv_python(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "venv_python"
    )


def test_converter_and_its_pip_install_run_in_the_virtual_environment():
    converter_calls = [
        elts
        for elts in _run_calls(_source(CONVERT))
        if any(
            isinstance(e, ast.Constant)
            and isinstance(e.value, str)
            and e.value.endswith("convert_lora_to_gguf.py")
            for e in elts
        )
    ]
    assert len(converter_calls) == 2  # --help, then the real conversion
    assert all(_is_venv_python(elts[0]) for elts in converter_calls)

    pip_calls = [
        elts
        for elts in _run_calls(_source(PREPARE))
        if any(isinstance(e, ast.Constant) and e.value == "-r" for e in elts)
    ]
    assert len(pip_calls) == 1
    assert _is_venv_python(pip_calls[0][0])


def test_converter_arguments_match_the_standalone_notebook():
    standalone = "\n".join(
        "".join(cell["source"])
        for cell in _cells(STANDALONE_NOTEBOOK)
        if cell["cell_type"] == "code"
    )
    convert = _source(CONVERT)
    for fragment in ('"--outtype", "f16"', '"--base-model-id"', '"--outfile"'):
        assert fragment in standalone
        assert fragment in convert
    assert '"--base-model-id", GGUF_BASE_MODEL_ID' in convert
    assert '"--outfile", OUTPUT_GGUF' in convert
    assert "ADAPTER_DIR" in convert


def _function_sources(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    return {
        node.name: ast.get_source_segment(source, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def test_copied_helpers_are_identical_to_the_standalone_notebooks():
    training = _function_sources(_source(CONFIG))
    standalone_source = next(
        src
        for src in (
            "".join(cell["source"])
            for cell in _cells(STANDALONE_NOTEBOOK)
            if cell["cell_type"] == "code"
        )
        if "def safe_extract" in src
    )
    standalone = _function_sources(standalone_source)
    for name in COPIED_HELPERS:
        assert training[name] == standalone[name], f"{name} drifted"


def test_the_llama_cpp_commit_is_printed_and_recorded():
    assert 'print("llama.cpp commit:", LLAMA_CPP_COMMIT)' in _source(PREPARE)
    assert "llama_cpp_commit=LLAMA_CPP_COMMIT" in _source(VERIFY)
    assert "LLAMA_CPP_REF = None" in _source(CONFIG)


# --- helpers --------------------------------------------------------------------


def test_config_uses_the_trained_base_model_and_the_three_output_names():
    ns = _helpers("some/base-model")
    assert ns["GGUF_BASE_MODEL_ID"] == "some/base-model"
    assert ns["GGUF_OUTPUT_FILES"] == [
        "adapter-f16.gguf",
        "adapter-f16.gguf.sha256",
        "adapter-f16.gguf.json",
    ]


def test_conversion_step_says_the_adapter_is_safe_and_reraises(capsys):
    ns = _helpers()
    with pytest.raises(ValueError, match="boom"):
        with ns["conversion_step"]("verify the GGUF"):
            raise ValueError("boom")
    out = capsys.readouterr().out
    assert "'verify the GGUF' failed" in out
    assert "already uploaded" in out
    assert "adapter_to_gguf_template.ipynb" in out


def test_conversion_step_is_silent_when_nothing_fails(capsys):
    ns = _helpers()
    with ns["conversion_step"]("anything"):
        pass
    assert capsys.readouterr().out == ""


def test_venv_python_points_inside_the_converter_venv():
    ns = _helpers()
    path = Path(ns["venv_python"]())
    assert path.is_absolute()
    assert path.parent.parent.name == "converter-venv"
    assert path.name in {"python", "python.exe"}


def test_build_gguf_metadata_has_every_recorded_field():
    ns = _helpers()
    metadata = ns["build_gguf_metadata"](
        llama_cpp_commit="c0ffee",
        llama_cpp_ref=None,
        base_model_id="unsloth/gemma-3-4b-it",
        lora_rank=16,
        lora_alpha=32.0,
        tensor_pairs=238,
        gguf_sha256="a" * 64,
        gguf_bytes=62_000_000,
        adapter_zip_sha256="b" * 64,
    )
    assert metadata == {
        "llama_cpp_commit": "c0ffee",
        "llama_cpp_ref": None,
        "converter": "convert_lora_to_gguf.py",
        "outtype": "f16",
        "base_model_id": "unsloth/gemma-3-4b-it",
        "lora_rank": 16,
        "lora_alpha": 32.0,
        "tensor_pairs": 238,
        "gguf_sha256": "a" * 64,
        "gguf_bytes": 62_000_000,
        "adapter_zip_sha256": "b" * 64,
    }
    json.dumps(metadata)  # serialisable


def _stub_gguf_package(root: Path, alpha, tensors) -> None:
    package = root / "llama.cpp" / "gguf-py" / "gguf"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "class _Field:\n"
        "    def __init__(self, value):\n"
        "        self._value = value\n"
        "    def contents(self):\n"
        "        return self._value\n"
        "\n"
        "class _Scalar:\n"
        "    def __init__(self, value):\n"
        "        self._value = value\n"
        "    def tolist(self):\n"
        "        return self._value\n"
        "\n"
        "class _Tensor:\n"
        "    def __init__(self, name, shape):\n"
        "        self.name = name\n"
        "        self.shape = shape\n"
        "\n"
        "class GGUFReader:\n"
        "    def __init__(self, path):\n"
        "        self.fields = {\n"
        "            'general.type': _Field('adapter'),\n"
        "            'adapter.type': _Field('lora'),\n"
        f"            'adapter.lora.alpha': _Field(_Scalar({alpha!r})),\n"
        "        }\n"
        f"        self.tensors = [_Tensor(n, s) for n, s in {tensors!r}]\n",
        encoding="utf-8",
    )


def test_read_gguf_fields_returns_the_json_the_verifier_needs(tmp_path, monkeypatch):
    _stub_gguf_package(
        tmp_path,
        alpha=32.0,
        tensors=[("blk.0.attn_q.weight.lora_a", (16, 2560)), ("blk.0.attn_q.weight.lora_b", (2560, 16))],
    )
    monkeypatch.chdir(tmp_path)
    ns = _helpers()

    fields = ns["read_gguf_fields"]("ignored.gguf", python=sys.executable)

    assert fields["general_type"] == "adapter"
    assert fields["adapter_type"] == "lora"
    assert fields["alpha"] == 32.0
    assert fields["tensors"][0] == ["blk.0.attn_q.weight.lora_a", [16, 2560]]
    tensors = [(name, tuple(shape)) for name, shape in fields["tensors"]]
    summary = ns["check_lora_fields"](
        fields["general_type"],
        fields["adapter_type"],
        fields["alpha"],
        tensors,
        16,
        32.0,
    )
    assert summary == {"tensor_pairs": 1, "rank": 16, "alpha": 32.0}


def test_read_gguf_fields_reports_a_reader_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # no llama.cpp/gguf-py here: the import fails
    ns = _helpers()
    with pytest.raises(RuntimeError, match="could not read"):
        ns["read_gguf_fields"]("ignored.gguf", python=sys.executable)
    assert "ModuleNotFoundError" in capsys.readouterr().out


# --- the cells that run against the saved adapter -----------------------------------


def _write_adapter(directory: Path, **config) -> None:
    directory.mkdir()
    settings = {
        "peft_type": "LORA",
        "r": 16,
        "lora_alpha": 32,
        "base_model_name_or_path": "unsloth/gemma-3-4b-it-unsloth-bnb-4bit",
    }
    settings.update(config)
    (directory / "adapter_config.json").write_text(json.dumps(settings))
    (directory / "adapter_model.safetensors").write_bytes(b"weights")


def test_read_adapter_cell_reads_rank_and_alpha_and_survives_missing_torch(
    tmp_path, capsys
):
    adapter_dir = tmp_path / "trained_adapter"
    _write_adapter(adapter_dir)
    ns = _helpers()
    ns["ADAPTER_DIR"] = str(adapter_dir)
    ns["trainer"] = object()
    ns["model"] = object()

    _run_cell(READ_ADAPTER, ns)

    assert (ns["LORA_RANK"], ns["LORA_ALPHA"]) == (16, 32.0)
    assert "trainer" not in ns and "model" not in ns
    assert "converter will use base config from: unsloth/gemma-3-4b-it" in (
        capsys.readouterr().out
    )


def test_read_adapter_cell_rejects_something_that_is_not_a_lora(tmp_path, capsys):
    adapter_dir = tmp_path / "trained_adapter"
    _write_adapter(adapter_dir, peft_type="PREFIX_TUNING")
    ns = _helpers()
    ns["ADAPTER_DIR"] = str(adapter_dir)
    with pytest.raises(ValueError, match="not a LoRA adapter"):
        _run_cell(READ_ADAPTER, ns)
    assert "already uploaded" in capsys.readouterr().out


def test_read_adapter_cell_needs_the_weights_file(tmp_path):
    adapter_dir = tmp_path / "trained_adapter"
    _write_adapter(adapter_dir)
    (adapter_dir / "adapter_model.safetensors").unlink()
    ns = _helpers()
    ns["ADAPTER_DIR"] = str(adapter_dir)
    with pytest.raises(FileNotFoundError, match="adapter_model.safetensors"):
        _run_cell(READ_ADAPTER, ns)


def _verify_namespace(tmp_path, monkeypatch, **fields) -> dict:
    monkeypatch.chdir(tmp_path)
    Path("adapter-f16.gguf").write_bytes(b"gguf-bytes")
    Path("trained_adapter.zip").write_bytes(b"zip-bytes")
    ns = _helpers()
    ns.update(
        {
            "LORA_RANK": 16,
            "LORA_ALPHA": 32.0,
            "LLAMA_CPP_COMMIT": "c0ffee",
            "ADAPTER_ZIP_PATH": "trained_adapter.zip",
        }
    )
    valid = {
        "general_type": "adapter",
        "adapter_type": "lora",
        "alpha": 32.0,
        "tensors": [["x.lora_a", [16, 64]], ["x.lora_b", [64, 16]]],
    }
    valid.update(fields)
    ns["read_gguf_fields"] = lambda path: valid
    return ns


def test_verify_cell_writes_checksum_and_metadata(tmp_path, monkeypatch, capsys):
    ns = _verify_namespace(tmp_path, monkeypatch)
    _run_cell(VERIFY, ns)

    gguf_sha = hashlib.sha256(b"gguf-bytes").hexdigest()
    assert Path("adapter-f16.gguf.sha256").read_text() == (
        f"{gguf_sha}  adapter-f16.gguf\n"
    )
    metadata = json.loads(Path("adapter-f16.gguf.json").read_text())
    assert metadata["gguf_sha256"] == gguf_sha
    assert metadata["adapter_zip_sha256"] == hashlib.sha256(b"zip-bytes").hexdigest()
    assert metadata["llama_cpp_commit"] == "c0ffee"
    assert metadata["llama_cpp_ref"] is None
    assert metadata["lora_rank"] == 16 and metadata["tensor_pairs"] == 1
    out = capsys.readouterr().out
    assert "GGUF LoRA verified" in out and "llama.cpp commit: c0ffee" in out


def test_verify_cell_refuses_a_gguf_that_is_not_a_lora(tmp_path, monkeypatch):
    ns = _verify_namespace(tmp_path, monkeypatch, general_type="model")
    with pytest.raises(ValueError, match="general.type"):
        _run_cell(VERIFY, ns)
    assert not Path("adapter-f16.gguf.sha256").exists()
    assert not Path("adapter-f16.gguf.json").exists()


def _fake_colab_module(downloads: list[str]) -> dict:
    files = types.SimpleNamespace(download=downloads.append)
    colab = types.ModuleType("google.colab")
    colab.files = files
    google = types.ModuleType("google")
    google.colab = colab
    return {"google": google, "google.colab": colab}


def test_download_cell_downloads_all_three_files_in_colab(monkeypatch, capsys):
    downloads: list[str] = []
    for name, module in _fake_colab_module(downloads).items():
        monkeypatch.setitem(sys.modules, name, module)
    _run_cell(DOWNLOAD, _helpers())
    assert downloads == [
        "adapter-f16.gguf",
        "adapter-f16.gguf.sha256",
        "adapter-f16.gguf.json",
    ]
    assert "multiple downloads" in capsys.readouterr().out


def test_download_cell_outside_colab_names_the_files(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "google", None)  # makes the import fail
    monkeypatch.setitem(sys.modules, "google.colab", None)
    _run_cell(DOWNLOAD, _helpers())
    out = capsys.readouterr().out
    assert "Not running in Colab" in out
    assert "adapter-f16.gguf.json" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest training/tests/test_dpo_notebook_gguf_cells.py -q`
Expected: `20 failed, 1 passed` (the one that passes only checks that cell 10 is still the upload cell; every other test needs the new cells).

- [ ] **Step 3: Apply the notebook edit**

Write the script below to a file outside the repo (for example your scratchpad directory as `add_gguf_cells.py`), then run it once from the repo root with `python <path-to>/add_gguf_cells.py`. It appends cells 11-17, asserts the notebook still has exactly 11 cells before it starts, and keeps the file's CRLF/indent-1/no-trailing-newline serialisation.

```python
"""One-off: append the GGUF export cells (11-17) to the training notebook.

Run from the repo root:  python <this file>
It only appends; cells 0-10 are never touched. It refuses to run twice.
"""

import json
from pathlib import Path

NOTEBOOK = Path("docs/colab/dpo_training_template.ipynb")

CELL_11_MARKDOWN = r'''## Convert the adapter to GGUF (after the upload)

The trained adapter has already been uploaded to EquipED by the cell above, so
nothing below can lose it. The next cells convert that same adapter into a GGUF
LoRA file that the host's llama.cpp `llama-server` can load, verify it, and offer
it for download. This adds roughly 5-10 minutes (it installs the llama.cpp
converter into a separate virtual environment, so the training libraries above
are not disturbed).

You get three files: `adapter-f16.gguf`, `adapter-f16.gguf.sha256` (its
checksum) and `adapter-f16.gguf.json` (which llama.cpp commit made it, and which
uploaded adapter it came from). Nothing is deployed: give the files to the host
owner, who loads them by hand (`training/serving-lora-adapter.md`).

If any step below fails, the adapter is still safe on the backend. Re-convert it
later with `docs/colab/adapter_to_gguf_template.ipynb`.'''

CELL_12_CONFIG_AND_HELPERS = r'''import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# The converter needs the regular instruct model's config, not the 4-bit variant
# named inside adapter_config.json; BASE_MODEL_NAME (cell 6) is exactly that.
GGUF_BASE_MODEL_ID = BASE_MODEL_NAME
OUTPUT_GGUF = "adapter-f16.gguf"
GGUF_OUTPUT_FILES = [OUTPUT_GGUF, OUTPUT_GGUF + ".sha256", OUTPUT_GGUF + ".json"]
LLAMA_CPP_REPO = "https://github.com/ggml-org/llama.cpp"
# None = llama.cpp's default branch. To match the host's llama-server build,
# set a FULL commit hash from that build's source tree.
LLAMA_CPP_REF = None
CONVERTER_VENV = "converter-venv"

# Runs inside the converter virtual environment: reads the GGUF with llama.cpp's
# own gguf package and prints what check_lora_fields needs as one JSON line.
GGUF_DUMP_SCRIPT = """
import json
import sys

sys.path.insert(0, "llama.cpp/gguf-py")
from gguf import GGUFReader


def plain(value):
    return value.tolist() if hasattr(value, "tolist") else value


reader = GGUFReader(sys.argv[1])


def field_value(name):
    field = reader.fields.get(name)
    return None if field is None else plain(field.contents())


print(
    json.dumps(
        {
            "general_type": field_value("general.type"),
            "adapter_type": field_value("adapter.type"),
            "alpha": field_value("adapter.lora.alpha"),
            "tensors": [
                [tensor.name, [int(dim) for dim in tensor.shape]]
                for tensor in reader.tensors
            ],
        }
    )
)
"""


def run(command):
    command = [str(part) for part in command]
    print("$", " ".join(command))
    subprocess.run(command, check=True)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_lora_fields(
    general_type, adapter_type, alpha, tensors, expected_rank, expected_alpha
):
    problems = []
    if general_type != "adapter":
        problems.append(f"general.type is {general_type!r}, expected 'adapter'")
    if adapter_type != "lora":
        problems.append(f"adapter.type is {adapter_type!r}, expected 'lora'")
    if alpha is None or abs(float(alpha) - expected_alpha) > 1e-6:
        problems.append(f"alpha is {alpha!r}, expected {expected_alpha}")
    lora_a = [item for item in tensors if item[0].endswith(".lora_a")]
    lora_b = [item for item in tensors if item[0].endswith(".lora_b")]
    if not lora_a:
        problems.append("no lora_a tensors found")
    if len(lora_a) != len(lora_b):
        problems.append(f"{len(lora_a)} lora_a tensors but {len(lora_b)} lora_b tensors")
    for name, shape in lora_a + lora_b:
        if min(shape) != expected_rank:
            problems.append(
                f"{name}: smallest dimension {min(shape)} is not rank {expected_rank}"
            )
            break
    if problems:
        raise ValueError("; ".join(problems))
    return {"tensor_pairs": len(lora_a), "rank": expected_rank, "alpha": float(alpha)}


@contextlib.contextmanager
def conversion_step(name):
    """Say the adapter is safe if a conversion step fails, then re-raise."""
    try:
        yield
    except Exception:
        print(
            f"\nGGUF conversion step '{name}' failed. The trained adapter was "
            "already uploaded to EquipED and is safe. Re-convert it later with "
            "docs/colab/adapter_to_gguf_template.ipynb."
        )
        raise


def venv_python():
    """The interpreter inside the converter virtual environment."""
    scripts, exe = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return str(Path(CONVERTER_VENV).resolve() / scripts / exe)


def read_gguf_fields(gguf_path, python=None):
    """Read the GGUF with llama.cpp's gguf package, inside the converter venv."""
    result = subprocess.run(
        [python or venv_python(), "-c", GGUF_DUMP_SCRIPT, str(gguf_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"could not read {gguf_path} (exit {result.returncode})")
    return json.loads(result.stdout.strip().splitlines()[-1])


def build_gguf_metadata(
    *,
    llama_cpp_commit,
    llama_cpp_ref,
    base_model_id,
    lora_rank,
    lora_alpha,
    tensor_pairs,
    gguf_sha256,
    gguf_bytes,
    adapter_zip_sha256,
):
    return {
        "llama_cpp_commit": llama_cpp_commit,
        "llama_cpp_ref": llama_cpp_ref,
        "converter": "convert_lora_to_gguf.py",
        "outtype": "f16",
        "base_model_id": base_model_id,
        "lora_rank": lora_rank,
        "lora_alpha": lora_alpha,
        "tensor_pairs": tensor_pairs,
        "gguf_sha256": gguf_sha256,
        "gguf_bytes": gguf_bytes,
        "adapter_zip_sha256": adapter_zip_sha256,
    }'''

CELL_13_READ_ADAPTER = r'''with conversion_step("read the saved adapter"):
    # Best effort: give the converter as much RAM as possible.
    try:
        import gc

        for _name in ("trainer", "model"):
            globals().pop(_name, None)
        gc.collect()
        import torch

        torch.cuda.empty_cache()
    except Exception as exc:
        print(f"(could not free memory, continuing: {exc!r})")

    adapter_config = json.loads(
        (Path(ADAPTER_DIR) / "adapter_config.json").read_text(encoding="utf-8")
    )
    if adapter_config.get("peft_type") != "LORA":
        raise ValueError(
            f"not a LoRA adapter: peft_type={adapter_config.get('peft_type')!r}"
        )
    if not (Path(ADAPTER_DIR) / "adapter_model.safetensors").exists():
        raise FileNotFoundError("adapter_model.safetensors is missing from the adapter")
    LORA_RANK = int(adapter_config["r"])
    LORA_ALPHA = float(adapter_config["lora_alpha"])
    print("adapter base (as trained):", adapter_config.get("base_model_name_or_path"))
    print("converter will use base config from:", GGUF_BASE_MODEL_ID)
    print("rank:", LORA_RANK, "alpha:", LORA_ALPHA)'''

CELL_14_PREPARE_CONVERTER = r'''with conversion_step("prepare the converter"):
    if not os.path.isdir("llama.cpp"):
        run(["git", "clone", "--depth", "1", LLAMA_CPP_REPO, "llama.cpp"])
        if LLAMA_CPP_REF:
            fetched = subprocess.run(
                ["git", "-C", "llama.cpp", "fetch", "--depth", "1", "origin", LLAMA_CPP_REF]
            )
            if fetched.returncode == 0:
                run(["git", "-C", "llama.cpp", "checkout", "FETCH_HEAD"])
            else:
                print(f"WARNING: could not fetch {LLAMA_CPP_REF}; using the default branch.")
    LLAMA_CPP_COMMIT = subprocess.run(
        ["git", "-C", "llama.cpp", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    print("llama.cpp commit:", LLAMA_CPP_COMMIT)

    requirements_dir = Path("llama.cpp/requirements")
    candidates = [
        requirements_dir / "requirements-convert_lora_to_gguf.txt",
        requirements_dir / "requirements-convert_hf_to_gguf.txt",
    ]
    requirements_file = next((path for path in candidates if path.exists()), None)
    if requirements_file is None:
        raise FileNotFoundError(
            "no converter requirements file under llama.cpp/requirements; "
            "the llama.cpp layout may have changed, check that directory"
        )

    # A separate virtual environment keeps the converter's packages away from
    # the pinned training stack. Some Colab images lack python's venv support
    # (ensurepip), so fall back to virtualenv.
    shutil.rmtree(CONVERTER_VENV, ignore_errors=True)
    try:
        run([sys.executable, "-m", "venv", CONVERTER_VENV])
    except subprocess.CalledProcessError:
        print("python -m venv failed; falling back to virtualenv")
        shutil.rmtree(CONVERTER_VENV, ignore_errors=True)
        run([sys.executable, "-m", "pip", "install", "-q", "virtualenv"])
        run([sys.executable, "-m", "virtualenv", CONVERTER_VENV])
    run([venv_python(), "-m", "pip", "install", "-q", "-r", requirements_file])'''

CELL_15_CONVERT = r'''with conversion_step("convert to GGUF"):
    # Print the converter's own flags first, so the log records what this
    # llama.cpp version actually accepts.
    run([venv_python(), "llama.cpp/convert_lora_to_gguf.py", "--help"])

    run(
        [
            venv_python(),
            "llama.cpp/convert_lora_to_gguf.py",
            "--base-model-id", GGUF_BASE_MODEL_ID,
            "--outfile", OUTPUT_GGUF,
            "--outtype", "f16",
            ADAPTER_DIR,
        ]
    )
    if not os.path.exists(OUTPUT_GGUF):
        raise FileNotFoundError(f"converter finished but {OUTPUT_GGUF!r} was not created")'''

CELL_16_VERIFY = r'''with conversion_step("verify the GGUF"):
    fields = read_gguf_fields(OUTPUT_GGUF)
    tensors = [(name, tuple(shape)) for name, shape in fields["tensors"]]
    summary = check_lora_fields(
        fields["general_type"],
        fields["adapter_type"],
        fields["alpha"],
        tensors,
        LORA_RANK,
        LORA_ALPHA,
    )
    print("GGUF LoRA verified:", summary)

    gguf_sha256 = sha256_of(OUTPUT_GGUF)
    gguf_bytes = os.path.getsize(OUTPUT_GGUF)
    Path(OUTPUT_GGUF + ".sha256").write_text(
        f"{gguf_sha256}  {OUTPUT_GGUF}\n", encoding="utf-8"
    )
    gguf_metadata = build_gguf_metadata(
        llama_cpp_commit=LLAMA_CPP_COMMIT,
        llama_cpp_ref=LLAMA_CPP_REF,
        base_model_id=GGUF_BASE_MODEL_ID,
        lora_rank=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        tensor_pairs=summary["tensor_pairs"],
        gguf_sha256=gguf_sha256,
        gguf_bytes=gguf_bytes,
        adapter_zip_sha256=sha256_of(ADAPTER_ZIP_PATH),
    )
    Path(OUTPUT_GGUF + ".json").write_text(
        json.dumps(gguf_metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{OUTPUT_GGUF}: {gguf_bytes / (1024 * 1024):.1f} MB")
    print("sha256:", gguf_sha256)
    print("llama.cpp commit:", LLAMA_CPP_COMMIT)'''

CELL_17_DOWNLOAD = r'''with conversion_step("download the files"):
    try:
        from google.colab import files
    except ImportError:
        print("Not running in Colab: the files are in the working directory:")
        print(", ".join(GGUF_OUTPUT_FILES))
    else:
        print("Your browser may ask to allow multiple downloads; allow them.")
        for _name in GGUF_OUTPUT_FILES:
            files.download(_name)
        print("Give these files to the host owner (training/serving-lora-adapter.md).")'''


def to_source(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": to_source(text),
    }


raw = NOTEBOOK.read_bytes()
notebook = json.loads(raw.decode("utf-8"))
assert len(notebook["cells"]) == 11, "expected the 11-cell notebook; already applied?"

notebook["cells"].extend(
    [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": to_source(CELL_11_MARKDOWN),
        },
        code_cell(CELL_12_CONFIG_AND_HELPERS),
        code_cell(CELL_13_READ_ADAPTER),
        code_cell(CELL_14_PREPARE_CONVERTER),
        code_cell(CELL_15_CONVERT),
        code_cell(CELL_16_VERIFY),
        code_cell(CELL_17_DOWNLOAD),
    ]
)

# Same serialisation the file already uses: indent=1, CRLF, no trailing newline.
out = json.dumps(notebook, indent=1, ensure_ascii=False).replace("\n", "\r\n")
NOTEBOOK.write_bytes(out.encode("utf-8"))
print("appended cells 11-17")
```

Expected output: `appended cells 11-17`.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `python -m pytest training/tests/test_dpo_notebook_gguf_cells.py -q`
Expected: `21 passed` (takes a few seconds; one test tries to import torch and shrugs if it is missing).

- [ ] **Step 5: Run the whole suites**

Run: `python -m pytest training/tests -q`
Expected: `147 passed` (126 baseline + 21 new).

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_dpo_colab_contract.py -q`
Expected: `46 passed` (one unrelated `Duplicate name` UserWarning is normal).

- [ ] **Step 6: Check that cells 0-10 and the standalone notebook are untouched**

Run: `git diff --stat`
Expected: exactly one changed file, `docs/colab/dpo_training_template.ipynb`, about 361 insertions and **0 deletions**. Any deletion means an existing cell was changed or the CRLF/indent serialisation was lost: run `git checkout docs/colab/dpo_training_template.ipynb` and redo Step 3. `git status --short` must list only that file and the new test file.

- [ ] **Step 7: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb training/tests/test_dpo_notebook_gguf_cells.py
git commit -m "feat(colab): export a verified GGUF LoRA at the end of the training notebook"
```

---

### Task 2: Tell the host owner about the new outputs

**Files:**
- Modify: `training/serving-lora-adapter.md`

**Interfaces:**
- Consumes: the three output file names from Task 1.
- Produces: docs only.

- [ ] **Step 1: Add one paragraph to the runbook**

In `training/serving-lora-adapter.md`, find the line ``- `adapter-f16.gguf.sha256`, its checksum`` (the second item of the list under "You will receive two files from the training side:"). Insert this after that line, keeping one blank line before it and one blank line after it (the blank line before "**Verified 2026-09-19 on llama-server build 10430:**" stays):

```markdown

The training notebook (`docs/colab/dpo_training_template.ipynb`) now produces
both of these at the end of a run, plus an optional `adapter-f16.gguf.json`
that records which llama.cpp commit made the file and which uploaded adapter it
came from. You can ignore the JSON; it is a record for whoever trains. The
standalone conversion notebook (`docs/colab/adapter_to_gguf_template.ipynb`,
for re-converting an adapter that is already stored) produces only the first
two.
```

Change nothing else in the file.

- [ ] **Step 2: Check the file names in the paragraph exist**

Run: `python -c "import pathlib; [print(p, pathlib.Path(p).exists()) for p in ('docs/colab/dpo_training_template.ipynb','docs/colab/adapter_to_gguf_template.ipynb')]"`
Expected: both lines end in `True`.

Run: `git diff --stat`
Expected: only `training/serving-lora-adapter.md` changed, about 8 insertions and 0 deletions.

- [ ] **Step 3: Commit**

```bash
git add training/serving-lora-adapter.md
git commit -m "docs(training): note that the training notebook now produces the GGUF"
```

---

### Task 3: One real Colab run (the user does this; not for a subagent)

The offline tests cannot show that the virtual environment step, the converter and the downloads work in a real Colab session. This run adds one adapter row to the shared Neon dev database and one stored `adapter.zip`, as any training run does. Record the results in the SDD ledger (`.superpowers/sdd/2026-09-19-training-notebook-gguf-export/progress.md`).

**Files:** none.

- [ ] **Step 1: Run the notebook**

In the admin panel: Training Data, SME, Start Training Job. Open `docs/colab/dpo_training_template.ipynb` in Colab on a GPU runtime, paste the two URLs, Run all.

Expected, in order: training output; `Adapter uploaded:` from cell 10; then the conversion section: `llama.cpp commit: <40-hex>`; either a `python -m venv` success or the line `python -m venv failed; falling back to virtualenv` (note which one happened); the converter's `--help`; `GGUF LoRA verified: {...}`; `adapter-f16.gguf: <about 60> MB`, `sha256: ...`; three browser downloads. If any conversion step fails, the failure message must say the adapter was already uploaded.

- [ ] **Step 2: Check the downloaded files**

`adapter-f16.gguf.sha256` must match the file (PowerShell: `certutil -hashfile adapter-f16.gguf SHA256`). `adapter-f16.gguf.json` must show the printed llama.cpp commit, `llama_cpp_ref: null`, `lora_rank: 16`, `lora_alpha: 32.0`, `converter: convert_lora_to_gguf.py`, and `adapter_zip_sha256` equal to the sha256 of the newest `adapters/sme/<adapter_id>/adapter.zip` on the backend disk (`certutil -hashfile <that zip> SHA256`).

- [ ] **Step 3: Note the outcome**

Record: total time of the conversion section, whether the venv fallback was used, and the GGUF size. If the run failed, keep the failing cell's output; the adapter row and zip are still valid and can be converted with the standalone notebook.
