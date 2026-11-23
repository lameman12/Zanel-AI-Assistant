import time
import tkinter as tk
from zanelmodules.config import (
    INPUT_PLACEHOLDER,
    MAX_PASTES,
    MAX_SERVER_MESSAGE_CHARS,
    PASTE_MAX_CHARS,
    PASTE_THRESHOLD_CHARS,
    PASTE_THRESHOLD_LINES,
    VIEWER_CHUNK_CHARS,
)
from zanelmodules.storage import save_drafts
from zanelmodules.widgets import ThemedScrollbar


class PasteMixin:

    def on_paste(self, _event=None):
        try:
            data = self.root.clipboard_get()
        except tk.TclError:
            return "break"

        if not isinstance(data, str) or not data:
            return "break"

        data = data.replace("\r\n", "\n").replace("\r", "\n")

        if (
            len(data) >= PASTE_THRESHOLD_CHARS
            or data.count("\n") >= PASTE_THRESHOLD_LINES - 1
        ):
            self.add_pending_paste(data)
            return "break"

        try:
            if self.manual.get() == INPUT_PLACEHOLDER:
                self.manual.delete(0, tk.END)
                self.manual.configure(fg="#E8F5ED")

            if self.manual.selection_present():
                self.manual.delete(tk.SEL_FIRST, tk.SEL_LAST)

            self.manual.insert(tk.INSERT, data.replace("\n", " "))
        except tk.TclError:
            pass

        self.on_draft_key()
        return "break"

    def add_pending_paste(self, data):
        data = str(data or "")

        if not data.strip():
            return False

        if len(self.pending_pastes) >= MAX_PASTES:
            self.flash_state(f"Max {MAX_PASTES} pasted messages")
            return False

        trimmed = len(data) > PASTE_MAX_CHARS
        self.pending_pastes.append(data[:PASTE_MAX_CHARS])
        self.update_paste_bar()
        self.on_draft_key()

        if trimmed:
            self.flash_state(
                f"Paste trimmed to {PASTE_MAX_CHARS:,} characters"
            )

        return True

    def clear_pending_paste(self, index=None):
        if index is None:
            self.pending_pastes = []
        elif 0 <= index < len(self.pending_pastes):
            del self.pending_pastes[index]

        self.update_paste_bar()
        self.on_draft_key()

    def view_pending_paste(self, index):
        if 0 <= index < len(self.pending_pastes):
            self.open_paste_viewer(
                self.pending_pastes[index],
                editable=True,
                on_save=lambda value, i=index: self.save_pending_paste(
                    i,
                    value,
                ),
                title=f"Edit pasted message {index + 1}",
            )

    def save_pending_paste(self, index, value):
        value = str(value or "").replace("\r\n", "\n").replace("\r", "\n")

        if not 0 <= index < len(self.pending_pastes):
            return

        if not value.strip():
            self.clear_pending_paste(index)
            return

        self.pending_pastes[index] = value[:PASTE_MAX_CHARS]
        self.update_paste_bar()
        self.on_draft_key()

    def layout_paste_chips(self, _event=None):
        chips = self.paste_chip_widgets

        if not chips:
            return

        try:
            width = self.paste_chips.winfo_width()

            if width <= 1:
                width = 400

            columns = max(1, min(4, width // 120))

            if columns == self.paste_columns:
                return

            self.paste_columns = columns

            for index, chip in enumerate(chips):
                chip.grid(
                    row=index // columns,
                    column=index % columns,
                    sticky="ew",
                    padx=2,
                    pady=2,
                )

            for column in range(4):
                if column < columns:
                    self.paste_chips.grid_columnconfigure(
                        column,
                        weight=1,
                        uniform="paste_chips",
                    )
                else:
                    self.paste_chips.grid_columnconfigure(
                        column,
                        weight=0,
                        uniform="",
                    )
        except tk.TclError:
            pass

    def update_paste_bar(self):
        try:
            count = len(self.pending_pastes)

            if count == 0:
                self.paste_bar.pack_forget()
                return

            total = sum(len(item) for item in self.pending_pastes)

            self.paste_summary.configure(
                text=(
                    f"Pasted messages  ·  {count}/{MAX_PASTES}"
                    f"  ·  {total:,} characters"
                )
            )

            for child in self.paste_chips.winfo_children():
                child.destroy()

            self.paste_chip_widgets = []
            self.paste_columns = None
            theme = self.theme

            for index, item in enumerate(self.pending_pastes):
                size = len(item)
                size_text = f"{size / 1000:.1f}k" if size >= 1000 else str(size)

                chip = tk.Frame(
                    self.paste_chips,
                    bg=theme["field"],
                    highlightthickness=1,
                    highlightbackground=theme["border"],
                    cursor="hand2",
                )

                label = tk.Label(
                    chip,
                    text=f"Paste {index + 1}  ·  {size_text}",
                    fg=theme["accent"],
                    bg=theme["field"],
                    anchor="w",
                    cursor="hand2",
                    padx=6,
                    pady=3,
                    font=("Segoe UI", 8, "bold"),
                )
                label.pack(side="left", fill="x", expand=True)

                remove = tk.Button(
                    chip,
                    text="×",
                    command=lambda i=index: self.clear_pending_paste(i),
                    fg="#B9C2D0",
                    bg=theme["field"],
                    activeforeground="white",
                    activebackground="#c43f52",
                    borderwidth=0,
                    highlightthickness=0,
                    padx=6,
                    cursor="hand2",
                    font=("Segoe UI Symbol", 9),
                )
                remove.pack(side="right", fill="y")

                for widget in (chip, label):
                    widget.bind(
                        "<Button-1>",
                        lambda _event, i=index: self.view_pending_paste(i),
                    )

                self.paste_chip_widgets.append(chip)

            self.layout_paste_chips()

            if not self.paste_bar.winfo_manager():
                options = {
                    "side": "bottom",
                    "fill": "x",
                    "padx": 12,
                    "pady": (0, 6),
                }

                chat_holder = getattr(self, "chat_holder", self.chat)

                if chat_holder.winfo_manager():
                    options["before"] = chat_holder

                self.paste_bar.pack(**options)
        except tk.TclError:
            pass

    def current_input_text(self):
        value = self.manual.get()

        return "" if value == INPUT_PLACEHOLDER else value

    def store_draft(self, chat_id):
        if not chat_id:
            return

        if self.chat_store.get_chat(chat_id) is None:
            self.drafts.pop(chat_id, None)
            return

        try:
            text = self.current_input_text()
        except tk.TclError:
            return

        pastes = list(self.pending_pastes)

        if text.strip() or pastes:
            self.drafts[chat_id] = {
                "text": text[:MAX_SERVER_MESSAGE_CHARS],
                "pastes": pastes,
            }
        else:
            self.drafts.pop(chat_id, None)

    def restore_draft(self, chat_id):
        draft = self.drafts.get(chat_id) or {}
        text = str(draft.get("text") or "")

        self.pending_pastes = [
            value
            for value in (draft.get("pastes") or [])
            if isinstance(value, str) and value
        ][:MAX_PASTES]

        try:
            self.manual.delete(0, tk.END)

            try:
                focused = self.root.focus_get() is self.manual
            except (KeyError, tk.TclError):
                focused = False

            if text:
                self.manual.insert(0, text)
                self.manual.configure(fg="#E8F5ED")
            elif focused:
                self.manual.configure(fg="#E8F5ED")
            else:
                self.manual.insert(0, INPUT_PLACEHOLDER)
                self.manual.configure(fg="#6F7A74")
        except tk.TclError:
            pass

        self.update_paste_bar()

    def on_draft_key(self, _event=None):
        self.store_draft(self.active_chat_id)
        self.schedule_draft_save()

    def schedule_draft_save(self):
        if self.draft_job is not None:
            try:
                self.root.after_cancel(self.draft_job)
            except tk.TclError:
                pass

        try:
            self.draft_job = self.root.after(700, self.persist_drafts)
        except (tk.TclError, RuntimeError):
            self.draft_job = None

    def persist_drafts(self):
        self.draft_job = None
        data = {}

        for chat_id, draft in list(self.drafts.items()):
            meta = self.chat_store.get_chat(chat_id)

            if meta is None or meta.get("anonymous"):
                continue

            data[chat_id] = draft

        save_drafts(data)

    def viewer_is_open(self):
        overlay = self.viewer_window

        if overlay is None:
            return False

        try:
            return bool(overlay.winfo_exists())
        except tk.TclError:
            return False

    def open_paste_viewer(
        self,
        text,
        editable=False,
        on_save=None,
        title="Pasted message",
    ):
        if not isinstance(text, str):
            return

        if not editable and not text:
            return

        if self.viewer_is_open():
            return

        theme = self.theme
        total = len(text)
        top_offset = 42
        state = {"closing": False, "job": None}
        loaded = {"count": 0, "busy": False}

        overlay = tk.Frame(self.root, bg=theme["bg"])
        self.viewer_window = overlay

        header = tk.Frame(overlay, bg=theme["title"], height=44)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Button(
            header,
            text="←  Back",
            command=lambda: request_close(),
            fg="#DDF8E8",
            bg=theme["button"],
            activeforeground="white",
            activebackground=theme["button_hover"],
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            font=("Segoe UI Symbol", 9, "bold"),
        ).pack(side="left", padx=(12, 0), pady=7)

        title_box = tk.Frame(header, bg=theme["title"])
        title_box.pack(side="left", padx=(12, 0))

        tk.Label(
            title_box,
            text=title,
            fg="#F2F6FF",
            bg=theme["title"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        meta_label = tk.Label(
            title_box,
            text="",
            fg="#8290A8",
            bg=theme["title"],
            font=("Segoe UI", 8),
        )
        meta_label.pack(anchor="w")

        save_button = None

        if editable:
            save_button = tk.Button(
                header,
                text="Save",
                fg="#071019",
                bg=theme["accent"],
                activeforeground="#071019",
                activebackground=theme["accent_hover"],
                borderwidth=0,
                relief="flat",
                padx=14,
                pady=5,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            save_button.pack(side="right", padx=(6, 12), pady=7)

        copy_button = tk.Button(
            header,
            text="Copy all",
            fg="#DDF8E8" if editable else "#071019",
            bg=theme["button"] if editable else theme["accent"],
            activeforeground="white" if editable else "#071019",
            activebackground=(
                theme["button_hover"]
                if editable
                else theme["accent_hover"]
            ),
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        copy_button.pack(
            side="right",
            padx=(0, 0 if editable else 12),
            pady=7,
        )

        tk.Frame(
            overlay,
            bg=theme["accent"],
            height=2,
        ).pack(fill="x", side="top")

        footer = tk.Frame(overlay, bg=theme["title"], height=26)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        status = tk.Label(
            footer,
            text="",
            fg="#8290A8",
            bg=theme["title"],
            font=("Segoe UI", 8),
        )
        status.pack(side="left", padx=14)

        body = tk.Frame(
            overlay,
            bg=theme["panel"],
            highlightthickness=1,
            highlightbackground=theme["border"],
        )
        body.pack(fill="both", expand=True, padx=12, pady=(10, 8))

        scrollbar = ThemedScrollbar(
            body,
            orient="vertical",
            bg=theme["track"],
            track=theme["panel"],
            thumb=theme["accent"],
            width=6,
        )
        scrollbar.pack(side="right", fill="y")

        text_widget = tk.Text(
            body,
            wrap="word",
            undo=editable,
            maxundo=200 if editable else 0,
            bg=theme["panel"],
            fg="#E8F5ED",
            insertbackground="white",
            selectbackground="#2d405c",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=14,
            pady=12,
            font=("Segoe UI", self.font_size),
        )
        text_widget.pack(side="left", fill="both", expand=True)

        def current_text():
            return text_widget.get("1.0", "end-1c")

        def has_changes():
            return editable and current_text() != text

        def update_status(_event=None):
            try:
                if editable:
                    count = len(current_text())

                    meta_label.configure(text=f"{count:,} characters")

                    status.configure(
                        text=(
                            f"{count:,} / {PASTE_MAX_CHARS:,} characters"
                            "  ·  Ctrl+S to save  ·  Esc to go back"
                        ),
                        fg="#FF6B7A" if count > PASTE_MAX_CHARS else "#8290A8",
                    )
                else:
                    meta_label.configure(text=f"{total:,} characters")

                    more = (
                        "  ·  scroll down to load more"
                        if loaded["count"] < total
                        else ""
                    )

                    status.configure(
                        text=(
                            f"Showing {loaded['count']:,} of "
                            f"{total:,} characters{more}"
                            "  ·  Esc to go back"
                        ),
                        fg="#8290A8",
                    )
            except tk.TclError:
                pass

        def load_chunk():
            if loaded["busy"] or loaded["count"] >= total:
                return

            loaded["busy"] = True

            try:
                start = loaded["count"]
                end = total if editable else min(total, start + VIEWER_CHUNK_CHARS)

                if end < total:
                    cut = text.rfind("\n", start, end)

                    if cut <= start + VIEWER_CHUNK_CHARS // 2:
                        cut = text.rfind(" ", start, end)

                    if cut > start + VIEWER_CHUNK_CHARS // 2:
                        end = cut + 1

                text_widget.insert("end", text[start:end])
                loaded["count"] = end
                update_status()
            except tk.TclError:
                pass
            finally:
                loaded["busy"] = False

        def on_scroll(first, last):
            try:
                scrollbar.set(first, last)

                if loaded["count"] < total and float(last) >= 0.97:
                    overlay.after_idle(load_chunk)
            except (tk.TclError, ValueError):
                pass

        scrollbar.configure(command=text_widget.yview)
        text_widget.configure(yscrollcommand=on_scroll)

        def focus_text():
            try:
                text_widget.focus_set()
            except tk.TclError:
                pass

        def finish_close():
            if self.viewer_window is overlay:
                self.viewer_window = None

            self.viewer_closer = None

            try:
                overlay.destroy()
            except tk.TclError:
                pass

        def animate(opening):
            try:
                self.root.update_idletasks()
                distance = max(1, self.root.winfo_height() - top_offset)
            except tk.TclError:
                return

            started = time.monotonic()
            duration = 0.26 if opening else 0.2

            def step():
                state["job"] = None

                if not self.running:
                    return

                progress = min(1.0, (time.monotonic() - started) / duration)

                if opening:
                    offset = int(distance * (1 - progress) ** 3)
                else:
                    offset = int(distance * progress ** 2)

                try:
                    overlay.place(
                        x=0,
                        y=top_offset + offset,
                        relwidth=1.0,
                        relheight=1.0,
                        height=-top_offset,
                    )
                except tk.TclError:
                    return

                if progress >= 1.0:
                    if opening:
                        focus_text()
                    else:
                        finish_close()

                    return

                try:
                    state["job"] = overlay.after(12, step)
                except tk.TclError:
                    state["job"] = None

            step()

        def request_close(animate_out=True, force=False):
            if state["closing"]:
                return "break"

            if editable and not force and has_changes():
                self.confirm(
                    "Discard changes",
                    "Close without saving your changes?",
                    lambda ok: request_close(animate_out, True) if ok else None,
                    yes_text="Discard",
                    no_text="Keep editing",
                    danger=True,
                    dedupe=True,
                )
                return "break"

            state["closing"] = True

            if state["job"] is not None:
                try:
                    overlay.after_cancel(state["job"])
                except tk.TclError:
                    pass

                state["job"] = None

            if animate_out:
                animate(False)
            else:
                finish_close()

            return "break"

        def save_and_close(_event=None):
            if not editable or on_save is None:
                return "break"

            try:
                on_save(current_text())
            except Exception:
                pass

            request_close(True, True)
            return "break"

        def copy_all():
            try:
                value = current_text() if editable else text
                self.root.clipboard_clear()
                self.root.clipboard_append(value)
                copy_button.configure(text="Copied")
                overlay.after(
                    1500,
                    lambda: copy_button.configure(text="Copy all"),
                )
            except tk.TclError:
                pass

        def select_all(_event=None):
            text_widget.tag_add("sel", "1.0", "end-1c")
            return "break"

        copy_button.configure(command=copy_all)

        if save_button is not None:
            save_button.configure(command=save_and_close)

        if editable:
            text_widget.bind("<KeyRelease>", update_status)
            text_widget.bind("<ButtonRelease-1>", update_status)
            text_widget.bind("<Control-s>", save_and_close)
            text_widget.bind("<Control-a>", select_all)
        else:
            def block_edit(event):
                if event.keysym in (
                    "Left", "Right", "Up", "Down",
                    "Prior", "Next", "Home", "End",
                ):
                    return None

                if event.state & 0x4 and event.keysym.lower() in ("c", "a"):
                    return None

                return "break"

            text_widget.bind("<Key>", block_edit)
            text_widget.bind("<Control-a>", select_all)
            text_widget.bind("<<Paste>>", lambda _event: "break")
            text_widget.bind("<<Cut>>", lambda _event: "break")
            text_widget.bind("<Button-2>", lambda _event: "break")

        text_widget.bind("<Escape>", lambda _event: request_close())

        self.viewer_closer = request_close

        load_chunk()
        update_status()

        try:
            self.root.update_idletasks()
            overlay.place(
                x=0,
                y=top_offset + max(1, self.root.winfo_height() - top_offset),
                relwidth=1.0,
                relheight=1.0,
                height=-top_offset,
            )
            overlay.lift()
        except tk.TclError:
            return

        animate(True)
