"""CPU-only static and contract tests for docs/colab/dpo_training_template.ipynb.

Extracts the package-validation and adapter-packaging notebook cells and runs them
without network or GPU access. This verifies compatibility with the package manifest
and EquipED adapter rules.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
from server.modules.training_data.contracts import DpoPackageManifest

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"


def _load_notebook() -> dict:
    with NOTEBOOK_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_notebook_cell_code(cell_index: int) -> str:
    nb = _load_notebook()
    cell = nb["cells"][cell_index]
    assert cell["cell_type"] == "code"
    return "".join(cell["source"])


def _build_valid_package_archive(
    *,
    agent_id: str = "sme",
    pairs: list[dict[str, str]] | None = None,
    provenance: list[dict[str, Any]] | None = None,
    manifest_override: dict[str, Any] | None = None,
    include_members: set[str] | None = None,
    corrupt_pairs_bytes: bytes | None = None,
    corrupt_prov_bytes: bytes | None = None,
) -> bytes:
    if pairs is None:
        pairs = [
            {
                "prompt": "prompt 1",
                "chosen": "chosen response 1",
                "rejected": "rejected response 1",
            },
            {
                "prompt": "prompt 2",
                "chosen": "chosen response 2",
                "rejected": "rejected response 2",
            },
        ]
    if provenance is None:
        provenance = []
        for i, pair in enumerate(pairs):
            gen_id = f"{i + 1:08x}-1111-1111-1111-111111111111"
            p_prompt = pair.get("prompt", "") if isinstance(pair, dict) else ""
            p_rejected = pair.get("rejected", "") if isinstance(pair, dict) else ""
            provenance.append(
                {
                    "pair_id": gen_id,
                    "generation_id": gen_id,
                    "evaluation_id": f"{i + 1:08x}-2222-2222-2222-222222222222",
                    "document_id": f"{i + 1:08x}-3333-3333-3333-333333333333",
                    "agent_id": agent_id,
                    "unit_key": f"envelope_{i}",
                    "model_name": "unsloth/gemma-3-4b-it",
                    "response_contract_key": "criterion_measurements.v1",
                    "response_contract_version": 1,
                    "criterion_ids": [f"A-{i + 1:02d}"],
                    "reviewer_ids": [f"{i + 1:08x}-4444-4444-4444-444444444444"],
                    "prompt_sha256": hashlib.sha256(
                        p_prompt.encode("utf-8")
                    ).hexdigest(),
                    "response_sha256": hashlib.sha256(
                        p_rejected.encode("utf-8")
                    ).hexdigest(),
                    "created_at": "2026-09-18T00:00:00Z",
                }
            )

    pairs_bytes = (
        corrupt_pairs_bytes
        if corrupt_pairs_bytes is not None
        else "\n".join(json.dumps(p) for p in pairs).encode("utf-8")
    )
    prov_bytes = (
        corrupt_prov_bytes
        if corrupt_prov_bytes is not None
        else "\n".join(json.dumps(r) for r in provenance).encode("utf-8")
    )

    manifest_obj = DpoPackageManifest(
        manifest_version="equiped.dpo-package.v1",
        agent_id=agent_id,
        model_name="unsloth/gemma-3-4b-it",
        response_contract_keys=["criterion_measurements.v1"],
        pair_count=len(pairs),
        evaluation_count=len(provenance),
        reviewer_count=1,
        skipped_counts={"identical": 0},
        pairs_sha256=hashlib.sha256(pairs_bytes).hexdigest(),
        pairs_bytes=len(pairs_bytes),
        provenance_sha256=hashlib.sha256(prov_bytes).hexdigest(),
        provenance_bytes=len(prov_bytes),
        export_timestamp="2026-09-18T00:00:00Z",
    )

    manifest_data = manifest_obj.model_dump()
    if manifest_override:
        manifest_data.update(manifest_override)

    manifest_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")

    members_to_write = (
        include_members
        if include_members is not None
        else {"manifest.json", "pairs.jsonl", "provenance.jsonl"}
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if "manifest.json" in members_to_write:
            zf.writestr("manifest.json", manifest_bytes)
        if "pairs.jsonl" in members_to_write:
            zf.writestr("pairs.jsonl", pairs_bytes)
        if "provenance.jsonl" in members_to_write:
            zf.writestr("provenance.jsonl", prov_bytes)
        for extra in members_to_write - {
            "manifest.json",
            "pairs.jsonl",
            "provenance.jsonl",
        }:
            zf.writestr(extra, b"extra content")

    return buf.getvalue()


class MockResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _execute_notebook_validation_cell(package_bytes: bytes) -> dict[str, Any]:
    raw_code = _get_notebook_cell_code(2)
    # The requests import would overwrite the injected test double.
    # We replace `import requests` with our mock injection to keep execution offline.
    mock_requests_module_code = (
        "class _MockRequests:\n"
        "    @staticmethod\n"
        "    def get(url):\n"
        "        return _mock_response\n"
        "requests = _MockRequests()\n"
    )
    code = raw_code.replace("import requests\n", mock_requests_module_code)

    globals_dict = {
        "DOWNLOAD_URL": "http://mock-test/download",
        "_mock_response": MockResponse(package_bytes),
    }
    exec(code, globals_dict)  # noqa: S102
    return globals_dict


def test_notebook_validation_cell_accepts_valid_package():
    package_bytes = _build_valid_package_archive(agent_id="sme")
    ctx = _execute_notebook_validation_cell(package_bytes)

    assert len(ctx["pairs"]) == 2
    assert len(ctx["provenance_records"]) == 2
    assert ctx["manifest"]["agent_id"] == "sme"
    assert ctx["manifest"]["manifest_version"] == "equiped.dpo-package.v1"


def test_notebook_validation_matches_dpo_package_manifest_contract():
    """Verify that all fields present on DpoPackageManifest are validated."""
    nb_code = _get_notebook_cell_code(2)
    manifest_dummy = DpoPackageManifest(
        agent_id="sme",
        pairs_sha256="abc",
        pairs_bytes=10,
        provenance_sha256="def",
        provenance_bytes=20,
        export_timestamp="2026-09-18T00:00:00Z",
    )
    pydantic_field_names = set(manifest_dummy.model_dump().keys())

    # Extract REQUIRED_MANIFEST_FIELDS from the notebook cell
    dict_code = nb_code.split("REQUIRED_MANIFEST_FIELDS: dict")[1].split(
        "REQUIRED_PAIR_KEYS"
    )[0]
    cell_fields_code = "REQUIRED_MANIFEST_FIELDS: dict" + dict_code
    env = {}
    exec(cell_fields_code, {}, env)  # noqa: S102
    cell_fields = set(env["REQUIRED_MANIFEST_FIELDS"].keys())

    assert pydantic_field_names == cell_fields, (
        f"Notebook validation fields {cell_fields} must exactly match "
        f"DpoPackageManifest fields {pydantic_field_names}"
    )


def test_notebook_validation_rejects_missing_archive_members():
    package_bytes = _build_valid_package_archive(
        include_members={"manifest.json", "pairs.jsonl"}
    )
    with pytest.raises(ValueError, match="Package archive member mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_unexpected_archive_members():
    package_bytes = _build_valid_package_archive(
        include_members={
            "manifest.json",
            "pairs.jsonl",
            "provenance.jsonl",
            "rogue.txt",
        }
    )
    with pytest.raises(ValueError, match="Package archive member mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_invalid_manifest_version():
    package_bytes = _build_valid_package_archive(
        manifest_override={"manifest_version": "unsupported.v2"}
    )
    with pytest.raises(ValueError, match="Unsupported manifest_version"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_unsupported_agent():
    package_bytes = _build_valid_package_archive(
        manifest_override={"agent_id": "unsupported_agent"}
    )
    with pytest.raises(ValueError, match="Unsupported agent_id"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_missing_manifest_field():
    data = DpoPackageManifest(
        agent_id="sme",
        pairs_sha256="abc",
        pairs_bytes=10,
        provenance_sha256="def",
        provenance_bytes=20,
        export_timestamp="now",
    ).model_dump()
    del data["reviewer_count"]
    raw_manifest = json.dumps(data).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", raw_manifest)
        zf.writestr("pairs.jsonl", b'{"prompt":"a","chosen":"b","rejected":"c"}\n')
        zf.writestr("provenance.jsonl", b'{"score": 1}\n')

    with pytest.raises(ValueError, match="missing required field: 'reviewer_count'"):
        _execute_notebook_validation_cell(buf.getvalue())


def test_notebook_validation_rejects_corrupted_pairs_hash():
    package_bytes = _build_valid_package_archive(
        manifest_override={"pairs_sha256": "0" * 64}
    )
    with pytest.raises(ValueError, match="pairs.jsonl SHA-256 mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_corrupted_pairs_bytes():
    package_bytes = _build_valid_package_archive(
        manifest_override={"pairs_bytes": 99999}
    )
    with pytest.raises(ValueError, match="pairs.jsonl byte length mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_corrupted_provenance_hash():
    package_bytes = _build_valid_package_archive(
        manifest_override={"provenance_sha256": "0" * 64}
    )
    with pytest.raises(ValueError, match="provenance.jsonl SHA-256 mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_corrupted_provenance_bytes():
    package_bytes = _build_valid_package_archive(
        manifest_override={"provenance_bytes": 99999}
    )
    with pytest.raises(ValueError, match="provenance.jsonl byte length mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_zero_pairs():
    package_bytes = _build_valid_package_archive(pairs=[], provenance=[])
    with pytest.raises(ValueError, match="Package contains 0 pairs"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_pair_count_mismatch():
    package_bytes = _build_valid_package_archive(manifest_override={"pair_count": 5})
    with pytest.raises(
        ValueError, match="Parsed pair count .* does not match manifest.pair_count"
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_missing_pair_keys():
    bad_pairs = [{"prompt": "p", "chosen": "c"}]
    package_bytes = _build_valid_package_archive(pairs=bad_pairs)
    with pytest.raises(ValueError, match="missing required key"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_empty_string_pair_field():
    bad_pairs = [{"prompt": "p", "chosen": "  ", "rejected": "r"}]
    package_bytes = _build_valid_package_archive(pairs=bad_pairs)
    with pytest.raises(ValueError, match="must be a non-empty string"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_identical_chosen_and_rejected():
    bad_pairs = [{"prompt": "p", "chosen": "same", "rejected": "same"}]
    package_bytes = _build_valid_package_archive(pairs=bad_pairs)
    with pytest.raises(ValueError, match="'chosen' and 'rejected' are identical"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_malformed_provenance_json():
    package_bytes = _build_valid_package_archive(corrupt_prov_bytes=b"not json\n")
    with pytest.raises(ValueError, match="provenance.jsonl line 1: invalid JSON"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_non_object_provenance_record():
    package_bytes = _build_valid_package_archive(
        corrupt_prov_bytes=b'"just a string"\n'
    )
    with pytest.raises(ValueError, match="record must be a JSON object"):
        _execute_notebook_validation_cell(package_bytes)


def test_adapter_packaging_cell_creates_deterministic_archive_with_relative_paths():
    """Verify notebook cell 10 verifies outputs, builds relative paths, and uploads."""
    raw_code = _get_notebook_cell_code(10)
    mock_requests_module_code = (
        "class _MockRequests:\n"
        "    @staticmethod\n"
        "    def post(url, files=None):\n"
        "        return _mock_post(url, files=files)\n"
        "requests = _MockRequests()\n"
    )
    code = raw_code.replace("import requests\n", mock_requests_module_code)

    uploaded_files = {}

    def mock_post(url, files=None):
        assert url == "http://mock-test/upload"
        uploaded_files["file"] = files["file"][1].read()
        return type(
            "MockResp",
            (),
            {
                "raise_for_status": lambda self=None: None,
                "json": lambda self=None: {"status": "ok"},
            },
        )()

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = Path(tmpdir) / "trained_adapter"
        adapter_dir.mkdir()
        (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
        (adapter_dir / "training_manifest.json").write_text("{}", encoding="utf-8")
        (adapter_dir / "adapter_model.safetensors").write_bytes(b"weights-binary")

        # Add a sub-directory to ensure recursive relative preservation
        sub = adapter_dir / "logs"
        sub.mkdir()
        (sub / "events.json").write_text("[]", encoding="utf-8")

        zip_out = Path("trained_adapter.zip")
        try:
            ctx = {
                "ADAPTER_DIR": str(adapter_dir),
                "UPLOAD_URL": "http://mock-test/upload",
                "_mock_post": mock_post,
            }
            exec(code, ctx)  # noqa: S102

            assert zip_out.exists()
            with zipfile.ZipFile(zip_out, "r") as zf:
                namelist = zf.namelist()
                # Must preserve relative paths with forward slashes and no leading slash
                assert "adapter_config.json" in namelist
                assert "training_manifest.json" in namelist
                assert "adapter_model.safetensors" in namelist
                assert "logs/events.json" in namelist
                for name in namelist:
                    assert not name.startswith("/")
                    assert not name.startswith("..")

            # Upload occurred
            assert len(uploaded_files["file"]) == zip_out.stat().st_size
        finally:
            zip_out.unlink(missing_ok=True)


def test_adapter_packaging_cell_rejects_missing_required_files():
    code = _get_notebook_cell_code(10)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = Path(tmpdir) / "trained_adapter"
        adapter_dir.mkdir()
        # Missing adapter_config.json and training_manifest.json
        (adapter_dir / "adapter_model.safetensors").write_bytes(b"weights")

        ctx = {
            "ADAPTER_DIR": str(adapter_dir),
            "ADAPTER_ZIP_PATH": str(Path(tmpdir) / "output.zip"),
            "UPLOAD_URL": "http://mock-test/upload",
            "requests": None,
        }
        with pytest.raises(FileNotFoundError, match="missing required output files"):
            exec(code, ctx)  # noqa: S102


def test_adapter_packaging_cell_rejects_missing_weights_file():
    code = _get_notebook_cell_code(10)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = Path(tmpdir) / "trained_adapter"
        adapter_dir.mkdir()
        (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
        (adapter_dir / "training_manifest.json").write_text("{}", encoding="utf-8")
        # Missing weights file

        ctx = {
            "ADAPTER_DIR": str(adapter_dir),
            "ADAPTER_ZIP_PATH": str(Path(tmpdir) / "output.zip"),
            "UPLOAD_URL": "http://mock-test/upload",
            "requests": None,
        }
        with pytest.raises(FileNotFoundError, match="does not contain adapter_model"):
            exec(code, ctx)  # noqa: S102


def test_notebook_validation_rejects_duplicate_zip_members():
    # Create an archive with duplicate filenames in its central directory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", b"{}")
        # Add pairs.jsonl twice
        zf.writestr("pairs.jsonl", b'{"prompt":"a","chosen":"b","rejected":"c"}\n')
        zf.writestr("pairs.jsonl", b'{"prompt":"a","chosen":"b","rejected":"c"}\n')
        zf.writestr("provenance.jsonl", b'{"score":1}\n')

    with pytest.raises(ValueError, match="duplicate entries"):
        _execute_notebook_validation_cell(buf.getvalue())


def test_notebook_validation_rejects_negative_counts():
    neg_eval_bytes = _build_valid_package_archive(
        manifest_override={"evaluation_count": -1}
    )
    with pytest.raises(ValueError, match="negative evaluation_count"):
        _execute_notebook_validation_cell(neg_eval_bytes)

    neg_reviewer_bytes = _build_valid_package_archive(
        manifest_override={"reviewer_count": -1}
    )
    with pytest.raises(ValueError, match="negative reviewer_count"):
        _execute_notebook_validation_cell(neg_reviewer_bytes)

    neg_skipped_bytes = _build_valid_package_archive(
        manifest_override={"skipped_counts": {"identical": -1}}
    )
    with pytest.raises(ValueError, match="negative skipped_counts"):
        _execute_notebook_validation_cell(neg_skipped_bytes)


def test_notebook_validation_rejects_provenance_pair_count_mismatch():
    prov_record_1 = {
        "pair_id": "pair-1",
        "generation_id": "11111111-1111-1111-1111-111111111111",
        "evaluation_id": "22222222-2222-2222-2222-222222222222",
        "document_id": "33333333-3333-3333-3333-333333333333",
        "agent_id": "sme",
        "unit_key": "envelope_0",
        "model_name": "unsloth/gemma-3-4b-it",
        "response_contract_key": "criterion_measurements.v1",
        "response_contract_version": 1,
        "criterion_ids": ["A-01"],
        "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
        "prompt_sha256": "a" * 64,
        "response_sha256": "b" * 64,
        "created_at": "2026-09-18T00:00:00Z",
    }
    package_bytes = _build_valid_package_archive(
        pairs=[
            {"prompt": "p1", "chosen": "c1", "rejected": "r1"},
            {"prompt": "p2", "chosen": "c2", "rejected": "r2"},
        ],
        provenance=[prov_record_1],
        manifest_override={"pair_count": 2},
    )
    with pytest.raises(
        ValueError, match="Parsed provenance record count .* does not match pair count"
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_static_pins_and_model_spec():
    """Verify primary-source-compatible pins and base model revision."""
    nb = _load_notebook()
    install_cell_code = "".join(nb["cells"][4]["source"])
    model_cell_code = "".join(nb["cells"][6]["source"])

    assert 'PIN_UNSLOTH = "==2025.3.10"' in install_cell_code
    assert 'PIN_TRL = "==0.15.2"' in install_cell_code
    assert 'PIN_PEFT = "==0.14.0"' in install_cell_code
    assert 'PIN_BITSANDBYTES = "==0.45.3"' in install_cell_code
    assert 'PIN_DATASETS = "==3.3.2"' in install_cell_code
    assert 'PIN_TRANSFORMERS = "==4.50.0"' in install_cell_code
    assert 'PIN_ACCELERATE = "==1.4.0"' in install_cell_code

    assert 'BASE_MODEL_NAME = "unsloth/gemma-3-4b-it"' in model_cell_code
    assert (
        'BASE_MODEL_REVISION = "21bc97b90507086e76f0d256fee672973085d905"'
        in model_cell_code
    )


def test_notebook_training_api_constructors_present():
    """Verify FastLanguageModel, DPOConfig, and DPOTrainer invocations exist."""
    nb = _load_notebook()
    model_cell_code = "".join(nb["cells"][6]["source"])
    trainer_cell_code = "".join(nb["cells"][7]["source"])

    assert "FastLanguageModel.from_pretrained" in model_cell_code
    assert "FastLanguageModel.get_peft_model" in model_cell_code
    assert "DPOConfig(" in trainer_cell_code
    assert "DPOTrainer(" in trainer_cell_code


def test_notebook_validation_rejects_missing_provenance_field():
    prov = [
        {
            "pair_id": "pair-1",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            # missing unit_key
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match="provenance.jsonl line 1: missing required field: 'unit_key'"
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_empty_provenance_pair_id():
    prov = [
        {
            "pair_id": "   ",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(ValueError, match="'pair_id' must be a non-empty string"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_duplicate_provenance_pair_ids():
    prov = [
        {
            "pair_id": "dup-id",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        },
        {
            "pair_id": "dup-id",
            "generation_id": "55555555-5555-5555-5555-555555555555",
            "evaluation_id": "66666666-6666-6666-6666-666666666666",
            "document_id": "77777777-7777-7777-7777-777777777777",
            "agent_id": "sme",
            "unit_key": "envelope_1",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-02"],
            "reviewer_ids": ["88888888-8888-8888-8888-888888888888"],
            "prompt_sha256": "c" * 64,
            "response_sha256": "d" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        },
    ]
    package_bytes = _build_valid_package_archive(
        pairs=[
            {"prompt": "p1", "chosen": "c1", "rejected": "r1"},
            {"prompt": "p2", "chosen": "c2", "rejected": "r2"},
        ],
        provenance=prov,
        manifest_override={"pair_count": 2},
    )
    with pytest.raises(ValueError, match="duplicate pair_id 'dup-id'"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_provenance_wrong_agent():
    prov = [
        {
            "pair_id": "pair-1",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "coordinator",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        agent_id="sme",
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError,
        match="agent_id 'coordinator' does not match manifest agent_id 'sme'",
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_provenance_invalid_uuid():
    prov = [
        {
            "pair_id": "pair-1",
            "generation_id": "not-a-valid-uuid",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match="field 'generation_id' must be a valid UUID string"
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_provenance_invalid_hash():
    prov = [
        {
            "pair_id": "pair-1",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "invalid_hash_not_64_hex",
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match="'prompt_sha256' must be a 64-char hexadecimal string"
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_provenance_invalid_criterion_ids_and_types():
    prov_invalid_crit = [
        {
            "pair_id": "pair-1",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": [123],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes_crit = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov_invalid_crit,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match="'criterion_ids' must be a list of non-empty strings"
    ):
        _execute_notebook_validation_cell(package_bytes_crit)

    prov_invalid_rev = [
        {
            "pair_id": "pair-1",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["not-a-uuid"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes_rev = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov_invalid_rev,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match="'reviewer_ids' must be a list of valid UUID strings"
    ):
        _execute_notebook_validation_cell(package_bytes_rev)

    prov_invalid_version = [
        {
            "pair_id": "pair-1",
            "generation_id": "11111111-1111-1111-1111-111111111111",
            "evaluation_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 0,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["44444444-4444-4444-4444-444444444444"],
            "prompt_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes_ver = _build_valid_package_archive(
        pairs=[{"prompt": "p", "chosen": "c", "rejected": "r"}],
        provenance=prov_invalid_version,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match="'response_contract_version' must be a positive integer"
    ):
        _execute_notebook_validation_cell(package_bytes_ver)


def test_notebook_validation_cell_provides_positional_pair_provenance_records():
    package_bytes = _build_valid_package_archive(agent_id="sme")
    ctx = _execute_notebook_validation_cell(package_bytes)

    assert "pair_provenance_records" in ctx
    assert len(ctx["pair_provenance_records"]) == 2
    for pair, prov in ctx["pair_provenance_records"]:
        assert isinstance(pair, dict)
        assert isinstance(prov, dict)
        assert "prompt" in pair and "pair_id" in prov


def test_notebook_validation_rejects_corrupted_pair_id_relationship():
    pairs = [{"prompt": "p", "chosen": "c", "rejected": "r"}]
    gen_id = "11111111-1111-1111-1111-111111111111"
    prov = [
        {
            # corrupt: pair_id != generation_id
            "pair_id": "22222222-2222-2222-2222-222222222222",
            "generation_id": gen_id,
            "evaluation_id": "33333333-3333-3333-3333-333333333333",
            "document_id": "44444444-4444-4444-4444-444444444444",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["55555555-5555-5555-5555-555555555555"],
            "prompt_sha256": hashlib.sha256(
                pairs[0]["prompt"].encode("utf-8")
            ).hexdigest(),
            "response_sha256": hashlib.sha256(
                pairs[0]["rejected"].encode("utf-8")
            ).hexdigest(),
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=pairs,
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(
        ValueError, match=r"Record 1: pair_id .* must match generation_id .*"
    ):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_corrupted_prompt_sha256_relationship():
    pairs = [{"prompt": "p", "chosen": "c", "rejected": "r"}]
    gen_id = "11111111-1111-1111-1111-111111111111"
    prov = [
        {
            "pair_id": gen_id,
            "generation_id": gen_id,
            "evaluation_id": "33333333-3333-3333-3333-333333333333",
            "document_id": "44444444-4444-4444-4444-444444444444",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["55555555-5555-5555-5555-555555555555"],
            "prompt_sha256": "f" * 64,  # corrupt prompt_sha256
            "response_sha256": hashlib.sha256(
                pairs[0]["rejected"].encode("utf-8")
            ).hexdigest(),
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=pairs,
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(ValueError, match=r"Record 1: prompt_sha256 mismatch"):
        _execute_notebook_validation_cell(package_bytes)


def test_notebook_validation_rejects_corrupted_response_sha256_relationship():
    pairs = [{"prompt": "p", "chosen": "c", "rejected": "r"}]
    gen_id = "11111111-1111-1111-1111-111111111111"
    prov = [
        {
            "pair_id": gen_id,
            "generation_id": gen_id,
            "evaluation_id": "33333333-3333-3333-3333-333333333333",
            "document_id": "44444444-4444-4444-4444-444444444444",
            "agent_id": "sme",
            "unit_key": "envelope_0",
            "model_name": "unsloth/gemma-3-4b-it",
            "response_contract_key": "criterion_measurements.v1",
            "response_contract_version": 1,
            "criterion_ids": ["A-01"],
            "reviewer_ids": ["55555555-5555-5555-5555-555555555555"],
            "prompt_sha256": hashlib.sha256(
                pairs[0]["prompt"].encode("utf-8")
            ).hexdigest(),
            "response_sha256": "f" * 64,  # corrupt response_sha256
            "created_at": "2026-09-18T00:00:00Z",
        }
    ]
    package_bytes = _build_valid_package_archive(
        pairs=pairs,
        provenance=prov,
        manifest_override={"pair_count": 1},
    )
    with pytest.raises(ValueError, match=r"Record 1: response_sha256 mismatch"):
        _execute_notebook_validation_cell(package_bytes)


# --- grouped held-out split (cell 5) and held-out artifact (cells 8-10) -------


class _FakeDatasetsModule:
    """Stands in for `datasets` (not installed in the CPU test environment)."""

    class Dataset:
        @staticmethod
        def from_list(rows):
            return list(rows)


def _pairs_and_provenance(n_evaluations: int, pairs_per_evaluation: int):
    pairs: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []
    for e in range(n_evaluations):
        for p in range(pairs_per_evaluation):
            n = e * pairs_per_evaluation + p
            pair = {
                "prompt": f"prompt {n}",
                "chosen": f"chosen {n}",
                "rejected": f"rejected {n}",
            }
            pairs.append(pair)
            records.append(
                {
                    "pair_id": f"{n + 1:08x}-1111-1111-1111-111111111111",
                    "evaluation_id": f"{e + 1:08x}-2222-2222-2222-222222222222",
                }
            )
    return pairs, list(zip(pairs, records, strict=True))


def _run_split_cell(monkeypatch, pairs, pair_provenance_records) -> dict[str, Any]:
    monkeypatch.setitem(sys.modules, "datasets", _FakeDatasetsModule)
    ctx: dict[str, Any] = {
        "pairs": pairs,
        "pair_provenance_records": pair_provenance_records,
    }
    exec(_get_notebook_cell_code(5), ctx)  # noqa: S102
    return ctx


def test_split_cell_holds_out_whole_evaluations(monkeypatch):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    heldout_rows = ctx["heldout_rows"]
    heldout_evals = {row["evaluation_id"] for row in heldout_rows}
    assert len(heldout_evals) == 2  # ceil(20% of 10 evaluations)
    assert len(heldout_rows) == 6  # every pair of a held-out evaluation
    assert len(ctx["train_dataset"]) == 24
    assert len(ctx["eval_dataset"]) == 6
    train_evals = {prov["evaluation_id"] for _, prov in ctx["train_items"]}
    assert train_evals.isdisjoint(heldout_evals)


def test_split_cell_rows_carry_ids_and_datasets_carry_only_training_columns(
    monkeypatch,
):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    for row in ctx["heldout_rows"]:
        assert set(row) == {
            "pair_id",
            "evaluation_id",
            "prompt",
            "chosen",
            "rejected",
        }
    for row in [*ctx["train_dataset"], *ctx["eval_dataset"]]:
        assert set(row) == {"prompt", "chosen", "rejected"}


def test_split_cell_is_deterministic(monkeypatch):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    first = _run_split_cell(monkeypatch, pairs, records)["heldout_rows"]
    second = _run_split_cell(monkeypatch, pairs, records)["heldout_rows"]
    assert first == second


def test_split_cell_holds_out_one_of_two_evaluations(monkeypatch):
    pairs, records = _pairs_and_provenance(n_evaluations=2, pairs_per_evaluation=10)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    assert len({row["evaluation_id"] for row in ctx["heldout_rows"]}) == 1
    assert len(ctx["heldout_rows"]) == 10
    assert len(ctx["train_dataset"]) == 10


def test_split_cell_holds_nothing_out_below_twenty_pairs(monkeypatch, capsys):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=1)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    assert ctx["eval_dataset"] is None
    assert ctx["heldout_rows"] == []
    assert len(ctx["train_dataset"]) == 10
    assert "Holding nothing out" in capsys.readouterr().out


def test_split_cell_holds_nothing_out_for_a_single_evaluation(monkeypatch, capsys):
    pairs, records = _pairs_and_provenance(n_evaluations=1, pairs_per_evaluation=25)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    assert ctx["eval_dataset"] is None
    assert ctx["heldout_rows"] == []
    assert len(ctx["train_dataset"]) == 25
    assert "single evaluation" in capsys.readouterr().out


class _FakePeftConfig:
    def to_dict(self):
        return {
            "r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0,
            "target_modules": {"q_proj", "v_proj"},
        }


class _FakeModel:
    peft_config = {"default": _FakePeftConfig()}


class _FakeTrainingArgs:
    seed = 42
    learning_rate = 5e-6
    num_train_epochs = 1
    beta = 0.1
    per_device_train_batch_size = 1
    gradient_accumulation_steps = 8


def _run_manifest_cell(split_ctx: dict[str, Any], adapter_dir: Path) -> dict[str, Any]:
    ctx = dict(split_ctx)
    ctx.update(
        {
            "ADAPTER_DIR": str(adapter_dir),
            "manifest": {"pairs_sha256": "a" * 64, "provenance_sha256": "b" * 64},
            "BASE_MODEL_NAME": "unsloth/gemma-3-4b-it",
            "BASE_MODEL_REVISION": "rev",
            "training_args": _FakeTrainingArgs(),
            "TRAINING_SEED": 42,
            "PRECISION_NAME": "float16",
            "USE_FP16": True,
            "USE_BF16": False,
            "MAX_SEQ_LENGTH": 2048,
            "model": _FakeModel(),
            "metrics": None,
        }
    )
    exec(_get_notebook_cell_code(9), ctx)  # noqa: S102
    return ctx


def test_manifest_cell_writes_heldout_file_and_records_its_hash(monkeypatch, tmp_path):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    split_ctx = _run_split_cell(monkeypatch, pairs, records)
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()

    _run_manifest_cell(split_ctx, adapter_dir)

    heldout_path = adapter_dir / "heldout_pairs.jsonl"
    heldout_bytes = heldout_path.read_bytes()
    lines = heldout_bytes.decode("utf-8").splitlines()
    assert [json.loads(line) for line in lines] == split_ctx["heldout_rows"]

    training_manifest = json.loads(
        (adapter_dir / "training_manifest.json").read_text(encoding="utf-8")
    )
    assert training_manifest["heldout"] == {
        "method": "group_by_evaluation_id",
        "seed": 42,
        "fraction": 0.2,
        "pair_count": 6,
        "evaluation_count": 2,
        "sha256": hashlib.sha256(heldout_bytes).hexdigest(),
    }


def test_manifest_cell_records_null_heldout_when_nothing_was_held_out(
    monkeypatch, tmp_path
):
    pairs, records = _pairs_and_provenance(n_evaluations=5, pairs_per_evaluation=1)
    split_ctx = _run_split_cell(monkeypatch, pairs, records)
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()

    _run_manifest_cell(split_ctx, adapter_dir)

    assert not (adapter_dir / "heldout_pairs.jsonl").exists()
    training_manifest = json.loads(
        (adapter_dir / "training_manifest.json").read_text(encoding="utf-8")
    )
    assert training_manifest["heldout"] is None


def test_packaging_cell_archives_the_heldout_file(monkeypatch, tmp_path):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    split_ctx = _run_split_cell(monkeypatch, pairs, records)
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"weights")
    _run_manifest_cell(split_ctx, adapter_dir)

    mock_requests = (
        "class _MockRequests:\n"
        "    @staticmethod\n"
        "    def post(url, files=None):\n"
        "        class _Resp:\n"
        "            def raise_for_status(self): pass\n"
        "            def json(self): return {}\n"
        "        return _Resp()\n"
        "requests = _MockRequests()\n"
    )
    code = _get_notebook_cell_code(10).replace("import requests\n", mock_requests)
    zip_path = tmp_path / "out.zip"
    code = code.replace(
        'ADAPTER_ZIP_PATH = "trained_adapter.zip"',
        f"ADAPTER_ZIP_PATH = {str(zip_path)!r}",
    )
    exec(code, {"ADAPTER_DIR": str(adapter_dir), "UPLOAD_URL": "http://mock"})  # noqa: S102

    with zipfile.ZipFile(zip_path) as zf:
        assert "heldout_pairs.jsonl" in zf.namelist()
        assert "training_manifest.json" in zf.namelist()
