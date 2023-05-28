import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .experiment_treetest import UIMockup  # noqa

app_context_var = contextvars.ContextVar("app")


class Reader:
    def __init__(self, ctxvar):
        self.ctxvar = ctxvar

    def __getattr__(self, key):
        return getattr(self.ctxvar.get(), key)


app: "UIMockup" = Reader(app_context_var)
