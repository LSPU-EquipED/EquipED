from __future__ import annotations

import subprocess
import sys

CODE = """
import server.modules.admin.models
from server.core.database import Base
t = Base.metadata.tables['model_validations']
[fk.column for fk in t.c.adapter_id.foreign_keys]
"""


def test_admin_models_alone_resolve_adapter_foreign_key():
    """Importing only admin models must register the trained_adapters table."""
    result = subprocess.run(
        [sys.executable, "-c", CODE], capture_output=True, text=True
    )
    assert "NoReferencedTableError" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
