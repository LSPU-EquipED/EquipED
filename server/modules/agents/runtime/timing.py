"""Runtime timing instrumentation."""

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PhaseTimer:
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.phases: dict[str, float] = {}

    @contextmanager
    def measure(self, phase: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.phases[phase] = self.phases.get(phase, 0.0) + time.perf_counter() - t0

    def log_summary(self, prompt_chars: int = 0, parse_error: str = "") -> None:
        parts = [f"agent={self.agent_name}"]
        parts.extend(f"{phase}={secs:.3f}s" for phase, secs in self.phases.items())
        if prompt_chars:
            parts.append(f"prompt_chars={prompt_chars}")
        if parse_error:
            parts.append(f"parse_error={parse_error}")
        logger.info("[EVAL_TIMING] %s", " | ".join(parts))
