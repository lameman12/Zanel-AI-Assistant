import tkinter as tk
from zanelmodules.theme import blend_color


class ThemedScrollbar(tk.Canvas):
    def __init__(
        self,
        parent,
        orient="vertical",
        command=None,
        bg="#0B0E14",
        track="#24332B",
        thumb="#5CFF9D",
        width=8,
    ):
        super().__init__(
            parent,
            width=width if orient == "vertical" else None,
            height=None if orient == "vertical" else width,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )

        self.orient = orient
        self.command = command
        self.bg_color = bg
        self.track_color = track
        self.thumb_color = thumb
        self.first = 0.0
        self.last = 1.0
        self.dragging = False
        self.drag_start = 0
        self.drag_first = 0.0
        self.thumb_box = None
        self.visual_first = 0.0
        self.visual_last = 1.0
        self.animation_job = None
        self.hovered = False
        self.pressed = False

        self.configure(cursor="hand2")
        self.bind("<Configure>", self.draw)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_motion)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<MouseWheel>", self.on_mousewheel)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Destroy>", self.on_destroy)

    def configure(self, cnf=None, **kwargs):
        command = kwargs.pop("command", None)
        if command is not None:
            self.command = command
        try:
            if cnf is not None:
                return super().configure(cnf, **kwargs)
            if kwargs:
                return super().configure(**kwargs)
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        return None

    def set(self, first, last):
        try:
            target_first = max(0.0, min(1.0, float(first)))
            target_last = max(target_first, min(1.0, float(last)))
        except (TypeError, ValueError, OverflowError):
            return

        if abs(target_first - self.first) < 0.0001 and abs(target_last - self.last) < 0.0001:
            return

        self.first = target_first
        self.last = target_last
        self.start_animation()

    def start_animation(self):
        if self.animation_job is not None:
            return

        try:
            self.animation_job = self.after(16, self.animate)
        except (tk.TclError, RuntimeError):
            self.animation_job = None

    def animate(self):
        self.animation_job = None

        try:
            if not self.winfo_exists():
                return

            first_difference = self.first - self.visual_first
            last_difference = self.last - self.visual_last
            self.visual_first += first_difference * 0.38
            self.visual_last += last_difference * 0.38

            if abs(first_difference) < 0.0005:
                self.visual_first = self.first
            if abs(last_difference) < 0.0005:
                self.visual_last = self.last

            self.draw()

            if (
                abs(self.first - self.visual_first) > 0.0005
                or abs(self.last - self.visual_last) > 0.0005
            ):
                self.start_animation()
        except (tk.TclError, RuntimeError):
            pass

    def draw(self, _event=None):
        try:
            self.delete("all")
            width = max(1, int(self.winfo_width()))
            height = max(1, int(self.winfo_height()))

            viewport = max(0.01, min(1.0, self.visual_last - self.visual_first))

            if self.orient == "vertical":
                track_width = max(2, width - 4)
                track_left = (width - track_width) / 2
                self.create_rectangle(
                    track_left,
                    2,
                    track_left + track_width,
                    height - 2,
                    fill=self.track_color,
                    outline="",
                )

                thumb_height = max(28, int(viewport * height))
                thumb_height = min(height - 4, thumb_height)
                travel = max(0, height - thumb_height)
                thumb_top = int(
                    (self.visual_first / max(1.0 - viewport, 0.01))
                    * travel
                )
                thumb_top = max(0, min(travel, thumb_top))
                thumb_bottom = thumb_top + thumb_height
                thumb_left = 1
                thumb_right = width - 1
                thumb_color = self.thumb_color

                if self.hovered or self.pressed:
                    thumb_color = blend_color(
                        self.thumb_color,
                        "#FFFFFF",
                        0.28 if self.hovered else 0.16,
                    )

                if thumb_height < height - 2:
                    self.create_oval(
                        thumb_left,
                        thumb_top,
                        thumb_right,
                        thumb_top + max(4, thumb_right - thumb_left),
                        fill=thumb_color,
                        outline="",
                    )
                    self.create_rectangle(
                        thumb_left,
                        thumb_top + (thumb_right - thumb_left) // 2,
                        thumb_right,
                        thumb_bottom - (thumb_right - thumb_left) // 2,
                        fill=thumb_color,
                        outline="",
                    )
                    self.create_oval(
                        thumb_left,
                        thumb_bottom - max(4, thumb_right - thumb_left),
                        thumb_right,
                        thumb_bottom,
                        fill=thumb_color,
                        outline="",
                    )
                self.thumb_box = (thumb_top, thumb_bottom)
            else:
                inset = max(1, height // 4)
                self.create_rectangle(
                    0,
                    inset,
                    width,
                    height - inset,
                    fill=self.track_color,
                    outline="",
                )
                thumb_width = max(28, int(viewport * width))
                thumb_width = min(width - 4, thumb_width)
                travel = max(0, width - thumb_width)
                thumb_left = int(
                    (self.visual_first / max(1.0 - viewport, 0.01))
                    * travel
                )
                thumb_left = max(0, min(travel, thumb_left))
                thumb_right = thumb_left + thumb_width
                thumb_color = self.thumb_color

                if self.hovered or self.pressed:
                    thumb_color = blend_color(
                        self.thumb_color,
                        "#FFFFFF",
                        0.28 if self.hovered else 0.16,
                    )

                if thumb_width < width - 2:
                    radius = max(3, min(6, height // 3))
                    self.create_oval(
                        thumb_left,
                        1,
                        thumb_left + radius * 2,
                        height - 1,
                        fill=thumb_color,
                        outline="",
                    )
                    self.create_rectangle(
                        thumb_left + radius,
                        1,
                        thumb_right - radius,
                        height - 1,
                        fill=thumb_color,
                        outline="",
                    )
                    self.create_oval(
                        thumb_right - radius * 2,
                        1,
                        thumb_right,
                        height - 1,
                        fill=thumb_color,
                        outline="",
                    )
                self.thumb_box = (thumb_left, thumb_right)
        except tk.TclError:
            pass

    def on_press(self, event):
        if self.command is None:
            return

        position = event.y if self.orient == "vertical" else event.x
        self.dragging = True
        self.pressed = True
        self.drag_start = event.y if self.orient == "vertical" else event.x
        self.drag_first = self.first
        self.draw()

        if self.thumb_box is not None:
            thumb_start, thumb_end = self.thumb_box
            if thumb_start <= position <= thumb_end:
                return

        if self.orient == "vertical":
            size = max(1, self.winfo_height())
        else:
            size = max(1, self.winfo_width())

        viewport = max(0.01, min(1.0, self.last - self.first))
        thumb_size = min(
            size - 4,
            max(28, int(viewport * size)),
        )
        travel = max(1.0, size - thumb_size)
        target = max(
            0.0,
            min(
                1.0 - viewport,
                (position - thumb_size * 0.5) / travel,
            ),
        )
        self.run_command("moveto", str(target))

    def on_motion(self, event):
        if not self.dragging or self.command is None:
            return

        position = event.y if self.orient == "vertical" else event.x
        size = (
            max(1, self.winfo_height())
            if self.orient == "vertical"
            else max(1, self.winfo_width())
        )
        viewport = max(0.01, min(1.0, self.last - self.first))
        thumb_size = min(
            size - 4,
            max(28, int(viewport * size)),
        )
        travel = max(1.0, size - thumb_size)
        target = self.drag_first + (position - self.drag_start) / travel
        target = max(0.0, min(1.0 - viewport, target))
        self.run_command("moveto", str(target))

    def on_release(self, _event=None):
        self.dragging = False
        self.pressed = False
        self.draw()

    def on_mousewheel(self, event):
        if self.command is None:
            return "break"

        amount = -1 if event.delta > 0 else 1
        self.run_command("scroll", amount, "units")
        return "break"

    def run_command(self, *args):
        if not callable(self.command):
            return False
        try:
            self.command(*args)
            return True
        except (tk.TclError, RuntimeError, ValueError, TypeError):
            return False

    def on_enter(self, _event=None):
        self.hovered = True
        self.draw()

    def on_leave(self, _event=None):
        if not self.dragging:
            self.hovered = False
            self.draw()

    def on_destroy(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self.animation_job is not None:
            try:
                self.after_cancel(self.animation_job)
            except tk.TclError:
                pass
            self.animation_job = None


class ModernSlider(tk.Canvas):
    def __init__(
        self,
        parent,
        variable,
        from_,
        to,
        height=24,
        bg="#0B0E14",
        track="#24332B",
        fill="#5CFF9D",
        handle="#5CFF9D",
        handle_active="#D8FFE9",
        glow="#2F8F63",
    ):
        super().__init__(
            parent,
            height=height,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )

        self.variable = variable
        self.from_ = from_
        self.to = to
        self.bg_color = bg
        self.track_color = track
        self.fill_color = fill
        self.handle_color = handle
        self.handle_active_color = handle_active
        self.glow_color = glow

        self.pad = 18
        self.pos = None
        self.radius = 8.0
        self.glow_level = 0.0
        self.hover = False
        self.dragging = False
        self.job = None
        self.trace_id = None

        try:
            self.trace_id = self.variable.trace_add(
                "write",
                self.on_variable,
            )
        except tk.TclError:
            self.trace_id = None

        self.bind("<Configure>", self.on_configure)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_motion)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Destroy>", self.on_destroy)

    def current_value(self):
        try:
            value = float(self.variable.get())
        except (tk.TclError, ValueError, TypeError):
            value = float(self.from_)

        return max(
            float(self.from_),
            min(float(self.to), value),
        )

    def usable_width(self):
        return max(
            1.0,
            float(self.winfo_width()) - self.pad * 2,
        )

    def target_x(self):
        span = max(
            1.0,
            float(self.to) - float(self.from_),
        )

        ratio = (
            self.current_value()
            - float(self.from_)
        ) / span

        return self.pad + ratio * self.usable_width()

    def x_to_value(self, x):
        span = float(self.to) - float(self.from_)

        ratio = (
            float(x) - self.pad
        ) / self.usable_width()

        ratio = max(0.0, min(1.0, ratio))

        return int(
            round(float(self.from_) + ratio * span)
        )

    def on_configure(self, _event=None):
        self.pos = self.target_x()
        self.draw()

    def on_variable(self, *_args):
        self.start_animation()

    def on_enter(self, _event=None):
        self.hover = True
        self.start_animation()

    def on_leave(self, _event=None):
        self.hover = False
        self.start_animation()

    def on_press(self, event):
        self.dragging = True
        self.set_from_x(event.x)
        self.start_animation()

    def on_motion(self, event):
        if not self.dragging:
            return

        self.set_from_x(event.x)

    def on_release(self, _event=None):
        self.dragging = False
        self.start_animation()

    def set_from_x(self, x):
        value = self.x_to_value(x)

        try:
            if int(self.variable.get()) != value:
                self.variable.set(value)
            else:
                self.start_animation()
        except (tk.TclError, ValueError):
            pass

    def on_destroy(self, event=None):
        if event is not None and event.widget is not self:
            return

        if self.job is not None:
            try:
                self.after_cancel(self.job)
            except tk.TclError:
                pass

            self.job = None

        if self.trace_id is not None:
            try:
                self.variable.trace_remove(
                    "write",
                    self.trace_id,
                )
            except (tk.TclError, ValueError):
                pass

            self.trace_id = None

    def start_animation(self):
        if self.job is not None:
            return

        try:
            self.job = self.after(
                16,
                self.step,
            )
        except tk.TclError:
            self.job = None

    def step(self):
        self.job = None

        try:
            if not self.winfo_exists():
                return

            target = self.target_x()

            if self.pos is None:
                self.pos = target

            position_ease = 0.5 if self.dragging else 0.22

            self.pos += (target - self.pos) * position_ease

            if self.dragging:
                target_radius = 12.0
                target_glow = 1.0
            elif self.hover:
                target_radius = 10.0
                target_glow = 0.55
            else:
                target_radius = 8.0
                target_glow = 0.0

            self.radius += (target_radius - self.radius) * 0.25
            self.glow_level += (target_glow - self.glow_level) * 0.2

            settled = (
                abs(target - self.pos) < 0.3
                and abs(target_radius - self.radius) < 0.05
                and abs(target_glow - self.glow_level) < 0.01
            )

            if settled:
                self.pos = target
                self.radius = target_radius
                self.glow_level = target_glow
                self.draw()
                return

            self.draw()

            self.job = self.after(
                16,
                self.step,
            )

        except tk.TclError:
            self.job = None

    def draw(self):
        try:
            self.delete("all")

            width = float(self.winfo_width())
            height = float(self.winfo_height())

            if width <= self.pad * 2 or height <= 1:
                return

            if self.pos is None:
                self.pos = self.target_x()

            center_y = height / 2

            self.create_line(
                self.pad,
                center_y,
                width - self.pad,
                center_y,
                fill=self.track_color,
                width=6,
                capstyle=tk.ROUND,
            )

            if self.pos - self.pad > 0.5:
                self.create_line(
                    self.pad,
                    center_y,
                    self.pos,
                    center_y,
                    fill=self.fill_color,
                    width=6,
                    capstyle=tk.ROUND,
                )

            glow_radius = (
                self.radius
                + 3
                + 7 * self.glow_level
            )

            self.create_oval(
                self.pos - glow_radius,
                center_y - glow_radius,
                self.pos + glow_radius,
                center_y + glow_radius,
                fill=blend_color(
                    self.bg_color,
                    self.glow_color,
                    0.25 + 0.75 * self.glow_level,
                ),
                outline="",
            )

            self.create_oval(
                self.pos - self.radius,
                center_y - self.radius,
                self.pos + self.radius,
                center_y + self.radius,
                fill=blend_color(
                    self.handle_color,
                    self.handle_active_color,
                    self.glow_level,
                ),
                outline=self.bg_color,
                width=2,
            )

        except tk.TclError:
            pass
