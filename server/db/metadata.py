"""Application metadata registry for Alembic autogeneration."""

from __future__ import annotations

from server.core.database import Base


def import_model_modules() -> None:
    """Import model modules so SQLAlchemy metadata is fully registered."""

    from server.modules.auth import models as _auth_models  # noqa: F401
    from server.modules.admin import models as _admin_models  # noqa: F401
    from server.modules.documents import models as _document_models  # noqa: F401
    from server.modules.evaluations import models as _evaluation_models  # noqa: F401
    from server.modules.feedback import models as _feedback_models  # noqa: F401
    from server.modules.synthesis import models as _synthesis_models  # noqa: F401


def get_target_metadata():
    """Return the shared SQLAlchemy metadata for migrations."""

    import_model_modules()
    return Base.metadata


__all__ = ["get_target_metadata", "import_model_modules"]
