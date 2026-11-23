import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import math
from zanelmodules.config import (
    CHAT_CREATE_COOLDOWN,
    CHAT_DELETE_COOLDOWN,
    CHAT_SWITCH_COOLDOWN,
    MAX_CHATS,
    RENAME_COOLDOWN,
    RENAME_MAX_CHARS,
)


class SidebarMixin:

    def refresh_sidebar(self):
        container = getattr(self, "chat_list", None)

        if container is None:
            return

        try:
            self.chat_canvas.itemconfigure(
                self.chat_list_window,
                state="hidden",
            )

            for child in container.winfo_children():
                child.destroy()

            self.sidebar_rows = {}
            chats = self.chat_store.list_chats()
            self.sidebar_count.configure(text=f"{len(chats)}/{MAX_CHATS}")

            for meta in chats:
                self.build_chat_row(container, meta)

            container.update_idletasks()
            self.chat_canvas.configure(
                scrollregion=self.chat_canvas.bbox("all") or (0, 0, 0, 0)
            )
        except tk.TclError:
            pass
        finally:
            try:
                self.chat_canvas.itemconfigure(
                    self.chat_list_window,
                    state="normal",
                )
            except tk.TclError:
                pass

    def refresh_sidebar_threadsafe(self):
        try:
            self.root.after(0, self.refresh_sidebar)
        except tk.TclError:
            pass

    @staticmethod
    def relative_time(stamp, anonymous=False):
        if anonymous:
            return "Not saved"

        try:
            delta = max(0.0, time.time() - float(stamp))
        except (TypeError, ValueError):
            return ""

        if delta < 60:
            return "Just now"

        if delta < 3600:
            return f"{int(delta // 60)} min ago"

        if delta < 86400:
            return f"{int(delta // 3600)} h ago"

        return f"{int(delta // 86400)} d ago"

    def build_chat_row(self, container, meta):
        chat_id = meta["id"]
        active = chat_id == self.active_chat_id
        loading = active and self.chat_loading
        anonymous = bool(meta.get("anonymous"))
        row_bg = self.theme["button"] if active else self.theme["panel"]
        cursor = "watch" if self.chat_loading else "hand2"

        row = tk.Frame(container, bg=row_bg, cursor=cursor)
        row.pack(fill="x", pady=1, padx=2)

        bar = tk.Frame(
            row,
            bg=self.theme["accent"] if active else row_bg,
            width=3,
        )
        bar.pack(side="left", fill="y")

        delete = tk.Button(
            row,
            text="×",
            command=lambda cid=chat_id: self.delete_chat(cid),
            fg="#8290A8" if active else "#56677A",
            bg=row_bg,
            activeforeground="white",
            activebackground="#c43f52",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            cursor="hand2",
            font=("Segoe UI Symbol", 10),
        )
        delete.pack(side="right", fill="y")

        rename = tk.Button(
            row,
            text="✎",
            command=lambda cid=chat_id: self.open_rename_dialog(cid),
            fg="#8290A8" if active else "#56677A",
            bg=row_bg,
            activeforeground="#071019",
            activebackground=self.theme["accent"],
            borderwidth=0,
            highlightthickness=0,
            padx=6,
            cursor="hand2",
            font=("Segoe UI Symbol", 10),
        )
        rename.pack(side="right", fill="y")

        box = tk.Frame(row, bg=row_bg, cursor=cursor)
        box.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

        title = ("◌  " if anonymous else "") + meta["name"]

        name_label = tk.Label(
            box,
            text=title,
            anchor="w",
            fg="#F2F6FF" if active else "#C8D8D0",
            bg=row_bg,
            cursor=cursor,
            font=("Segoe UI Symbol", 9, "bold" if active else "normal"),
        )
        name_label.pack(fill="x")

        title_font = tkfont.Font(
            family="Segoe UI Symbol",
            size=9,
            weight="bold" if active else "normal",
        )

        def fit_title(event, label=name_label, full=title, font=title_font):
            available = event.width - 4

            if available <= 10:
                return

            if font.measure(full) <= available:
                text = full
            else:
                text = full

                while text and font.measure(text + "…") > available:
                    text = text[:-1]

                text = text.rstrip() + "…"

            if label.cget("text") != text:
                label.configure(text=text)

        name_label.bind("<Configure>", fit_title)

        subtitle = (
            "Loading…"
            if loading
            else self.relative_time(meta.get("updated"), anonymous)
        )

        if chat_id in self.busy_chats and not loading:
            subtitle = "Replying…"

        sub_label = tk.Label(
            box,
            text=subtitle,
            anchor="w",
            fg="#8290A8",
            bg=row_bg,
            cursor=cursor,
            font=("Segoe UI", 8),
        )
        sub_label.pack(fill="x")

        for widget in (row, bar, box, name_label, sub_label):
            widget.bind(
                "<Button-1>",
                lambda _event, cid=chat_id: self.switch_chat(cid),
            )
            widget.bind(
                "<Enter>",
                lambda _event, cid=chat_id: self.sidebar_hover(cid, True),
            )
            widget.bind(
                "<Leave>",
                lambda _event, cid=chat_id: self.sidebar_leave(cid),
            )

        self.sidebar_rows[chat_id] = {
            "row": row,
            "bar": bar,
            "box": box,
            "label": name_label,
            "sub": sub_label,
            "delete": delete,
            "rename": rename,
            "active": active,
        }

    def sidebar_hover(self, chat_id, inside):
        entry = self.sidebar_rows.get(chat_id)

        if not entry or entry["active"]:
            return

        color = self.theme["button_hover"] if inside else self.theme["panel"]

        try:
            for key in ("row", "bar", "box", "label", "sub", "delete", "rename"):
                entry[key].configure(bg=color)

            hover_fg = "#C8D8D0" if inside else "#56677A"
            entry["delete"].configure(fg=hover_fg)
            entry["rename"].configure(fg=hover_fg)
        except tk.TclError:
            pass

    def sidebar_leave(self, chat_id):
        entry = self.sidebar_rows.get(chat_id)

        if not entry:
            return

        try:
            row = entry["row"]
            pointer_x, pointer_y = row.winfo_pointerxy()
            target = row.winfo_containing(pointer_x, pointer_y)
            inside = target is not None and (
                target is row or str(target).startswith(str(row) + ".")
            )
        except (tk.TclError, KeyError):
            inside = False

        self.sidebar_hover(chat_id, inside)

    def open_rename_dialog(self, chat_id):
        meta = self.chat_store.get_chat(chat_id)

        if meta is None:
            return

        remaining = RENAME_COOLDOWN - (time.time() - self.last_rename_time)

        if remaining > 0:
            self.flash_state(f"Wait {math.ceil(remaining)}s to rename again")
            return

        existing = self.rename_window

        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except tk.TclError:
                pass

            self.rename_window = None

        theme = self.theme
        width = 300
        height = 156

        window = tk.Toplevel(self.root)
        self.rename_window = window
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg=theme["border"])

        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass

        left, top, screen_w, screen_h = self.virtual_screen()

        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        x = max(left + 4, min(x, left + screen_w - width - 4))
        y = max(top + 4, min(y, top + screen_h - height - 4))

        window.geometry(f"{width}x{height}+{x}+{y}")

        inner = tk.Frame(window, bg=theme["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Label(
            inner,
            text="Rename chat",
            fg=theme["accent"],
            bg=theme["panel"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))

        field = tk.Frame(
            inner,
            bg=theme["field"],
            highlightthickness=1,
            highlightbackground=theme["border"],
            highlightcolor=theme["accent"],
        )
        field.pack(fill="x", padx=16)

        name_var = tk.StringVar(value=meta["name"][:RENAME_MAX_CHARS])

        entry = tk.Entry(
            field,
            textvariable=name_var,
            bg=theme["field"],
            fg="#E8F5ED",
            insertbackground="white",
            selectbackground=theme["accent"],
            selectforeground="#071019",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        entry.pack(fill="x", padx=10, pady=8)

        status = tk.Label(
            inner,
            text="",
            fg="#FF6B7A",
            bg=theme["panel"],
            font=("Segoe UI", 8),
        )
        status.pack(anchor="w", padx=16, pady=(4, 0))

        def limit_length(*_args):
            value = name_var.get()

            if len(value) > RENAME_MAX_CHARS:
                name_var.set(value[:RENAME_MAX_CHARS])

            try:
                status.configure(text="")
            except tk.TclError:
                pass

        name_var.trace_add("write", limit_length)

        def close_dialog(_event=None):
            if self.rename_window is window:
                self.rename_window = None

            try:
                window.destroy()
            except tk.TclError:
                pass

            return "break"

        def save_name(_event=None):
            value = " ".join(name_var.get().split())

            if not value:
                status.configure(text="Name can't be empty.")
                return "break"

            current = self.chat_store.get_chat(chat_id)

            if current is not None and current["name"] != value:
                self.chat_store.rename(chat_id, value, True)
                self.last_rename_time = time.time()
                self.refresh_sidebar()

            close_dialog()
            return "break"

        buttons = tk.Frame(inner, bg=theme["panel"])
        buttons.pack(side="bottom", fill="x", padx=16, pady=(0, 14))

        tk.Button(
            buttons,
            text="Cancel",
            command=close_dialog,
            fg="#DDF8E8",
            bg=theme["button"],
            activeforeground="white",
            activebackground=theme["button_hover"],
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        tk.Button(
            buttons,
            text="Save",
            command=save_name,
            fg="#071019",
            bg=theme["accent"],
            activeforeground="#071019",
            activebackground=theme["accent_hover"],
            borderwidth=0,
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        entry.bind("<Return>", save_name)
        entry.bind("<Escape>", close_dialog)

        def focus_entry():
            try:
                window.focus_force()
                entry.focus_set()
                entry.selection_range(0, "end")
                entry.icursor("end")
            except tk.TclError:
                pass

        window.after(60, focus_entry)
        try:
            window.update_idletasks()
            window.deiconify()
            window.lift()
        except tk.TclError:
            if self.rename_window is window:
                self.rename_window = None
            try:
                window.destroy()
            except tk.TclError:
                pass
            self.flash_state("Could not open the rename dialog.")

    def init_chats(self):
        chats = self.chat_store.list_chats()
        target = None
        last = self.chat_store.last_active

        if last and any(meta["id"] == last for meta in chats):
            target = last
        elif chats:
            target = chats[0]["id"]

        if target is None:
            meta = self.chat_store.create(False)
            target = meta["id"] if meta else None

        self.refresh_sidebar()

        if target:
            self.activate_chat(target, force=True)

    def switch_chat(self, chat_id):
        self.activate_chat(chat_id, force=False)

    def new_chat(self, anonymous=False):
        if self.chat_loading:
            self.flash_state("Chat is loading…")
            return

        if anonymous:
            existing = self.chat_store.anonymous_id()

            if existing:
                if existing != self.active_chat_id:
                    self.switch_chat(existing)
                else:
                    self.flash_state("Only one anonymous chat allowed")

                return

        remaining = CHAT_CREATE_COOLDOWN - (time.time() - self.last_chat_create)

        if remaining > 0:
            self.flash_state(f"Wait {math.ceil(remaining)}s for a new chat")
            return

        if self.chat_store.count() >= MAX_CHATS:
            self.flash_state(f"Max {MAX_CHATS} chats reached")
            return

        active = self.chat_store.get_chat(self.active_chat_id)

        if (
            active
            and bool(active.get("anonymous")) == bool(anonymous)
            and not self.chat_store.has_messages(self.active_chat_id)
        ):
            self.flash_state("This chat is already empty")
            return

        meta = self.chat_store.create(anonymous)

        if meta is None:
            self.flash_state(f"Max {MAX_CHATS} chats reached")
            return

        self.last_chat_create = time.time()
        self.activate_chat(meta["id"], force=True)

    def activate_chat(self, chat_id, force=False):
        if self.chat_store.get_chat(chat_id) is None:
            return False

        if not force:
            if self.chat_loading:
                self.flash_state("Chat is still loading, please wait")
                return False

            if chat_id == self.active_chat_id:
                return False

            remaining = CHAT_SWITCH_COOLDOWN - (time.time() - self.last_chat_switch)

            if remaining > 0:
                self.flash_state(f"Wait {math.ceil(remaining)}s")
                return False

        previous_chat = self.active_chat_id

        if previous_chat:
            self.store_draft(previous_chat)

        self.chat_store.flush()
        self.load_token += 1
        token = self.load_token
        self.last_chat_switch = time.time()
        self.active_chat_id = chat_id
        self.chat_store.set_last_active(chat_id)

        if previous_chat != chat_id:
            self.restore_draft(chat_id)
            self.schedule_draft_save()
        self.chat_loading = True
        self.deferred_entries = []
        self.history_entries = []
        self.history_start = 0
        self.loading_older = False
        self.reset_chat_view()
        self.set_chat_visible(False)
        self.show_loading_label(True)
        self.refresh_sidebar()

        threading.Thread(
            target=self._read_history,
            args=(token, chat_id),
            daemon=True,
        ).start()

        return True

    def delete_chat(self, chat_id):
        meta = self.chat_store.get_chat(chat_id)

        if meta is None:
            return

        if self.chat_loading:
            self.flash_state("Chat is loading…")
            return

        if chat_id in self.busy_chats:
            self.flash_state("Wait for the reply")
            return

        remaining = CHAT_DELETE_COOLDOWN - (time.time() - self.last_chat_delete)

        if remaining > 0:
            self.flash_state(f"Wait {math.ceil(remaining)}s")
            return

        if self.chat_store.has_messages(chat_id):
            if meta.get("anonymous"):
                question = "Close this anonymous chat? It will be deleted permanently."
            else:
                question = (
                    f"Delete \"{meta['name']}\"? "
                    "Its messages will be removed permanently."
                )

            self.confirm(
                "Delete chat",
                question,
                lambda ok: self.finish_delete_chat(chat_id) if ok else None,
                yes_text="Delete",
                no_text="Keep",
                danger=True,
                dedupe=True,
            )
            return

        self.finish_delete_chat(chat_id)

    def finish_delete_chat(self, chat_id):
        if self.chat_store.get_chat(chat_id) is None:
            return

        if self.chat_loading:
            self.flash_state("Chat is loading…")
            return

        if chat_id in self.busy_chats:
            self.flash_state("Wait for the reply")
            return

        self.last_chat_delete = time.time()
        was_active = chat_id == self.active_chat_id

        self.chat_store.delete(chat_id)
        self.drafts.pop(chat_id, None)
        self.schedule_draft_save()
        self.start_server_cleanup()

        if not was_active:
            self.refresh_sidebar()
            return

        self.active_chat_id = None
        remaining_chats = self.chat_store.list_chats()

        if remaining_chats:
            target = remaining_chats[0]["id"]
        else:
            created = self.chat_store.create(False)
            target = created["id"] if created else None

        if target:
            self.activate_chat(target, force=True)
        else:
            self.reset_chat_view()
            self.refresh_sidebar()
