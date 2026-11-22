import tkinter as tk
from zanelmodules.theme import blend_color


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
