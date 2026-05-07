"""Application metadata registry for Alembic autogeneration."""

from __future__ import annotations

from server.core.database import Base


def import_model_modules() -> None:
    """Import model modules so SQLAlchemy metadata is fully registered."""

    from server.modules.auth import models as _auth_models  # noqa: F401


def get_target_metadata():
    """Return the shared SQLAlchemy metadata for migrations."""

    import_model_modules()
    return Base.metadata


__all__ = ["get_target_metadata", "import_model_modules"]
