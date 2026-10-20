"""Bounded public ITSO errors shared by admission and saved-result reads."""


class ITSOError(RuntimeError):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status
        super().__init__(code)
