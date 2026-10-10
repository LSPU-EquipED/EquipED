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
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

DOCS_COLAB = Path(__file__).resolve().parents[2] / "docs" / "colab"
TRAINING_NOTEBOOK = DOCS_COLAB / "dpo_training_template.ipynb"
STANDALONE_NOTEBOOK = DOCS_COLAB / "adapter_to_gguf_template.ipynb"

FIRST_NEW_CELL = 12
UPLOAD_CELL = 11
HEADER, CONFIG, READ_ADAPTER, PREPARE, CONVERT, VERIFY, DOWNLOAD = range(12, 19)
COPIED_HELPERS = ("run", "sha256_of", "check_lora_fields", "gguf_output_name")

# Mirrors the file-name rule in apps/server/modules/training_data/serving.py
# (parse_gguf_filename): the app matches loaded adapters to versions by it.
SERVING_NAME_RE = re.compile(r"^(?P<agent>[a-z]+)-v(?P<version>\d+)\.gguf$")


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
    namespace.setdefault("report", lambda *args, **kwargs: None)  # status helper
    exec(compile(_source(index), f"<cell-{index}>", "exec"), namespace)  # noqa: S102
    return namespace


def _helpers(base_model_name: str = "unsloth/gemma-3-4b-it") -> dict:
    return _run_cell(CONFIG, {"BASE_MODEL_NAME": base_model_name})


# --- structure ------------------------------------------------------------------


def test_new_cells_follow_the_untouched_training_cells():
    cells = _cells(TRAINING_NOTEBOOK)
    assert len(cells) == 19
    assert cells[HEADER]["cell_type"] == "markdown"
    assert all(cells[i]["cell_type"] == "code" for i in range(CONFIG, DOWNLOAD + 1))
    # cell 11 is still the upload cell the earlier tests pin
    assert "UPLOAD_URL" in _source(UPLOAD_CELL)


def test_every_new_code_cell_parses_as_python():
    for source in _new_code_sources():
        ast.parse(source)


def test_conversion_happens_after_the_upload_and_download_after_verification():
    sources = ["".join(cell["source"]) for cell in _cells(TRAINING_NOTEBOOK)]

    def first(predicate):
        return next(i for i, source in enumerate(sources) if predicate(source))

    upload = first(lambda s: "UPLOAD_URL" in s and "upload_response = requests.post(" in s)
    first_conversion = first(
        lambda s: "conversion_step" in s or "convert_lora_to_gguf" in s
    )
    verify = first(
        lambda s: "check_lora_fields(" in s and "def check_lora_fields" not in s
    )
    download = first(lambda s: "files.download" in s)
    assert upload == UPLOAD_CELL
    assert upload < first_conversion
    assert verify < download


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
    # no upload_response in the namespace: the legacy fallback names
    assert ns["GGUF_OUTPUT_FILES"] == [
        "adapter-f16.gguf",
        "adapter-f16.gguf.sha256",
        "adapter-f16.gguf.json",
    ]
    assert ns["GGUF_SOURCE"] == {
        "agent_id": None,
        "adapter_version": None,
        "adapter_id": None,
    }


@pytest.mark.parametrize(
    ("agent_id", "version", "expected"),
    [
        ("sme", 3, "sme-v3.gguf"),
        ("gad", 1, "gad-v1.gguf"),
        ("coordinator", 12, "coordinator-v12.gguf"),
        ("sme", "4", "sme-v4.gguf"),
        ("SME", 1, None),
        ("sme", 0, None),
        ("sme", -1, None),
        ("sme", "0", None),
        ("", 1, None),
        ("sme-x", 1, None),
        ("sme", None, None),
        ("sme", "x", None),
        ("sme", True, None),
        (None, 1, None),
        (3, 1, None),
    ],
)
def test_gguf_output_name_table(agent_id, version, expected):
    assert _helpers()["gguf_output_name"](agent_id, version) == expected


def test_gguf_output_name_round_trips_the_serving_file_name_rule():
    name = _helpers()["gguf_output_name"]("itso", 7)
    match = SERVING_NAME_RE.match(name)
    assert match is not None
    assert (match["agent"], int(match["version"])) == ("itso", 7)


class _FakeUpload:
    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error

    def json(self):
        if self._error is not None:
            raise self._error
        return self._payload


def _config_with_upload(upload) -> dict:
    return _run_cell(
        CONFIG,
        {"BASE_MODEL_NAME": "unsloth/gemma-3-4b-it", "upload_response": upload},
    )


def test_config_names_the_file_from_the_upload_response(capsys):
    upload = _FakeUpload(
        {"agent_id": "gad", "version": 1, "adapter_id": "abc-123", "job_id": "j"}
    )
    ns = _config_with_upload(upload)
    assert ns["OUTPUT_GGUF"] == "gad-v1.gguf"
    assert ns["GGUF_OUTPUT_FILES"] == [
        "gad-v1.gguf",
        "gad-v1.gguf.sha256",
        "gad-v1.gguf.json",
    ]
    assert ns["GGUF_SOURCE"] == {
        "agent_id": "gad",
        "adapter_version": 1,
        "adapter_id": "abc-123",
    }
    assert SERVING_NAME_RE.match(ns["OUTPUT_GGUF"])
    out = capsys.readouterr().out
    assert "gad-v1.gguf" in out and "WARNING" not in out


@pytest.mark.parametrize(
    "upload",
    [
        _FakeUpload(error=ValueError("not json")),
        _FakeUpload({"agent_id": "gad"}),
        _FakeUpload({"version": 2}),
        _FakeUpload({"agent_id": "GAD", "version": 2}),
        _FakeUpload(["not", "a", "dict"]),
        None,
        object(),
    ],
)
def test_config_falls_back_with_a_warning_when_the_upload_is_unusable(upload, capsys):
    ns = _config_with_upload(upload)
    assert ns["OUTPUT_GGUF"] == "adapter-f16.gguf"
    assert ns["GGUF_OUTPUT_FILES"][0] == "adapter-f16.gguf"
    out = capsys.readouterr().out
    assert "WARNING" in out and "<agent>-v<version>.gguf" in out


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
    capsys.readouterr()  # drop the config cell's own output
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
        agent_id="sme",
        adapter_version=3,
        adapter_id="abc-123",
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
        "agent_id": "sme",
        "adapter_version": 3,
        "adapter_id": "abc-123",
    }
    json.dumps(metadata)  # serialisable


def test_build_gguf_metadata_always_has_the_source_keys_null_when_unknown():
    metadata = _helpers()["build_gguf_metadata"](
        llama_cpp_commit="c0ffee",
        llama_cpp_ref=None,
        base_model_id="unsloth/gemma-3-4b-it",
        lora_rank=16,
        lora_alpha=32.0,
        tensor_pairs=238,
        gguf_sha256="a" * 64,
        gguf_bytes=1,
        adapter_zip_sha256="b" * 64,
    )
    assert metadata["agent_id"] is None
    assert metadata["adapter_version"] is None
    assert metadata["adapter_id"] is None


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
        tensors=[
            ("blk.0.attn_q.weight.lora_a", (16, 2560)),
            ("blk.0.attn_q.weight.lora_b", (2560, 16)),
        ],
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


def _verify_namespace(tmp_path, monkeypatch, upload=None, **fields) -> dict:
    monkeypatch.chdir(tmp_path)
    Path("trained_adapter.zip").write_bytes(b"zip-bytes")
    ns = _config_with_upload(upload)
    Path(ns["OUTPUT_GGUF"]).write_bytes(b"gguf-bytes")
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
    assert metadata["agent_id"] is None
    assert metadata["adapter_version"] is None
    assert metadata["adapter_id"] is None


def test_verify_cell_names_files_and_records_the_source_for_a_named_output(
    tmp_path, monkeypatch
):
    upload = _FakeUpload({"agent_id": "sme", "version": 3, "adapter_id": "abc-123"})
    ns = _verify_namespace(tmp_path, monkeypatch, upload=upload)
    _run_cell(VERIFY, ns)

    gguf_sha = hashlib.sha256(b"gguf-bytes").hexdigest()
    assert Path("sme-v3.gguf.sha256").read_text() == f"{gguf_sha}  sme-v3.gguf\n"
    metadata = json.loads(Path("sme-v3.gguf.json").read_text())
    assert metadata["agent_id"] == "sme"
    assert metadata["adapter_version"] == 3
    assert metadata["adapter_id"] == "abc-123"
    assert not Path("adapter-f16.gguf.sha256").exists()


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


def test_download_cell_downloads_the_named_files_and_prints_the_flag(
    monkeypatch, capsys
):
    downloads: list[str] = []
    for name, module in _fake_colab_module(downloads).items():
        monkeypatch.setitem(sys.modules, name, module)
    upload = _FakeUpload({"agent_id": "sme", "version": 3, "adapter_id": "a"})
    _run_cell(DOWNLOAD, _config_with_upload(upload))
    assert downloads == ["sme-v3.gguf", "sme-v3.gguf.sha256", "sme-v3.gguf.json"]
    out = capsys.readouterr().out
    assert "--lora-scaled <FULL PATH>\\sme-v3.gguf:0.0" in out


def test_download_cell_outside_colab_names_the_files(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "google", None)  # makes the import fail
    monkeypatch.setitem(sys.modules, "google.colab", None)
    _run_cell(DOWNLOAD, _helpers())
    out = capsys.readouterr().out
    assert "Not running in Colab" in out
    assert "adapter-f16.gguf.json" in out


# --- the converter environment and the source hygiene ---------------------------------


def _prepare_namespace(tmp_path, monkeypatch, failing_venv: bool):
    monkeypatch.chdir(tmp_path)
    requirements = tmp_path / "llama.cpp" / "requirements"
    requirements.mkdir(parents=True)
    (requirements / "requirements-convert_lora_to_gguf.txt").write_text("numpy\n")
    ns = _helpers()
    commands: list[list[str]] = []

    def fake_run(command):
        command = [str(part) for part in command]
        commands.append(command)
        if failing_venv and command[1:4] == ["-m", "venv", "converter-venv"]:
            raise subprocess.CalledProcessError(1, command)

    fake_subprocess = types.SimpleNamespace(
        run=lambda *args, **kwargs: types.SimpleNamespace(stdout="c0ffee\n"),
        CalledProcessError=subprocess.CalledProcessError,
    )
    ns.update(run=fake_run, subprocess=fake_subprocess)
    return ns, commands


def test_prepare_cell_creates_the_venv_and_installs_requirements_into_it(
    tmp_path, monkeypatch
):
    ns, commands = _prepare_namespace(tmp_path, monkeypatch, failing_venv=False)
    _run_cell(PREPARE, ns)

    assert ns["LLAMA_CPP_COMMIT"] == "c0ffee"
    assert commands[0][1:] == ["-m", "venv", "converter-venv"]
    assert commands[1][0] == ns["venv_python"]()
    assert commands[1][1:5] == ["-m", "pip", "install", "-q"]
    assert commands[1][5] == "-r"
    assert not any("virtualenv" in part for c in commands for part in c)


def test_prepare_cell_falls_back_to_virtualenv_when_venv_fails(
    tmp_path, monkeypatch, capsys
):
    ns, commands = _prepare_namespace(tmp_path, monkeypatch, failing_venv=True)
    _run_cell(PREPARE, ns)

    assert [c[1:] for c in commands[:3]] == [
        ["-m", "venv", "converter-venv"],
        ["-m", "pip", "install", "-q", "virtualenv"],
        ["-m", "virtualenv", "converter-venv"],
    ]
    assert commands[3][0] == ns["venv_python"]()
    assert commands[3][5] == "-r"
    assert "falling back to virtualenv" in capsys.readouterr().out


def test_new_cell_sources_are_ascii_only():
    for cell in _cells(TRAINING_NOTEBOOK)[FIRST_NEW_CELL:]:
        "".join(cell["source"]).encode("ascii")


# --- converter env and streamed subprocess output --------------------------------

HELPER_COMMAND_OK = [
    sys.executable,
    "-c",
    "import sys; print('hel'+'lo'); print('ERR'+'-LINE', file=sys.stderr)",
]
HELPER_COMMAND_FAIL = [
    sys.executable,
    "-c",
    "import sys; print('before'+'-exit'); sys.exit(3)",
]


def test_convert_cell_disables_hf_transfer_before_any_run_call():
    source = _source(CONVERT)
    assign = 'os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"'
    assert assign in source
    assert source.index(assign) < source.index("run(")
    assert source.index("with conversion_step") < source.index(assign)


def test_convert_cell_env_assignment_executes_and_is_restored(monkeypatch):
    import os

    monkeypatch.setenv("HF_HUB_ENABLE_HF_TRANSFER", "1")
    line = next(
        ln.strip()
        for ln in _source(CONVERT).splitlines()
        if ln.strip().startswith("os.environ[")
    )
    exec(line, {"os": os})  # noqa: S102
    assert os.environ["HF_HUB_ENABLE_HF_TRANSFER"] == "0"


def test_run_helper_streams_stdout_and_stderr(capsys):
    _helpers()["run"](HELPER_COMMAND_OK)
    out = capsys.readouterr().out
    assert "hello" in out
    assert "ERR-LINE" in out


def test_run_helper_prints_output_then_raises_on_failure(capsys):
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _helpers()["run"](HELPER_COMMAND_FAIL)
    assert excinfo.value.returncode == 3
    assert "before-exit" in capsys.readouterr().out
