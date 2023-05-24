import contextvars

app_context_var = contextvars.ContextVar("app")


class Reader:
    def __init__(self, ctxvar):
        self.ctxvar = ctxvar

    def __getattr__(self, key):
        return getattr(self.ctxvar.get(), key)


app = Reader(app_context_var)
