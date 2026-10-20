"""Installed harness boundaries: host-independent, network I/O only in tools."""

import ast
import subprocess
import sys
from pathlib import Path

import equiped_harness


def test_source_import_boundary():
    root = Path(equiped_harness.__file__).parent
    forbidden = {
        "server",
        "sqlalchemy",
        "chromadb",
        "fastapi",
        "os",
        "dotenv",
    }
    for source in root.rglob("*.py"):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            elif isinstance(node, ast.Call):
                dynamic = (
                    isinstance(node.func, ast.Name) and node.func.id == "__import__"
                ) or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                )
                if dynamic:
                    assert node.args and isinstance(node.args[0], ast.Constant), source
                    names = [node.args[0].value]
            for name in names:
                assert name.split(".")[0] not in forbidden, (source, name)
                if "tools" not in source.relative_to(root).parts:
                    assert name.split(".")[0] not in {
                        "requests",
                        "httpx",
                        "socket",
                        "aiohttp",
                    }, (source, name)
                    assert not name.startswith(("urllib.request", "http.client")), (
                        source,
                        name,
                    )


def test_installed_import_without_backend_path(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "from equiped_harness import EvaluationRequest, ExecutionConfig, evaluate; "
            "from equiped_harness import SME, Coordinator, GAD, ITSO; "
            "import equiped_harness.contracts; "
            "import equiped_harness.manifests; "
            "import equiped_harness.contracts.snapshots; "
            "import equiped_harness.strategies.calculators; "
            "import sys; assert 'server' not in sys.modules",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
