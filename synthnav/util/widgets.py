import tkinter as tk


class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        self.event_callback = kwargs.pop("command", None)
        auto_select = kwargs.pop("auto_select", True)

        # https://stackoverflow.com/questions/3169344/undo-and-redo-features-in-a-tkinter-text-widget
        if "undo" not in kwargs:
            kwargs["undo"] = True

        if "maxundo" not in kwargs:
            kwargs["maxundo"] = -1

        if "autoseparators" not in kwargs:
            kwargs["autoseparators"] = True

        super().__init__(*args, **kwargs)
        if self.event_callback:
            self.bind("<<Modified>>", self._handle_modified_event)
            self.edit_modified(0)

        if auto_select:
            self.bind("<Control-Key-a>", self._handle_select_all)

    def _handle_modified_event(self, event):
        self.event_callback(event)
        self.edit_modified(0)

    def _handle_select_all(self, _event):
        self.tag_add(tk.SEL, "1.0", tk.END)
        self.mark_set(tk.INSERT, "1.0")
        self.see(tk.INSERT)
        return "break"
