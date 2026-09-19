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
