import threading
import time
import tkinter as tk
from pathlib import Path
import sys
from zanelmodules.config import API_KEY_FILE, APP_DATA_DIR, DEFAULT_THEME


class ApiKeyMixin:

    @staticmethod
    def _is_invalid_key_message(text):
        lowered = str(text or "").lower()

        if "key" not in lowered:
            return False

        return any(
            word in lowered
            for word in (
                "invalid",
                "unauthorized",
                "rejected",
                "revoked",
                "expired",
                "not valid",
            )
        )

    def delete_api_key_files(self):
        candidates = [API_KEY_FILE]

        try:
            candidates.append(
                Path(sys.executable).resolve().parent / "api_key.txt"
            )
        except Exception:
            pass

        try:
            candidates.append(
                Path(__file__).resolve().parent / "api_key.txt"
            )
        except Exception:
            pass

        try:
            candidates.append(
                Path.home() / "AppData" / "Local" / "Zanel" / "api_key.txt"
            )
        except Exception:
            pass

        try:
            candidates.append(
                Path.home() / "AppData" / "Roaming" / "Zanel" / "api_key.txt"
            )
        except Exception:
            pass

        seen = set()

        for candidate in candidates:
            try:
                key = str(Path(candidate).resolve()).lower()

                if key in seen:
                    continue

                seen.add(key)

                if not Path(candidate).is_file():
                    continue

                try:
                    Path(candidate).unlink()
                except OSError:
                    try:
                        Path(candidate).write_text("", encoding="utf-8")
                    except OSError:
                        pass
            except Exception:
                continue

    def handle_invalid_key(self):
        with self.key_lock:
            if (
                self.invalid_key_active
                or not self.running
                or not self.api_key
            ):
                return

            self.invalid_key_active = True

        try:
            self.root.after(0, self.show_invalid_key_notice)
        except (tk.TclError, RuntimeError):
            with self.key_lock:
                self.invalid_key_active = False

    def show_invalid_key_notice(self):
        if not self.running:
            return

        self.confirm(
            "Invalid API key",
            "Your API key is no longer valid. "
            "You will be logged out in 10 seconds.",
            lambda _ok: self.logout_invalid_key(),
            yes_text="OK",
            info=True,
            timeout=10,
            dedupe=True,
        )

    def logout_invalid_key(self):
        if not self.running:
            return

        self.api_key = ""
        self.last_action_feedback = ""
        self.delete_api_key_files()

        self.hide_toast()

        closer = getattr(self, "viewer_closer", None)

        if closer is not None:
            try:
                closer(False, True)
            except Exception:
                pass

        if self.settings_frame is not None:
            try:
                self.close_settings(force=True)
            except Exception:
                pass

        self.set_mic(True)

        compact = self.compact_window

        if compact is not None:
            try:
                compact.destroy()
            except tk.TclError:
                pass

            self.compact_window = None

        self.root.after(150, self.resume_taskbar_icon)

        self.normal_geometry = None

        try:
            self.root.withdraw()
        except tk.TclError:
            pass

        self.show_api_key_window()

    def load_api_key(self):
        candidates = []

        try:
            candidates.append(API_KEY_FILE)
        except Exception:
            pass

        try:
            candidates.append(
                Path(sys.executable).resolve().parent / "api_key.txt"
            )
        except Exception:
            pass

        try:
            candidates.append(
                Path(__file__).resolve().parent / "api_key.txt"
            )
        except Exception:
            pass

        try:
            candidates.append(
                Path.home() / "AppData" / "Local" / "Zanel" / "api_key.txt"
            )
        except Exception:
            pass

        try:
            candidates.append(
                Path.home() / "AppData" / "Roaming" / "Zanel" / "api_key.txt"
            )
        except Exception:
            pass

        seen = set()

        for candidate in candidates:
            try:
                candidate = Path(candidate).expanduser().resolve()
                key = str(candidate).lower()

                if key in seen:
                    continue

                seen.add(key)

                if not candidate.is_file():
                    continue

                value = candidate.read_text(
                    encoding="utf-8-sig"
                ).strip()

                if value:
                    return value

            except (OSError, UnicodeError, ValueError):
                continue
            except Exception:
                continue

        return ""

    def save_api_key(self, key):
        APP_DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        API_KEY_FILE.write_text(
            key.strip(),
            encoding="utf-8",
        )

    def show_api_key_window(self):
        window = tk.Toplevel(self.root)
        window.withdraw()

        window.geometry("440x270+80+100")
        window.configure(bg="#0B0E14")
        window.resizable(False, False)
        window.overrideredirect(True)
        window.attributes("-topmost", True)

        drag_x = 0
        drag_y = 0
        closed = False
        last_attempt = 0.0
        failed_attempts = 0
        locked_until = 0.0

        def close_window():
            nonlocal closed

            if closed:
                return

            closed = True

            try:
                window.grab_release()
            except tk.TclError:
                pass

            try:
                window.attributes("-topmost", False)
            except tk.TclError:
                pass

            try:
                window.destroy()
            except tk.TclError:
                pass

            self.close(force=True)

        window.protocol(
            "WM_DELETE_WINDOW",
            close_window,
        )

        def start_drag(event):
            nonlocal drag_x, drag_y

            drag_x = (
                event.x_root
                - window.winfo_x()
            )

            drag_y = (
                event.y_root
                - window.winfo_y()
            )

        def drag_window(event):
            if closed:
                return

            x = event.x_root - drag_x
            y = event.y_root - drag_y

            try:
                window.geometry(
                    f"440x270+{x}+{y}"
                )
            except tk.TclError:
                pass

        titlebar = tk.Frame(
            window,
            bg="#0D1713",
            height=44,
        )

        titlebar.pack(
            fill="x",
            side="top",
        )

        titlebar.pack_propagate(False)

        titlebar.bind(
            "<ButtonPress-1>",
            start_drag,
        )

        titlebar.bind(
            "<B1-Motion>",
            drag_window,
        )

        icon = tk.Label(
            titlebar,
            text="⌬",
            fg="#5CFF9D",
            bg="#0D1713",
            font=(
                "Segoe UI Symbol",
                15,
                "bold",
            ),
        )

        icon.pack(
            side="left",
            padx=(14, 7),
        )

        icon.bind(
            "<ButtonPress-1>",
            start_drag,
        )

        icon.bind(
            "<B1-Motion>",
            drag_window,
        )

        titlebar_label = tk.Label(
            titlebar,
            text="Zanel",
            fg="#F2F6FF",
            bg="#0D1713",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
        )

        titlebar_label.pack(
            side="left",
        )

        titlebar_label.bind(
            "<ButtonPress-1>",
            start_drag,
        )

        titlebar_label.bind(
            "<B1-Motion>",
            drag_window,
        )

        close_button = tk.Button(
            titlebar,
            text="×",
            command=close_window,
            fg="#B9C2D0",
            bg="#0D1713",
            activeforeground="white",
            activebackground="#C43F52",
            borderwidth=0,
            highlightthickness=0,
            font=(
                "Segoe UI",
                15,
            ),
            width=3,
            cursor="hand2",
        )

        close_button.pack(
            side="right",
            fill="y",
        )

        body = tk.Frame(
            window,
            bg="#0B0E14",
        )

        body.pack(
            fill="both",
            expand=True,
        )

        title_label = tk.Label(
            body,
            text="Enter API Key",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=(
                "Segoe UI",
                17,
                "bold",
            ),
        )

        title_label.pack(
            pady=(25, 5),
        )

        description = tk.Label(
            body,
            text="Enter your Zanel API key to continue.",
            fg="#8290A8",
            bg="#0B0E14",
            font=(
                "Segoe UI",
                9,
            ),
        )

        description.pack(
            pady=(0, 16),
        )

        entry_frame = tk.Frame(
            body,
            bg="#121A16",
        )

        entry_frame.pack(
            fill="x",
            padx=28,
        )

        entry = tk.Entry(
            entry_frame,
            show="•",
            bg="#121A16",
            fg="#E8F5ED",
            insertbackground="white",
            relief="flat",
            borderwidth=0,
            font=(
                "Segoe UI",
                10,
            ),
        )

        entry.pack(
            fill="x",
            padx=12,
            pady=10,
        )

        status = tk.Label(
            body,
            text="",
            fg="#8290A8",
            bg="#0B0E14",
            font=(
                "Segoe UI",
                9,
            ),
        )

        status.pack(
            pady=(10, 5),
        )

        checking = {"value": False}

        def finish_check(key, valid, message):
            nonlocal failed_attempts, locked_until

            checking["value"] = False

            if closed:
                return

            try:
                if not window.winfo_exists():
                    return

                button.configure(
                    state="normal",
                    text="Test & Save",
                    cursor="hand2",
                )
            except tk.TclError:
                return

            if valid:
                self.api_key = key

                try:
                    self.save_api_key(key)
                except Exception as exc:
                    status.configure(
                        text=f"Could not save API key: {exc}",
                        fg="#FF6B7A",
                    )
                    return

                status.configure(
                    text="API key verified and saved.",
                    fg="#5CFF9D",
                )

                self.invalid_key_active = False
                self.start_server_cleanup()

                def finish():
                    if closed:
                        return

                    try:
                        window.grab_release()
                    except tk.TclError:
                        pass

                    try:
                        window.destroy()
                    except tk.TclError:
                        pass

                    try:
                        self.set_mic(self.saved_mic_muted)
                    except Exception:
                        pass

                    try:
                        self.root.deiconify()
                    except tk.TclError:
                        pass

                window.after(700, finish)

            else:
                failed_attempts += 1

                if failed_attempts >= 5:
                    failed_attempts = 0
                    locked_until = time.time() + 60
                    message = "Too many failed attempts. Locked for 60s."

                status.configure(
                    text=message or "Invalid API key.",
                    fg="#FF6B7A",
                )

        def check_key():
            nonlocal last_attempt

            if closed or checking["value"]:
                return

            now = time.time()

            if now < locked_until:
                status.configure(
                    text=(
                        "Too many attempts. Try again in "
                        f"{int(locked_until - now) + 1}s."
                    ),
                    fg="#FF6B7A",
                )
                return

            if now - last_attempt < 3.0:
                status.configure(
                    text="Please wait a few seconds between attempts.",
                    fg="#FF6B7A",
                )
                return

            key = entry.get().strip()

            if not key:
                status.configure(
                    text="Please enter an API key.",
                    fg="#FF6B7A",
                )
                return

            last_attempt = now
            checking["value"] = True

            button.configure(
                state="disabled",
                text="Checking…",
                cursor="arrow",
            )

            status.configure(
                text="Checking API key...",
                fg="#8290A8",
            )

            def worker():
                try:
                    valid, message = self.test_api_key(key)
                except Exception as exc:
                    valid = False
                    message = str(exc)

                try:
                    window.after(
                        0,
                        lambda: finish_check(key, valid, message),
                    )
                except (tk.TclError, RuntimeError):
                    pass

            threading.Thread(
                target=worker,
                daemon=True,
            ).start()

        button = tk.Button(
            body,
            text="Test & Save",
            command=check_key,
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#32CD32",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
        )

        button.pack(
            pady=(2, 10),
        )

        entry.bind(
            "<Return>",
            lambda _event: check_key(),
        )

        entry.focus_set()

        self.recolor_tree(window, DEFAULT_THEME, self.theme)
        try:
            window.update_idletasks()
            window.deiconify()
            window.lift()
            window.grab_set()
            window.focus_force()
        except tk.TclError:
            close_window()
