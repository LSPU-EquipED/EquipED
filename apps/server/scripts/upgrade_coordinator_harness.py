"""Explicit Coordinator adapter v4 rubric cutover.

Usage: cd apps && uv run --project server python -m \
server.scripts.upgrade_coordinator_harness --actor-id UUID
"""

from __future__ import annotations

import argparse
import uuid

from server.core.database import get_session_factory
from server.modules.rubrics.service import upgrade_coordinator_harness


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish and activate Coordinator adapter v4."
    )
    parser.add_argument(
        "--actor-id",
        required=True,
        type=uuid.UUID,
        help="UUID of an active, approved administrator authorizing the cutover",
    )
    args = parser.parse_args()
    session = get_session_factory()()
    try:
        result = upgrade_coordinator_harness(session, actor_id=args.actor_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    state = "already active" if result.already_active else "activated"
    print(
        f"Coordinator adapter v4 {state}: revision {result.version_number} "
        f"({result.rubric_set_id})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
