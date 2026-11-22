import time
import tkinter as tk
import tkinter.messagebox as messagebox


def ask_local_confirmation(root, title, message, timeout=55):
    app = getattr(root, "zanel_app", None)
    cancel_event = getattr(app, "current_cancel_event", None)
    result = {"ok": False, "done": False}
    pending_status = app is not None and all(
        hasattr(app, attribute)
        for attribute in (
            "messages",
            "permission_status_lock",
            "pending_permission_count",
            "busy_chats",
            "mic_muted",
        )
    )

    if cancel_event is not None and cancel_event.is_set():
        return False

    if app is not None and getattr(app, "auto_allow_actions", False):
        return True

    def deliver(value):
        if result["done"]:
            return

        result["ok"] = bool(value)
        result["done"] = True

        if pending_status:
            with app.permission_status_lock:
                app.pending_permission_count = max(
                    0,
                    app.pending_permission_count - 1,
                )
                has_pending = app.pending_permission_count > 0

            if not has_pending:
                if (
                    cancel_event is not None
                    and cancel_event.is_set()
                ):
                    status = "Cancelling…"
                else:
                    status = (
                        "Zanel is thinking…"
                        if app.busy_chats
                        else "Mic Muted" if app.mic_muted else "Listening"
                    )

                app.messages.put(("state", status))

    lowered = str(title).lower()
    danger = any(
        word in lowered
        for word in (
            "run a command",
            "close",
            "lock",
            "delete",
            "uninstall",
        )
    )

    def show():
        try:
            if app is None:
                deliver(
                    messagebox.askyesno(title, message, parent=root)
                )
                return

            app.confirm(
                title,
                message,
                deliver,
                yes_text="Allow",
                no_text="Deny",
                danger=danger,
                timeout=timeout,
                cancel_event=cancel_event,
            )
        except Exception:
            deliver(False)

    try:
        if pending_status:
            with app.permission_status_lock:
                app.pending_permission_count += 1
                app.messages.put(("state", "Pending Permission"))

        root.after(0, show)
    except (tk.TclError, RuntimeError):
        if pending_status and not result["done"]:
            deliver(False)
        return False

    deadline = time.time() + timeout + 10

    while time.time() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            deliver(False)
            return False

        if result["done"]:
            return result["ok"]

        time.sleep(0.05)

    deliver(False)
    return False
