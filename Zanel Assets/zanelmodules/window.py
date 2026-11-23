import time
import tkinter as tk
import math
import ctypes.wintypes
import re
import platform
import ctypes
from zanelmodules.config import (
    DEFAULT_THEME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    RAIL_WIDTH,
    SIDEBAR_TOGGLE_COOLDOWN,
    SIDEBAR_WIDTH,
)
from zanelmodules.resources import resource_path
from zanelmodules.storage import save_window_state
from zanelmodules.windows_ctl import MONITORINFO


class WindowMixin:

    def min_size(self):
        width = MIN_WINDOW_WIDTH + RAIL_WIDTH

        if self.sidebar_open:
            width += SIDEBAR_WIDTH

        return width, MIN_WINDOW_HEIGHT

    def virtual_screen(self):
        try:
            user32 = ctypes.windll.user32
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))

            if width > 0 and height > 0:
                return left, top, width, height
        except Exception:
            pass

        return (
            0,
            0,
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )

    def get_monitor_rects(self):
        try:
            user32 = ctypes.windll.user32

            user32.MonitorFromWindow.restype = ctypes.wintypes.HANDLE
            user32.MonitorFromWindow.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.wintypes.DWORD,
            ]
            user32.GetMonitorInfoW.restype = ctypes.wintypes.BOOL
            user32.GetMonitorInfoW.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.POINTER(MONITORINFO),
            ]
            user32.GetParent.restype = ctypes.wintypes.HWND
            user32.GetParent.argtypes = [ctypes.wintypes.HWND]

            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            monitor = user32.MonitorFromWindow(hwnd, 2)

            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)

            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = (
                    info.rcWork.left,
                    info.rcWork.top,
                    info.rcWork.right,
                    info.rcWork.bottom,
                )
                full = (
                    info.rcMonitor.left,
                    info.rcMonitor.top,
                    info.rcMonitor.right,
                    info.rcMonitor.bottom,
                )
                return work, full
        except Exception:
            pass

        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()

        return (0, 0, width, height), (0, 0, width, height)

    def fit_rect(self, width, height, x, y, min_w=None, min_h=None):
        left, top, screen_w, screen_h = self.virtual_screen()
        base_w, base_h = self.min_size()

        min_w = base_w if min_w is None else min_w
        min_h = base_h if min_h is None else min_h
        min_w = min(int(min_w), screen_w)
        min_h = min(int(min_h), screen_h)

        width = max(min_w, min(int(width), screen_w))
        height = max(min_h, min(int(height), screen_h))
        x = max(left, min(int(x), left + screen_w - width))
        y = max(top, min(int(y), top + screen_h - height))

        return width, height, x, y

    def apply_geometry(self, width, height, x, y):
        width, height, x, y = self.fit_rect(width, height, x, y)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        return width, height, x, y

    def current_rect(self):
        return (
            self.root.winfo_x(),
            self.root.winfo_y(),
            self.root.winfo_width(),
            self.root.winfo_height(),
        )

    def apply_saved_window(self):
        state = self.window_state
        x = state["x"]
        y = state["y"]

        if x is None or y is None:
            x, y = 40, 80

        self.set_sidebar(self.sidebar_open, adjust=False)

        width, height, x, y = self.apply_geometry(
            state["width"],
            state["height"],
            x,
            y,
        )

        self.normal_rect = (x, y, width, height)
        self.update_window_controls()

    def schedule_window_save(self):
        if self.geometry_job is not None:
            try:
                self.root.after_cancel(self.geometry_job)
            except tk.TclError:
                pass

        try:
            self.geometry_job = self.root.after(500, self.save_window_now)
        except tk.TclError:
            self.geometry_job = None

    def save_window_now(self):
        self.geometry_job = None
        rect = self.normal_rect

        if rect is None:
            return

        save_window_state(
            {
                "width": rect[2],
                "height": rect[3],
                "x": rect[0],
                "y": rect[1],
                "maximized": False,
                "sidebar_open": self.sidebar_open,
            }
        )

    def on_root_configure(self, event):
        if self.resizing:
            return
        if event.widget is not self.root or self.win_mode != "normal":
            return

        try:
            if self.root.state() != "normal":
                return

            rect = self.current_rect()
        except tk.TclError:
            return

        if rect[2] <= 1 or rect[3] <= 1:
            return

        self.normal_rect = rect
        self.schedule_window_save()

    def update_window_controls(self):
        try:
            for edge, handle in self.resize_handles.items():
                handle.place(**self.resize_specs[edge])
                handle.lift()
        except tk.TclError:
            pass

    def reset_window_size(self):
        try:
            self.win_mode = "normal"
            self.root.attributes("-topmost", bool(self.always_on_top))

            width = DEFAULT_WINDOW_WIDTH + (
                SIDEBAR_WIDTH if self.sidebar_open else 0
            )

            x = self.root.winfo_x()
            y = self.root.winfo_y()

            width, height, x, y = self.apply_geometry(
                width,
                DEFAULT_WINDOW_HEIGHT,
                x,
                y,
            )

            self.normal_rect = (x, y, width, height)
            self.update_window_controls()
            self.schedule_window_save()
            self.flash_state("Window size reset")
        except tk.TclError:
            pass

    def build_resize_handles(self):
        self.edge_cursors = {
            "n": "size_ns",
            "s": "size_ns",
            "w": "size_we",
            "e": "size_we",
            "nw": "size_nw_se",
            "se": "size_nw_se",
            "sw": "size_ne_sw",
        }

        self.root.bind_all("<Motion>", self.on_edge_motion, add="+")
        self.root.bind_all("<ButtonPress-1>", self.on_edge_press, add="+")
        self.root.bind_all("<B1-Motion>", self.on_edge_drag, add="+")
        self.root.bind_all("<ButtonRelease-1>", self.on_edge_release, add="+")

    def is_root_event(self, event):
        try:
            return event.widget.winfo_toplevel() is self.root
        except (AttributeError, KeyError, tk.TclError):
            return False

    def edge_at(self, x_root, y_root):
        try:
            x = x_root - self.root.winfo_rootx()
            y = y_root - self.root.winfo_rooty()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
        except tk.TclError:
            return None

        if x < 0 or y < 0 or x >= width or y >= height:
            return None

        edge_size = 5
        corner_size = 12

        if x < corner_size and y < corner_size:
            return "nw"

        if x < corner_size and y >= height - corner_size:
            return "sw"

        if x >= width - corner_size and y >= height - corner_size:
            return "se"

        if y < edge_size and 14 <= x < width - 14:
            return "n"

        if y >= height - edge_size and 14 <= x < width - 14:
            return "s"

        if x < edge_size and y >= 44:
            return "w"

        if x >= width - edge_size and y >= 44:
            return "e"

        return None

    def on_edge_motion(self, event):
        if self.resizing or self.win_mode != "normal":
            return

        if not self.is_root_event(event):
            return

        edge = self.edge_at(event.x_root, event.y_root)
        cursor = self.edge_cursors.get(edge, "") if edge else ""

        if cursor != self.edge_cursor:
            self.edge_cursor = cursor

            try:
                self.root.configure(cursor=cursor)
            except tk.TclError:
                pass

    def on_edge_press(self, event):
        if self.win_mode != "normal":
            return

        if not self.is_root_event(event):
            return

        edge = self.edge_at(event.x_root, event.y_root)

        if edge:
            self.start_resize(edge, event)

    def on_edge_drag(self, event):
        data = self.resize_data

        if data:
            self.do_resize(data["edge"], event)

    def on_edge_release(self, event):
        if self.resize_data:
            self.end_resize()

    def keep_handles_on_top(self):
        if not self.running:
            return

        try:
            for handle in self.resize_handles.values():
                handle.lift()

            self.root.after(1500, self.keep_handles_on_top)
        except tk.TclError:
            pass

    def start_resize(self, edge, event):
        if self.win_mode != "normal":
            return

        self.resizing = True

        self.resize_data = {
            "edge": edge,
            "x": event.x_root,
            "y": event.y_root,
            "left": self.root.winfo_x(),
            "top": self.root.winfo_y(),
            "width": self.root.winfo_width(),
            "height": self.root.winfo_height(),
            "target": None,
            "applied": None,
            "job": None,
        }

    def do_resize(self, edge, event):
        data = self.resize_data

        if not data or self.win_mode != "normal":
            return

        dx = event.x_root - data["x"]
        dy = event.y_root - data["y"]
        min_w, min_h = self.min_size()
        view_left, view_top, view_w, view_h = self.virtual_screen()

        left = data["left"]
        top = data["top"]
        width = data["width"]
        height = data["height"]
        right = left + width
        bottom = top + height

        if "e" in edge:
            width = max(min_w, min(data["width"] + dx, view_left + view_w - left))

        if "s" in edge:
            height = max(min_h, min(data["height"] + dy, view_top + view_h - top))

        if "w" in edge:
            width = max(min_w, min(data["width"] - dx, right - view_left))
            left = right - width

        if "n" in edge:
            height = max(min_h, min(data["height"] - dy, bottom - view_top))
            top = bottom - height

        data["target"] = (width, height, left, top)

        if data["job"] is None:
            try:
                data["job"] = self.root.after(16, self.apply_resize)
            except tk.TclError:
                data["job"] = None

    def apply_resize(self):
        data = self.resize_data

        if not data:
            return

        data["job"] = None
        target = data.get("target")

        if not target or target == data.get("applied"):
            return

        try:
            self.root.geometry(
                f"{target[0]}x{target[1]}+{target[2]}+{target[3]}"
            )
            self.root.update_idletasks()
            data["applied"] = target
        except tk.TclError:
            pass

    def end_resize(self):
        data = self.resize_data

        if data and data.get("job") is not None:
            try:
                self.root.after_cancel(data["job"])
            except tk.TclError:
                pass

            data["job"] = None

        self.apply_resize()
        self.resize_data = None
        self.resizing = False

        try:
            rect = self.current_rect()

            if rect[2] > 1 and rect[3] > 1:
                self.normal_rect = rect
        except tk.TclError:
            pass

        self.schedule_window_save()

    def start_drag(self, event):
        if self.win_mode != "normal":
            return

        self.drag_x = event.x_root - self.root.winfo_x()
        self.drag_y = event.y_root - self.root.winfo_y()

    def drag_window(self, event):
        if not self.running or self.win_mode != "normal" or self.resizing:
            return

        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            _, _, x, y = self.fit_rect(
                width,
                height,
                event.x_root - self.drag_x,
                event.y_root - self.drag_y,
                1,
                1,
            )

            self.root.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def create_taskbar_icon(self):
        existing = self.taskbar_window

        if existing is not None:
            try:
                if existing.winfo_exists():
                    return
            except tk.TclError:
                pass

            self.taskbar_window = None

        if not self.running or self.taskbar_suspended:
            return

        self.taskbar_ready = False
        self.taskbar_busy = False

        try:
            proxy = tk.Toplevel(self.root)
            proxy.zanel_skip = True
            proxy.withdraw()
            proxy.title("Zanel")
            proxy.configure(bg="#0B0E14")
            proxy.geometry("1x1+-32000+-32000")

            try:
                proxy.iconbitmap(resource_path("zanelicon.ico"))
            except Exception:
                pass

            proxy.protocol("WM_DELETE_WINDOW", self.close)
            proxy.bind("<Map>", self.on_taskbar_activate)
            proxy.update_idletasks()
            proxy.iconify()

            self.taskbar_window = proxy

            self.root.after(
                600,
                lambda: setattr(self, "taskbar_ready", True),
            )
        except tk.TclError:
            self.taskbar_window = None

    def suspend_taskbar_icon(self):
        self.taskbar_suspended = True

        proxy = self.taskbar_window
        self.taskbar_window = None
        self.taskbar_ready = False
        self.taskbar_busy = False

        if proxy is not None:
            try:
                proxy.destroy()
            except tk.TclError:
                pass

    def resume_taskbar_icon(self):
        if not self.running:
            return

        self.taskbar_suspended = False
        self.create_taskbar_icon()

    def watch_taskbar_icon(self):
        if not self.running:
            return

        try:
            self.create_taskbar_icon()
            self.root.after(5000, self.watch_taskbar_icon)
        except (tk.TclError, RuntimeError):
            pass

    def on_taskbar_activate(self, event):
        proxy = self.taskbar_window

        if proxy is None or event.widget is not proxy:
            return

        if (
            not self.taskbar_ready
            or self.taskbar_busy
            or not self.running
        ):
            return

        self.taskbar_busy = True

        try:
            proxy.iconify()
        except tk.TclError:
            pass

        try:
            self.root.after(60, self.finish_taskbar_activate)
        except (tk.TclError, RuntimeError):
            self.taskbar_busy = False

    def finish_taskbar_activate(self):
        try:
            self.bring_to_front()
        except Exception:
            pass

        try:
            self.root.after(250, self.release_taskbar_busy)
        except (tk.TclError, RuntimeError):
            self.taskbar_busy = False

    def release_taskbar_busy(self):
        self.taskbar_busy = False

    def release_topmost(self):
        if not self.running:
            return

        try:
            self.root.attributes("-topmost", bool(self.always_on_top))
        except tk.TclError:
            pass

    def bring_to_front(self):
        if not self.running:
            return

        proxy = self.taskbar_window
        compact = self.compact_window
        compact_alive = False

        if compact is not None:
            try:
                compact_alive = bool(compact.winfo_exists())
            except tk.TclError:
                compact_alive = False

        try:
            root_state = self.root.state()
        except tk.TclError:
            return

        if compact_alive:
            try:
                if compact.state() == "iconic":
                    compact.deiconify()
                else:
                    compact.attributes("-topmost", True)
                    compact.lift()
            except tk.TclError:
                pass
        elif root_state != "withdrawn":
            try:
                if root_state == "iconic":
                    self.root.deiconify()

                if self.win_mode == "normal" and not self.resizing:
                    x, y, width, height = self.current_rect()

                    if width > 1 and height > 1:
                        self.apply_geometry(width, height, x, y)

                self.root.attributes("-topmost", True)
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                pass

            if not self.always_on_top:
                try:
                    self.root.after(400, self.release_topmost)
                except (tk.TclError, RuntimeError):
                    pass

        focus_child = root_state == "withdrawn" and not compact_alive

        try:
            children = list(self.root.winfo_children())
        except tk.TclError:
            return

        for child in children:
            if child is proxy or not isinstance(child, tk.Toplevel):
                continue

            try:
                if not child.winfo_viewable():
                    continue

                child.attributes("-topmost", True)
                child.lift()

                if focus_child:
                    child.focus_force()
            except tk.TclError:
                continue

    def toggle_sidebar(self):
        now = time.monotonic()
        if (
            self.sidebar_job is not None
            or now < self.sidebar_toggle_cooldown_until
        ):
            return

        self.sidebar_toggle_cooldown_until = (
            now + SIDEBAR_TOGGLE_COOLDOWN
        )

        try:
            self.sidebar_toggle.configure(state="disabled")
            self.sidebar_toggle_cooldown_job = self.root.after(
                int(SIDEBAR_TOGGLE_COOLDOWN * 1000),
                self.finish_sidebar_toggle_cooldown,
            )
        except (tk.TclError, RuntimeError):
            self.sidebar_toggle_cooldown_until = 0.0
            try:
                self.sidebar_toggle.configure(state="normal")
            except tk.TclError:
                pass
            self.flash_state("Could not start the sidebar cooldown.")
            return

        self.set_sidebar(not self.sidebar_open)

    def finish_sidebar_toggle_cooldown(self):
        self.sidebar_toggle_cooldown_job = None

        try:
            if self.running and self.sidebar_toggle.winfo_exists():
                self.sidebar_toggle.configure(state="normal")
        except (tk.TclError, RuntimeError):
            pass

    def set_sidebar(self, open_, adjust=True):
        open_ = bool(open_)
        changed = open_ != self.sidebar_open
        self.sidebar_open = open_

        try:
            self.sidebar_toggle.configure(text="‹" if open_ else "›")
        except tk.TclError:
            return

        if self.sidebar_job is not None:
            try:
                self.root.after_cancel(self.sidebar_job)
            except tk.TclError:
                pass

            self.sidebar_job = None

        if not adjust or not changed or self.win_mode != "normal":
            self.finish_sidebar(open_)

            if changed:
                self.schedule_window_save()

            return

        self.animate_sidebar(open_)

    def finish_sidebar(self, open_):
        self.sidebar_px = SIDEBAR_WIDTH if open_ else 0

        try:
            if open_:
                self.sidebar.configure(width=SIDEBAR_WIDTH)

                if not self.sidebar.winfo_manager():
                    self.sidebar.pack(side="left", fill="y", after=self.rail)
            else:
                self.sidebar.pack_forget()
        except tk.TclError:
            pass

    def animate_sidebar(self, open_):
        start_px = self.sidebar_px
        end_px = SIDEBAR_WIDTH if open_ else 0

        if start_px == end_px:
            self.finish_sidebar(open_)
            return

        try:
            self.root.update_idletasks()
            base_width = self.root.winfo_width() - start_px
            height = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            if not self.sidebar.winfo_manager():
                self.sidebar.configure(width=max(1, start_px))
                self.sidebar.pack(side="left", fill="y", after=self.rail)

            target_rect = self.fit_rect(
                base_width + end_px,
                height,
                x,
                y,
                MIN_WINDOW_WIDTH + RAIL_WIDTH,
                MIN_WINDOW_HEIGHT,
            )

            if open_:
                width, new_height, new_x, new_y = target_rect
                self.root.geometry(
                    f"{width}x{new_height}+{new_x}+{new_y}"
                )
        except tk.TclError:
            self.finish_sidebar(open_)
            return

        started = time.monotonic()
        duration = 0.22

        def step():
            self.sidebar_job = None

            if not self.running:
                return

            progress = min(1.0, (time.monotonic() - started) / duration)
            eased = 1 - (1 - progress) ** 3
            px = int(round(start_px + (end_px - start_px) * eased))

            try:
                self.sidebar_px = px

                if px > 0:
                    self.sidebar.configure(width=px)
            except tk.TclError:
                return

            if progress >= 1.0:
                self.finish_sidebar(open_)

                if not open_:
                    try:
                        width, new_height, new_x, new_y = target_rect
                        self.root.geometry(
                            f"{width}x{new_height}+{new_x}+{new_y}"
                        )
                    except tk.TclError:
                        pass

                self.schedule_window_save()
                return

            try:
                self.sidebar_job = self.root.after(12, step)
            except tk.TclError:
                self.sidebar_job = None

        step()

    def on_global_wheel(self, event):
        try:
            target = self.root.winfo_containing(event.x_root, event.y_root)

            if target is None:
                return

            path = str(target)
            chat_path = str(self.chat)

            if path == chat_path or path.startswith(chat_path + "."):
                return self.on_chat_mousewheel(event)

            if not self.sidebar_open:
                return

            canvas_path = str(self.chat_canvas)

            if path != canvas_path and not path.startswith(canvas_path + "."):
                return

            if self.chat_list.winfo_reqheight() <= self.chat_canvas.winfo_height():
                return

            self.chat_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        except (tk.TclError, KeyError):
            pass

    def apply_window_settings(self, opacity=None, topmost=None):
        if opacity is None:
            opacity = self.opacity

        if topmost is None:
            topmost = self.always_on_top

        try:
            self.root.attributes("-alpha", float(opacity))
        except (tk.TclError, ValueError, TypeError):
            pass

        try:
            self.root.attributes("-topmost", bool(topmost))
        except tk.TclError:
            pass

    def on_root_map(self, event=None):
        if event is not None and event.widget is not self.root:
            return

        if (
            self.compact_window is None
            and self.normal_geometry is None
        ):
            return

        self.restore_window()

    def sync_window_background(self):
        if platform.system() != "Windows":
            return

        color = self.theme["bg"]

        if color == self._bg_brush_color:
            return

        try:
            self.root.update_idletasks()

            red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            colorref = red | (green << 8) | (blue << 16)

            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32

            gdi32.CreateSolidBrush.restype = ctypes.c_void_p
            gdi32.CreateSolidBrush.argtypes = [ctypes.c_uint]
            gdi32.DeleteObject.argtypes = [ctypes.c_void_p]

            set_class = getattr(user32, "SetClassLongPtrW", None) or user32.SetClassLongW
            set_class.restype = ctypes.c_void_p
            set_class.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

            user32.GetParent.restype = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]

            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()

            brush = gdi32.CreateSolidBrush(colorref)
            set_class(hwnd, -10, brush)

            if self._bg_brush:
                gdi32.DeleteObject(self._bg_brush)

            self._bg_brush = brush
            self._bg_brush_color = color
        except Exception:
            pass

    def minimize_window(self):
        if getattr(self, "closed", False):
            return

        if getattr(self, "minimize_transition", False):
            return

        self.minimize_transition = True

        try:
            if getattr(self, "compact_window", None):
                try:
                    if self.compact_window.winfo_exists():
                        self.minimize_transition = False
                        return
                except tk.TclError:
                    self.compact_window = None

            try:
                self.normal_geometry = self.root.geometry()
            except tk.TclError:
                self.normal_geometry = "1000x700+100+100"

            try:
                self.root.withdraw()
            except tk.TclError:
                self.minimize_transition = False
                return

            self.create_compact_window()

        finally:
            self.minimize_transition = False

    def create_compact_window(self):
        if getattr(self, "closed", False):
            return

        existing = getattr(
            self,
            "compact_window",
            None
        )

        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    return
            except tk.TclError:
                self.compact_window = None

        self.compact_width = 250
        self.compact_height = 205
        self.compact_radius = 28
        self.compact_dragging = False
        self.compact_drag_x = 0
        self.compact_drag_y = 0

        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
        except tk.TclError:
            x = 100
            y = 100

        try:
            self.compact_window = tk.Toplevel(
                self.root
            )
        except tk.TclError:
            self.compact_window = None
            return

        window = self.compact_window

        window.overrideredirect(
            True
        )

        window.configure(
            bg="#071019"
        )

        try:
            window.attributes(
                "-topmost",
                True
            )

            window.attributes(
                "-transparentcolor",
                "#071019"
            )
        except tk.TclError:
            pass

        window.geometry(
            f"{self.compact_width}x{self.compact_height}+{x}+{y}"
        )

        window.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )

        canvas = tk.Canvas(
            window,
            width=self.compact_width,
            height=self.compact_height,
            bg="#071019",
            bd=0,
            highlightthickness=0,
            relief="flat"
        )

        canvas.pack(
            fill="both",
            expand=True
        )

        self.compact_canvas = canvas

        w = self.compact_width
        h = self.compact_height
        r = self.compact_radius

        def rounded_points(x1, y1, x2, y2, radius):
            points = []

            corners = (
                (x2 - radius, y1 + radius, 270),
                (x2 - radius, y2 - radius, 0),
                (x1 + radius, y2 - radius, 90),
                (x1 + radius, y1 + radius, 180),
            )

            for corner_x, corner_y, start in corners:
                for step in range(0, 91, 6):
                    angle = math.radians(start + step)

                    points.extend(
                        (
                            corner_x + math.cos(angle) * radius,
                            corner_y + math.sin(angle) * radius,
                        )
                    )

            return points

        canvas.create_polygon(
            *rounded_points(0, 0, w - 1, h - 1, r),
            fill=self.theme["border"],
            outline="",
            tags=("compact_border",),
        )

        canvas.create_polygon(
            *rounded_points(2, 2, w - 3, h - 3, r - 2),
            fill="#0D1713",
            outline=""
        )

        canvas.create_text(
            w // 2,
            66,
            text="⌬",
            fill=self.theme["accent"],
            font=(
                "Segoe UI Symbol",
                38,
                "bold"
            ),
            tags=("compact_accent",),
        )

        canvas.create_text(
            w // 2,
            116,
            text="Zanel Assistant",
            fill="#F2F6FF",
            font=(
                "Segoe UI",
                11,
                "bold"
            )
        )

        canvas.create_text(
            w // 2,
            137,
            text="Minimised",
            fill="#8290A8",
            font=(
                "Segoe UI",
                8
            )
        )

        canvas.create_text(
            w // 2,
            160,
            text="Double-click to restore",
            fill="#56677A",
            font=(
                "Segoe UI",
                8
            )
        )

        button_x = w - 38
        button_y = 32

        hover_circle = canvas.create_oval(
            button_x - 14,
            button_y - 14,
            button_x + 14,
            button_y + 14,
            fill="#0D1713",
            outline="",
            tags=("minbtn",)
        )

        button_text = canvas.create_text(
            button_x,
            button_y,
            text="—",
            fill="#A9B8B0",
            font=(
                "Segoe UI",
                12
            ),
            tags=("minbtn",)
        )

        pressed = {"button": False}

        def button_enter(_event=None):
            try:
                canvas.itemconfigure(
                    hover_circle,
                    fill="#ffa500"
                )

                canvas.itemconfigure(
                    button_text,
                    fill="#071019"
                )

                canvas.configure(
                    cursor="hand2"
                )
            except tk.TclError:
                pass

        def button_leave(_event=None):
            try:
                canvas.itemconfigure(
                    hover_circle,
                    fill=self.theme["title"]
                )

                canvas.itemconfigure(
                    button_text,
                    fill="#A9B8B0"
                )

                canvas.configure(
                    cursor=""
                )
            except tk.TclError:
                pass

        def on_press(event):
            if "minbtn" in canvas.gettags("current"):
                pressed["button"] = True
                self.compact_dragging = False
                return

            pressed["button"] = False
            self.compact_start_drag(event)

        def on_release(event):
            was_button = pressed["button"]
            pressed["button"] = False

            if was_button and "minbtn" in canvas.gettags("current"):
                button_leave()
                self.minimize_compact_window()
                return

            self.compact_stop_drag(event)

        def on_double_click(event):
            if "minbtn" in canvas.gettags("current"):
                return

            self.restore_window()

        canvas.tag_bind(
            "minbtn",
            "<Enter>",
            button_enter
        )

        canvas.tag_bind(
            "minbtn",
            "<Leave>",
            button_leave
        )

        canvas.bind(
            "<ButtonPress-1>",
            on_press
        )

        canvas.bind(
            "<B1-Motion>",
            self.compact_drag_window
        )

        canvas.bind(
            "<ButtonRelease-1>",
            on_release
        )

        canvas.bind(
            "<Double-Button-1>",
            on_double_click
        )

        window.bind(
            "<Map>",
            self.restore_compact_window,
            add="+"
        )

        window.update_idletasks()
        window.deiconify()
        window.lift()

        self.recolor_tree(window, DEFAULT_THEME, self.theme)

    def compact_start_drag(self, event):
        if getattr(self, "closed", False):
            return

        if not getattr(
            self,
            "compact_window",
            None
        ):
            return

        try:
            if not self.compact_window.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            self.compact_drag_x = (
                event.x_root
                - self.compact_window.winfo_x()
            )

            self.compact_drag_y = (
                event.y_root
                - self.compact_window.winfo_y()
            )

            self.compact_dragging = True
        except tk.TclError:
            self.compact_dragging = False

    def compact_drag_window(self, event):
        if getattr(self, "closed", False):
            return

        if not getattr(
            self,
            "compact_window",
            None
        ):
            return

        if not self.compact_dragging:
            return

        try:
            x = (
                event.x_root
                - self.compact_drag_x
            )

            y = (
                event.y_root
                - self.compact_drag_y
            )

            screen_width = self.compact_window.winfo_screenwidth()
            screen_height = self.compact_window.winfo_screenheight()

            x = max(
                0,
                min(
                    x,
                    screen_width - self.compact_width
                )
            )

            y = max(
                0,
                min(
                    y,
                    screen_height - self.compact_height
                )
            )

            self.compact_window.geometry(
                f"{self.compact_width}x{self.compact_height}+{x}+{y}"
            )

        except tk.TclError:
            pass

    def compact_stop_drag(self, _event=None):
        self.compact_dragging = False

    def minimize_compact_window(self):
        if getattr(self, "closed", False):
            return

        compact = getattr(
            self,
            "compact_window",
            None
        )

        if not compact:
            return

        try:
            if not compact.winfo_exists():
                self.compact_window = None
                return
        except tk.TclError:
            self.compact_window = None
            return

        try:
            self.compact_saved_geometry = compact.geometry()

            compact.overrideredirect(
                False
            )

            compact.attributes(
                "-topmost",
                False
            )

            compact.iconify()

            compact.unbind(
                "<Map>"
            )

            compact.bind(
                "<Map>",
                self.restore_compact_window,
                add="+"
            )

            self.suspend_taskbar_icon()

        except tk.TclError:
            pass

    def restore_compact_window(self, _event=None):
        compact = getattr(
            self,
            "compact_window",
            None
        )

        if not compact:
            return

        try:
            if not compact.winfo_exists():
                self.compact_window = None
                return

            state = compact.state()

            if state != "normal":
                return

            self.root.after(150, self.resume_taskbar_icon)

            compact.unbind(
                "<Map>"
            )

            compact.overrideredirect(
                True
            )

            compact.attributes(
                "-topmost",
                True
            )

            if getattr(
                self,
                "compact_saved_geometry",
                None
            ):
                compact.geometry(
                    self.compact_saved_geometry
                )

            compact.deiconify()
            compact.lift()
            compact.focus_force()

        except tk.TclError:
            pass

    def restore_window(self, _event=None):
        if getattr(self, "closed", False):
            return

        if getattr(
            self,
            "restore_transition",
            False
        ):
            return

        self.restore_transition = True

        try:
            compact = getattr(
                self,
                "compact_window",
                None
            )

            if compact:
                try:
                    if compact.winfo_exists():
                        compact_x = compact.winfo_x()
                        compact_y = compact.winfo_y()

                        normal_geometry = self.normal_geometry or self.root.geometry()
                        normal_size = re.match(
                            r"(\d+x\d+)",
                            normal_geometry
                        )

                        if normal_size:
                            self.normal_geometry = (
                                f"{normal_size.group(1)}+{compact_x}+{compact_y}"
                            )

                        compact.destroy()
                except tk.TclError:
                    pass

                self.compact_window = None

            try:
                self.root.overrideredirect(
                    True
                )
            except tk.TclError:
                pass

            try:
                if getattr(
                    self,
                    "normal_geometry",
                    None
                ):
                    self.root.geometry(
                        self.normal_geometry
                    )
            except tk.TclError:
                pass

            self.normal_geometry = None

            try:
                self.root.deiconify()
            except tk.TclError:
                return

            try:
                self.root.attributes(
                    "-topmost",
                    bool(self.always_on_top)
                )
            except tk.TclError:
                pass

            try:
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                pass

        finally:
            self.restore_transition = False

            try:
                self.root.after(150, self.resume_taskbar_icon)
            except (tk.TclError, RuntimeError):
                pass

    def close_application(self):
        self.close()
