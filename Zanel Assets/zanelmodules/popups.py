import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from zanelmodules.config import OFFICIAL_WEBSITE_URL
from zanelmodules.dialogs import ask_local_confirmation


class PopupMixin:

    def flash_state(self, text, seconds=2.5):
        self.show_toast(text, seconds)

    @staticmethod
    def toast_round(canvas, x1, y1, x2, y2, radius, **options):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]

        return canvas.create_polygon(points, smooth=True, **options)

    def show_toast(self, text, seconds=2.4):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.root.after(0, lambda: self.show_toast(text, seconds))
            except (tk.TclError, RuntimeError):
                pass
            return

        text = str(text or "").strip()

        if not text or not self.running:
            return

        try:
            if self.root.state() in ("withdrawn", "iconic"):
                return
        except tk.TclError:
            return

        self.hide_toast()
        self.toast_token += 1
        token = self.toast_token

        try:
            theme = self.theme
            transparent = "#010101"
            lowered = text.lower()

            if any(
                word in lowered
                for word in ("wait", "max", "cooldown", "loading", "already", "empty")
            ):
                symbol = "!"
            elif any(
                word in lowered
                for word in ("cleared", "reset", "saved", "renamed", "removed")
            ):
                symbol = "✓"
            else:
                symbol = "i"

            toast = tk.Toplevel(self.root)
            toast.zanel_skip = True
            toast.withdraw()
            toast.overrideredirect(True)
            toast.configure(bg=transparent)

            try:
                toast.attributes("-topmost", True)
                toast.attributes("-transparentcolor", transparent)
                toast.attributes("-alpha", 0.0)
            except tk.TclError:
                pass

            canvas = tk.Canvas(
                toast,
                width=360,
                height=200,
                bg=transparent,
                bd=0,
                highlightthickness=0,
            )
            canvas.pack()

            probe = canvas.create_text(
                0,
                0,
                text=text,
                anchor="nw",
                width=250,
                font=("Segoe UI", 9, "bold"),
            )
            bounds = canvas.bbox(probe)
            text_w = bounds[2] - bounds[0]
            text_h = bounds[3] - bounds[1]
            canvas.delete(probe)

            width = max(190, text_w + 84)
            height = text_h + 52
            bar_y = height - 12
            center_y = height // 2 - 3

            canvas.configure(width=width, height=height)

            self.toast_round(
                canvas,
                0,
                0,
                width - 1,
                height - 1,
                14,
                fill=theme["border"],
                outline="",
            )

            self.toast_round(
                canvas,
                1,
                1,
                width - 2,
                height - 2,
                13,
                fill=theme["panel"],
                outline="",
            )

            canvas.create_oval(
                17,
                center_y - 13,
                43,
                center_y + 13,
                fill=theme["button"],
                outline=theme["accent"],
                width=2,
            )

            canvas.create_text(
                30,
                center_y,
                text=symbol,
                fill=theme["accent"],
                font=("Segoe UI Symbol", 11, "bold"),
            )

            canvas.create_text(
                56,
                13,
                text="ZANEL",
                anchor="nw",
                fill=theme["accent"],
                font=("Segoe UI", 7, "bold"),
            )

            canvas.create_text(
                56,
                27,
                text=text,
                anchor="nw",
                width=250,
                fill="#E8F5ED",
                font=("Segoe UI", 9, "bold"),
            )

            bar_start = 56
            bar_end = width - 16

            canvas.create_line(
                bar_start,
                bar_y,
                bar_end,
                bar_y,
                fill=theme["track"],
                width=3,
                capstyle=tk.ROUND,
            )

            bar_item = canvas.create_line(
                bar_start,
                bar_y,
                bar_end,
                bar_y,
                fill=theme["accent"],
                width=3,
                capstyle=tk.ROUND,
            )

            canvas.configure(cursor="hand2")
            canvas.bind("<Button-1>", lambda _event: self.hide_toast())

            self.toast_bar = (canvas, bar_item, bar_start, bar_end, bar_y)
            self.toast_window = toast
            toast.update_idletasks()
            self.position_toast(0)
            toast.deiconify()

            self.toast_tick(token, time.monotonic(), max(0.4, float(seconds)))
        except tk.TclError:
            self.hide_toast()

    def position_toast(self, offset=0):
        toast = self.toast_window

        if toast is None:
            return

        width = toast.winfo_reqwidth()
        height = toast.winfo_reqheight()

        left, top, screen_w, screen_h = self.virtual_screen()

        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = (
            self.root.winfo_rooty()
            + self.root.winfo_height()
            - height
            - 96
            + offset
        )

        x = max(left + 4, min(x, left + screen_w - width - 4))
        y = max(top + 4, min(y, top + screen_h - height - 4))

        toast.geometry(f"{width}x{height}+{x}+{y}")

    def toast_tick(self, token, started, hold):
        if token != self.toast_token or self.toast_window is None:
            return

        fade_in = 0.18
        fade_out = 0.28
        elapsed = time.monotonic() - started

        try:
            if elapsed < fade_in:
                progress = 1 - (1 - elapsed / fade_in) ** 3
                alpha = 0.98 * progress
                offset = int((1 - progress) * 14)
                fraction = 1.0
            elif elapsed < fade_in + hold:
                alpha = 0.98
                offset = 0
                fraction = 1.0 - (elapsed - fade_in) / hold
            elif elapsed < fade_in + hold + fade_out:
                progress = (elapsed - fade_in - hold) / fade_out
                alpha = 0.98 * (1 - progress)
                offset = int(progress * 8)
                fraction = 0.0
            else:
                self.hide_toast()
                return

            bar = self.toast_bar

            if bar is not None:
                canvas, item, x1, x2, y = bar

                canvas.coords(
                    item,
                    x1,
                    y,
                    x1 + (x2 - x1) * max(0.0, fraction),
                    y,
                )

                canvas.itemconfigure(
                    item,
                    state="normal" if fraction > 0.02 else "hidden",
                )

            self.toast_window.attributes("-alpha", max(0.0, alpha))
            self.position_toast(offset)

            self.toast_job = self.root.after(
                16,
                lambda: self.toast_tick(token, started, hold),
            )
        except tk.TclError:
            self.hide_toast()

    def hide_toast(self):
        self.toast_token += 1

        if self.toast_job is not None:
            try:
                self.root.after_cancel(self.toast_job)
            except tk.TclError:
                pass

            self.toast_job = None

        toast = self.toast_window
        self.toast_window = None

        if toast is not None:
            try:
                toast.destroy()
            except tk.TclError:
                pass

    def preempt_info_confirmation(self):
        request = self.confirm_active

        if request is None or not request.get("info"):
            return False

        window = request.get("window")
        request["window"] = None
        self.confirm_active = None
        self.confirm_queue.appendleft(request)

        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

        return True

    def confirm(
        self,
        title,
        message,
        on_result,
        yes_text="Allow",
        no_text="Cancel",
        danger=False,
        timeout=None,
        dedupe=False,
        info=False,
        cancel_event=None,
        priority=False,
    ):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.root.after(
                    0,
                    lambda: self.confirm(
                        title,
                        message,
                        on_result,
                        yes_text,
                        no_text,
                        danger,
                        timeout,
                        dedupe,
                        info,
                        cancel_event,
                        priority,
                    ),
                )
            except (tk.TclError, RuntimeError):
                self._confirm_deliver(on_result, False)

            return

        if not self.running:
            self._confirm_deliver(on_result, False)
            return

        if dedupe:
            pending = list(self.confirm_queue)

            if self.confirm_active is not None:
                pending.append(self.confirm_active)

            for item in pending:
                if item["title"] == title and item["message"] == message:
                    return

        request = {
            "title": title,
            "message": message,
            "callback": on_result,
            "yes_text": yes_text,
            "no_text": no_text,
            "danger": danger,
            "timeout": timeout,
            "info": bool(info),
            "cancel_event": cancel_event,
            "delivered": False,
            "window": None,
        }

        if priority:
            self.confirm_queue.appendleft(request)
        else:
            self.confirm_queue.append(request)

        self._confirm_next()

    @staticmethod
    def _confirm_deliver(callback, value):
        try:
            if callback is not None:
                callback(bool(value))
        except Exception:
            pass

    def _confirm_resolve(self, request, value):
        if request["delivered"]:
            return

        request["delivered"] = True
        self._confirm_deliver(request["callback"], value)

    def _confirm_next(self):
        if not self.running:
            while self.confirm_queue:
                self._confirm_resolve(self.confirm_queue.popleft(), False)

            return

        while self.confirm_queue and self.confirm_active is None:
            request = self.confirm_queue.popleft()
            self.confirm_active = request

            try:
                self._confirm_show(request)
            except Exception:
                if self.confirm_active is request:
                    self.confirm_active = None

                self._confirm_resolve(request, False)

    def _confirm_show(self, request):
        window = tk.Toplevel(self.root)
        request["window"] = window

        try:
            self._confirm_build(window, request)
        except Exception:
            if request.get("window") is window:
                request["window"] = None

            try:
                window.destroy()
            except tk.TclError:
                pass

            raise

    def _confirm_build(self, window, request):
        theme = self.theme
        transparent = "#010101"
        danger = bool(request["danger"])
        red = "#C43F52"

        title = " ".join(
            str(request["title"] or "Confirm").split()
        )[:90]

        message = str(request["message"] or "").strip()

        if len(message) > 600:
            message = message[:599].rstrip() + "…"

        yes_text = str(request["yes_text"] or "Allow")[:14]
        no_text = str(request["no_text"] or "Cancel")[:14]

        try:
            timeout = float(request["timeout"]) if request["timeout"] else None

            if timeout is not None and timeout <= 0:
                timeout = None
        except (TypeError, ValueError):
            timeout = None

        info = bool(request.get("info"))

        if info:
            danger = False

        window.zanel_skip = True
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg=transparent)

        try:
            window.attributes("-topmost", True)
            window.attributes("-transparentcolor", transparent)
            window.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

        canvas = tk.Canvas(
            window,
            width=400,
            height=300,
            bg=transparent,
            bd=0,
            highlightthickness=0,
        )
        canvas.pack()

        text_x = 64
        text_w = 300
        width = text_x + text_w + 24

        probe = canvas.create_text(
            0,
            0,
            text=title,
            anchor="nw",
            width=text_w,
            font=("Segoe UI", 10, "bold"),
        )
        bounds = canvas.bbox(probe)
        title_h = bounds[3] - bounds[1]
        canvas.delete(probe)

        message_h = 0

        if message:
            probe = canvas.create_text(
                0,
                0,
                text=message,
                anchor="nw",
                width=text_w,
                font=("Segoe UI", 9),
            )
            bounds = canvas.bbox(probe)
            message_h = bounds[3] - bounds[1]
            canvas.delete(probe)

        message_y = 28 + title_h + 6
        buttons_y = message_y + message_h + (16 if message else 10)
        button_h = 32
        height = buttons_y + button_h + (30 if timeout else 18)
        bar_y = height - 14

        canvas.configure(width=width, height=height)

        button_font = tkfont.Font(
            family="Segoe UI",
            size=9,
            weight="bold",
        )

        yes_w = max(84, button_font.measure(yes_text) + 32)
        no_w = max(84, button_font.measure(no_text) + 32)

        yes_x2 = width - 20
        yes_x1 = yes_x2 - yes_w
        no_x2 = yes_x1 - 8
        no_x1 = no_x2 - no_w

        rects = {
            "yes": (yes_x1, buttons_y, yes_x2, buttons_y + button_h),
        }

        if not info:
            rects["no"] = (no_x1, buttons_y, no_x2, buttons_y + button_h)

        colors = {
            "yes": (
                (red, "#D9546A", "#A8323F", "#FFFFFF")
                if danger
                else (
                    theme["accent"],
                    theme["accent_hover"],
                    theme["accent_press"],
                    "#071019",
                )
            ),
            "no": (
                theme["button"],
                theme["button_hover"],
                theme["border"],
                "#DDF8E8",
            ),
        }

        accent = red if danger else theme["accent"]

        self.toast_round(
            canvas,
            0,
            0,
            width - 1,
            height - 1,
            14,
            fill=theme["border"],
            outline="",
        )

        self.toast_round(
            canvas,
            1,
            1,
            width - 2,
            height - 2,
            13,
            fill=theme["panel"],
            outline="",
        )

        canvas.create_oval(
            21,
            21,
            47,
            47,
            fill=theme["button"],
            outline=accent,
            width=2,
        )

        canvas.create_text(
            34,
            34,
            text="i" if info else ("!" if danger else "?"),
            fill=accent,
            font=("Segoe UI Symbol", 11, "bold"),
        )

        canvas.create_text(
            text_x,
            12,
            text="ZANEL",
            anchor="nw",
            fill=accent,
            font=("Segoe UI", 7, "bold"),
        )

        canvas.create_text(
            text_x,
            28,
            text=title,
            anchor="nw",
            width=text_w,
            fill="#F2F6FF",
            font=("Segoe UI", 10, "bold"),
        )

        if message:
            canvas.create_text(
                text_x,
                message_y,
                text=message,
                anchor="nw",
                width=text_w,
                fill="#C8D8D0",
                font=("Segoe UI", 9),
            )

        for name, label in (("no", no_text), ("yes", yes_text)):
            if name not in rects:
                continue

            x1, y1, x2, y2 = rects[name]

            self.toast_round(
                canvas,
                x1,
                y1,
                x2,
                y2,
                9,
                fill=colors[name][0],
                outline="",
                tags=(f"{name}_bg",),
            )

            canvas.create_text(
                (x1 + x2) // 2,
                (y1 + y2) // 2,
                text=label,
                fill=colors[name][3],
                font=("Segoe UI", 9, "bold"),
                tags=(f"{name}_txt",),
            )

        bar_start = text_x
        bar_end = width - 20
        bar_item = None

        if timeout:
            canvas.create_line(
                bar_start,
                bar_y,
                bar_end,
                bar_y,
                fill=theme["track"],
                width=3,
                capstyle=tk.ROUND,
            )

            bar_item = canvas.create_line(
                bar_start,
                bar_y,
                bar_end,
                bar_y,
                fill=accent,
                width=3,
                capstyle=tk.ROUND,
            )

        left, top, screen_w, screen_h = self.virtual_screen()
        anchor = (left, top, screen_w, screen_h)

        for host in (self.root, getattr(self, "compact_window", None)):
            try:
                if (
                    host is not None
                    and host.winfo_exists()
                    and host.state() not in ("withdrawn", "iconic")
                    and host.winfo_width() > 1
                ):
                    anchor = (
                        host.winfo_rootx(),
                        host.winfo_rooty(),
                        host.winfo_width(),
                        host.winfo_height(),
                    )
                    break
            except tk.TclError:
                continue

        x = anchor[0] + (anchor[2] - width) // 2
        y = anchor[1] + (anchor[3] - height) // 2
        x = max(left + 4, min(x, left + screen_w - width - 4))
        y = max(top + 4, min(y, top + screen_h - height - 4))

        state = {
            "closing": False,
            "job": None,
            "hover": None,
            "pressed": None,
            "alpha": 0.0,
        }

        pos = {"x": x, "y": y}
        drag = {"active": False, "dx": 0, "dy": 0}

        def set_alpha(value):
            state["alpha"] = max(0.0, min(1.0, value))

            try:
                window.attributes("-alpha", state["alpha"])
            except tk.TclError:
                pass

        def place(offset=0):
            try:
                window.geometry(
                    f"{width}x{height}+{pos['x']}+{pos['y'] + offset}"
                )
            except tk.TclError:
                pass

        def paint():
            try:
                for name in rects:
                    normal, hover_color, press_color, _ = colors[name]

                    if state["hover"] == name and state["pressed"] == name:
                        fill = press_color
                    elif state["hover"] == name:
                        fill = hover_color
                    else:
                        fill = normal

                    canvas.itemconfigure(f"{name}_bg", fill=fill)

                canvas.configure(
                    cursor=(
                        "hand2"
                        if state["hover"]
                        else ("fleur" if drag["active"] else "arrow")
                    )
                )
            except tk.TclError:
                pass

        def hit(event):
            for name, (x1, y1, x2, y2) in rects.items():
                if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                    return name

            return None

        def cancel_job():
            if state["job"] is not None:
                try:
                    window.after_cancel(state["job"])
                except tk.TclError:
                    pass

                state["job"] = None

        def destroy_window():
            try:
                window.destroy()
            except tk.TclError:
                pass

        def finish(value):
            if state["closing"]:
                return "break"

            state["closing"] = True
            cancel_job()
            self._confirm_resolve(request, value)

            closing_started = time.monotonic()
            start_alpha = state["alpha"]

            def fade():
                state["job"] = None
                progress = min(
                    1.0,
                    (time.monotonic() - closing_started) / 0.16,
                )

                set_alpha(start_alpha * (1 - progress))
                place(int(progress * 8))

                if progress >= 1.0:
                    destroy_window()
                    return

                try:
                    state["job"] = window.after(16, fade)
                except tk.TclError:
                    destroy_window()

            fade()
            return "break"

        def on_motion(event):
            if state["closing"]:
                return

            name = hit(event)

            if name != state["hover"]:
                state["hover"] = name
                paint()

        def on_leave(_event):
            state["hover"] = None
            paint()

        def on_press(event):
            if state["closing"]:
                return

            state["pressed"] = hit(event)

            if state["pressed"] is None:
                drag["active"] = True
                drag["dx"] = event.x_root - pos["x"]
                drag["dy"] = event.y_root - pos["y"]

            paint()

        def on_drag(event):
            if not drag["active"] or state["closing"]:
                return

            try:
                view_left, view_top, view_w, view_h = self.virtual_screen()

                pos["x"] = max(
                    view_left,
                    min(
                        event.x_root - drag["dx"],
                        view_left + view_w - width,
                    ),
                )

                pos["y"] = max(
                    view_top,
                    min(
                        event.y_root - drag["dy"],
                        view_top + view_h - height,
                    ),
                )

                place(0)
            except tk.TclError:
                pass

        def on_release(event):
            was_dragging = drag["active"]
            drag["active"] = False

            if state["closing"]:
                return

            pressed = state["pressed"]
            state["pressed"] = None
            name = hit(event)
            paint()

            if was_dragging:
                return

            if pressed and pressed == name:
                finish(name == "yes")

        def on_destroy(event):
            if event.widget is not window:
                return

            if request.get("window") is not window:
                return

            request["window"] = None
            state["closing"] = True
            state["job"] = None
            self._confirm_resolve(request, False)

            if self.confirm_active is request:
                self.confirm_active = None

            try:
                self.root.after(30, self._confirm_next)
            except (tk.TclError, RuntimeError, AttributeError):
                pass

        canvas.bind("<Motion>", on_motion)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        window.bind("<Return>", lambda _event: finish(True))
        window.bind("<KP_Enter>", lambda _event: finish(True))
        window.bind("<Escape>", lambda _event: finish(False))
        window.bind("<Destroy>", on_destroy, add="+")
        window.protocol("WM_DELETE_WINDOW", lambda: finish(False))

        started = time.monotonic()
        open_duration = 0.22

        def tick():
            state["job"] = None

            if state["closing"]:
                return

            cancel_event = request.get("cancel_event")
            if cancel_event is not None and cancel_event.is_set():
                finish(False)
                return

            elapsed = time.monotonic() - started
            progress = min(1.0, elapsed / open_duration)
            eased = 1 - (1 - progress) ** 3

            set_alpha(0.98 * eased)
            place(int((1 - eased) * 16))

            if timeout:
                fraction = 1.0 - elapsed / timeout

                if fraction <= 0:
                    finish(False)
                    return

                try:
                    canvas.coords(
                        bar_item,
                        bar_start,
                        bar_y,
                        bar_start + (bar_end - bar_start) * fraction,
                        bar_y,
                    )
                except tk.TclError:
                    pass

            if progress < 1.0:
                try:
                    window.lift()
                except tk.TclError:
                    pass

            if progress >= 1.0 and not timeout:
                return

            try:
                state["job"] = window.after(16, tick)
            except tk.TclError:
                state["job"] = None

        def focus_window():
            try:
                window.focus_force()
            except tk.TclError:
                pass

        place(16)
        window.update_idletasks()
        window.deiconify()
        window.lift()
        window.after(40, focus_window)
        tick()

    def show_disclaimer(self):
        self.confirm(
            "About Zanel's AI",
            "AI can make mistakes, so don't believe everything it says. "
            "Always double-check anything important.\n\n"
            "You can manually delete individual chats whenever you want.",
            None,
            yes_text="Got it",
            info=True,
            dedupe=True,
        )

    def open_official_website(self):
        threading.Thread(
            target=self._open_official_website_dialog,
            daemon=True
        ).start()

    def _open_official_website_dialog(self):
        confirmed = ask_local_confirmation(
            self.root,
            "Open Official Website",
            "Open the official Zanel Assistant website in your browser?",
            timeout=55,
        )

        if not confirmed:
            return

        try:
            webbrowser.open(OFFICIAL_WEBSITE_URL)
        except Exception:
            pass
