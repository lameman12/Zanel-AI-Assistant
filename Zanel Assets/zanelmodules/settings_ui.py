import os
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
import math
import colorsys
from zanelmodules.audio import list_input_devices
from zanelmodules.config import (
    DEFAULT_FONT_SIZE,
    DEFAULT_MIC_SENSITIVITY,
    DEFAULT_OPACITY,
    DEFAULT_THEME,
    DEFAULT_THEME_NAME,
    DEFAULT_TTS_VOICE,
    FONT_SIZES,
    GITHUB_RELEASES_URL,
    IS_MODIFIED,
    MIN_OPACITY,
    THEME_PRESETS,
    THEME_WIDGET_OPTIONS,
    TTS_VOICES,
    ZANEL_VERSION,
)
from zanelmodules.storage import find_data_folder, load_settings, save_settings
from zanelmodules.theme import (
    blend_color,
    get_theme,
    hex_to_hsv,
    hsv_to_hex,
    normalize_hex,
    theme_color_map,
)
from zanelmodules.widgets import ModernSlider


class SettingsMixin:

    def on_escape(self, _event=None):
        closer = getattr(self, "viewer_closer", None)

        if closer is not None:
            closer()
            return

        if self.settings_frame is not None:
            self.close_settings()
            return

        self.close()

    def persist_settings(self):
        return save_settings(
            {
                "voice": self.tts_voice,
                "silent_mode": self.silent_mode,
                "mic_muted": self.saved_mic_muted,
                "opacity": self.opacity,
                "always_on_top": self.always_on_top,
                "font_size": self.font_size,
                "mic_sensitivity": self.mic_sensitivity,
                "mic_device": self.mic_device,
                "multi_actions": self.multi_actions,
                "check_updates_start": self.check_updates_start,
                "confirm_close": self.confirm_close,
                "show_timestamps": self.show_timestamps,
                "auto_allow_actions": self.auto_allow_actions,
                "theme_name": self.theme_name,
                "theme_accent": self.theme_accent,
            }
        )

    def close_settings(self, force=False):
        if self.settings_frame is None:
            return

        if (
            not force
            and time.time() - self.last_settings_toggle < 0.8
        ):
            return

        if self.theme_editor is not None:
            self.theme_editor = None

            self.apply_theme(
                get_theme(
                    self.theme_name,
                    self.theme_accent,
                )
            )

        frame = self.settings_frame
        self.settings_frame = None
        self.last_settings_toggle = time.time()
        wheel_binding = getattr(frame, "advanced_wheel_binding", None)

        if wheel_binding:
            try:
                self.root._unbind(
                    ("bind", "all", "<MouseWheel>"),
                    wheel_binding,
                )
            except (AttributeError, tk.TclError):
                pass

        try:
            frame.destroy()
        except tk.TclError:
            pass

        self.apply_window_settings()
        self.apply_chat_font()
        if self.sidebar_reopen:
            self.sidebar_reopen = False
            self.set_sidebar(True)

        if (
            not self.settings_mic_was_muted
            and self.running
        ):
            self.set_mic(False)

    def open_settings(self):
        if self.settings_frame is not None:
            return

        now = time.time()

        if now - self.last_settings_toggle < 0.8:
            return

        self.last_settings_toggle = now

        self.sidebar_reopen = bool(self.sidebar_open)

        if self.sidebar_open:
            self.set_sidebar(False)

        frame = tk.Frame(
            self.root,
            bg="#0B0E14",
        )
        frame.place(
            x=0,
            y=42,
            relwidth=1.0,
            relheight=1.0,
            height=-42,
        )
        frame.lift()
        self.settings_frame = frame
        self.settings_mic_was_muted = self.saved_mic_muted
        self.set_mic(True)

        header = tk.Frame(frame, bg="#0B0E14")
        header.pack(fill="x", padx=16, pady=(12, 0))

        tk.Button(
            header,
            text="←  Back",
            command=self.close_settings,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI Symbol", 9, "bold"),
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            header,
            text="Settings",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=(12, 0))

        buttons = tk.Frame(frame, bg="#0B0E14")
        buttons.pack(side="bottom", fill="x", padx=22, pady=(0, 16))

        body = tk.Frame(frame, bg="#0B0E14")
        body.pack(fill="both", expand=True, padx=22, pady=(12, 0))

        tk.Label(
            body,
            text="Voice",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        tk.Label(
            body,
            text="Voices are generated by the Zanel server.",
            fg="#8290A8",
            bg="#0B0E14",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(0, 6))

        voice_var = tk.StringVar(value=self.tts_voice)

        voice_button = tk.Button(
            body,
            text=f"{self.tts_voice}   ▾",
            anchor="w",
            fg="#E8F5ED",
            bg="#121A16",
            activeforeground="#FFFFFF",
            activebackground="#1A2520",
            borderwidth=0,
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 10),
        )
        voice_button.pack(fill="x")

        list_frame = tk.Frame(
            frame,
            bg="#121A16",
            highlightthickness=1,
            highlightbackground="#293830",
        )

        list_scroll = tk.Scrollbar(
            list_frame,
            orient="vertical",
        )

        voice_list = tk.Listbox(
            list_frame,
            height=6,
            bg="#121A16",
            fg="#E8F5ED",
            selectbackground="#5CFF9D",
            selectforeground="#071019",
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            font=("Segoe UI", 9),
            yscrollcommand=list_scroll.set,
        )

        list_scroll.configure(command=voice_list.yview)
        list_scroll.pack(side="right", fill="y")
        voice_list.pack(side="left", fill="both", expand=True)

        for voice_name in TTS_VOICES:
            voice_list.insert("end", voice_name)

        list_state = {"open": False}
        hover_state = {"index": None}

        def update_voice_arrow():
            arrow = "▴" if list_state["open"] else "▾"

            voice_button.configure(
                text=f"{voice_var.get()}   {arrow}"
            )

        def chosen_index():
            if voice_var.get() in TTS_VOICES:
                return TTS_VOICES.index(voice_var.get())

            return None

        def highlight_index(index):
            if index is None:
                return

            voice_list.selection_clear(0, "end")
            voice_list.selection_set(index)

        def scroll_to_chosen():
            index = chosen_index()

            if index is None:
                return

            voice_list.update_idletasks()
            voice_list.yview(max(0, index - 2))

        def close_voice_list():
            list_state["open"] = False
            hover_state["index"] = None
            list_frame.place_forget()
            update_voice_arrow()

        def toggle_voice_list():
            if list_state["open"]:
                close_voice_list()
                return

            frame.update_idletasks()

            x = voice_button.winfo_rootx() - frame.winfo_rootx()
            y = (
                voice_button.winfo_rooty()
                - frame.winfo_rooty()
                + voice_button.winfo_height()
            )

            list_frame.place(
                x=x,
                y=y,
                width=voice_button.winfo_width(),
            )
            list_frame.lift()

            list_state["open"] = True
            hover_state["index"] = None
            update_voice_arrow()

            highlight_index(chosen_index())
            scroll_to_chosen()

            voice_list.focus_set()

        def hover_voice(event):
            index = voice_list.nearest(event.y)

            if index == hover_state["index"]:
                return

            hover_state["index"] = index
            highlight_index(index)

        def hover_from_pointer():
            if not list_state["open"]:
                return

            y = voice_list.winfo_pointery() - voice_list.winfo_rooty()
            index = voice_list.nearest(y)

            if index == hover_state["index"]:
                return

            hover_state["index"] = index
            highlight_index(index)

        def leave_voice_list(_event=None):
            hover_state["index"] = None
            highlight_index(chosen_index())

        def wheel_voice_list(_event=None):
            voice_list.after_idle(hover_from_pointer)

        def choose_voice(event=None):
            if event is not None and event.type == "5":
                index = voice_list.nearest(event.y)
            else:
                selection = voice_list.curselection()

                if not selection:
                    return

                index = selection[0]

            voice_var.set(TTS_VOICES[index])
            close_voice_list()

        voice_list.bind("<Motion>", hover_voice)
        voice_list.bind("<Leave>", leave_voice_list)
        voice_list.bind("<MouseWheel>", wheel_voice_list, add="+")
        voice_list.bind("<ButtonRelease-1>", choose_voice)
        voice_list.bind("<Return>", choose_voice)
        voice_button.configure(command=toggle_voice_list)

        speak_var = tk.BooleanVar(value=not self.silent_mode)

        mic_var = tk.BooleanVar(
            value=not self.settings_mic_was_muted
        )

        multi_var = tk.BooleanVar(value=self.multi_actions)

        startup_var = tk.BooleanVar(value=self.check_updates_start)
        close_var = tk.BooleanVar(value=self.confirm_close)
        stamp_var = tk.BooleanVar(value=self.show_timestamps)
        auto_allow_var = tk.BooleanVar(value=self.auto_allow_actions)

        tk.Label(
            body,
            text="Options",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(12, 4))

        toggle_card = tk.Frame(
            body,
            bg="#101713",
            highlightthickness=1,
            highlightbackground="#293830",
        )
        toggle_card.pack(fill="x")
        toggle_card.grid_columnconfigure(0, weight=1, uniform="toggles")
        toggle_card.grid_columnconfigure(1, weight=1, uniform="toggles")

        toggle_items = (
            ("Speak responses", speak_var),
            ("Microphone on", mic_var),
            ("Multiple actions (max 8)", multi_var),
            ("Check updates on start", startup_var),
            ("Confirm before closing", close_var),
            ("Show message times", stamp_var),
        )

        for toggle_index, (toggle_text, toggle_var) in enumerate(toggle_items):
            tk.Checkbutton(
                toggle_card,
                text=toggle_text,
                variable=toggle_var,
                anchor="w",
                fg="#E8F5ED",
                bg="#101713",
                selectcolor="#121A16",
                activeforeground="#FFFFFF",
                activebackground="#101713",
                highlightthickness=0,
                borderwidth=0,
                font=("Segoe UI", 9),
                cursor="hand2",
            ).grid(
                row=toggle_index // 2,
                column=toggle_index % 2,
                sticky="ew",
                padx=10,
                pady=6,
            )

        adv_scroll_frame = tk.Frame(frame, bg="#0B0E14")
        adv_canvas = tk.Canvas(
            adv_scroll_frame,
            bg="#0B0E14",
            highlightthickness=0,
            bd=0,
            yscrollincrement=18,
        )
        adv_scrollbar = tk.Scrollbar(
            adv_scroll_frame,
            orient="vertical",
            command=adv_canvas.yview,
            bg="#1A2520",
            activebackground="#293830",
            troughcolor="#0B0E14",
            width=8,
            borderwidth=0,
            highlightthickness=0,
        )
        adv_canvas.configure(yscrollcommand=adv_scrollbar.set)
        adv_scrollbar.pack(side="right", fill="y")
        adv_canvas.pack(side="left", fill="both", expand=True)

        adv_body = tk.Frame(adv_canvas, bg="#0B0E14")
        adv_body_window = adv_canvas.create_window(
            (0, 0),
            window=adv_body,
            anchor="nw",
        )

        def sync_advanced_region(_event=None):
            try:
                adv_canvas.configure(
                    scrollregion=adv_canvas.bbox("all") or (0, 0, 0, 0)
                )
            except tk.TclError:
                pass

        def sync_advanced_width(event):
            try:
                adv_canvas.itemconfigure(
                    adv_body_window,
                    width=max(1, event.width),
                )
            except tk.TclError:
                pass

        def scroll_advanced(event):
            try:
                target = self.root.winfo_containing(
                    event.x_root,
                    event.y_root,
                )
                target_path = str(target) if target is not None else ""
                body_path = str(adv_body)

                if not (
                    target_path == str(adv_canvas)
                    or target_path == body_path
                    or target_path.startswith(body_path + ".")
                ):
                    return

                if event.delta:
                    adv_canvas.yview_scroll(
                        -1 if event.delta > 0 else 1,
                        "units",
                    )

                return "break"
            except tk.TclError:
                return

        adv_body.bind("<Configure>", sync_advanced_region)
        adv_canvas.bind("<Configure>", sync_advanced_width)
        frame.advanced_wheel_binding = self.root.bind_all(
            "<MouseWheel>",
            scroll_advanced,
            add="+",
        )

        opacity_var = tk.IntVar(
            value=int(round(self.opacity * 100))
        )
        top_var = tk.BooleanVar(value=self.always_on_top)
        font_var = tk.IntVar(value=self.font_size)
        sens_var = tk.StringVar(value=self.mic_sensitivity)

        size_controls = tk.Frame(adv_body, bg="#0B0E14")
        size_controls.pack(fill="x", pady=(0, 8))
        size_controls.grid_columnconfigure(0, weight=1, uniform="size_controls")
        size_controls.grid_columnconfigure(1, weight=1, uniform="size_controls")

        opacity_group = tk.Frame(size_controls, bg="#0B0E14")
        opacity_group.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        opacity_label = tk.Label(
            opacity_group,
            text=f"Window opacity: {opacity_var.get()}%",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        )
        opacity_label.pack(anchor="w")

        ModernSlider(
            opacity_group,
            variable=opacity_var,
            from_=int(MIN_OPACITY * 100),
            to=100,
        ).pack(fill="x", pady=(2, 0))

        font_group = tk.Frame(size_controls, bg="#0B0E14")
        font_group.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        font_label = tk.Label(
            font_group,
            text=f"Chat text size: {font_var.get()}",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        )
        font_label.pack(anchor="w")

        ModernSlider(
            font_group,
            variable=font_var,
            from_=min(FONT_SIZES),
            to=max(FONT_SIZES),
        ).pack(fill="x", pady=(2, 0))

        tk.Checkbutton(
            adv_body,
            text="Keep window on top",
            variable=top_var,
            fg="#E8F5ED",
            bg="#0B0E14",
            selectcolor="#121A16",
            activeforeground="#FFFFFF",
            activebackground="#0B0E14",
            highlightthickness=0,
            borderwidth=0,
            pady=0,
            font=("Segoe UI", 10),
            cursor="hand2",
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            adv_body,
            text="Microphone sensitivity",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        sens_row = tk.Frame(adv_body, bg="#0B0E14")
        sens_row.pack(anchor="w", pady=(0, 6))

        for sens_text, sens_value in (
            ("Low", "low"),
            ("Medium", "medium"),
            ("High", "high"),
        ):
            tk.Radiobutton(
                sens_row,
                text=sens_text,
                value=sens_value,
                variable=sens_var,
                fg="#E8F5ED",
                bg="#0B0E14",
                selectcolor="#121A16",
                activeforeground="#FFFFFF",
                activebackground="#0B0E14",
                highlightthickness=0,
                borderwidth=0,
                font=("Segoe UI", 10),
                cursor="hand2",
            ).pack(side="left", padx=(0, 14))

        mic_dev_var = tk.StringVar(value=self.mic_device)
        mic_names = [""]
        mic_state = {"open": False, "wrap": 300}

        tk.Label(
            adv_body,
            text="Microphone",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        mic_button = tk.Button(
            adv_body,
            anchor="w",
            justify="left",
            fg="#E8F5ED",
            bg="#121A16",
            activeforeground="#FFFFFF",
            activebackground="#1A2520",
            borderwidth=0,
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        mic_button.pack(fill="x", pady=(2, 6))

        mic_list_frame = tk.Frame(
            frame,
            bg="#121A16",
            highlightthickness=1,
            highlightbackground="#293830",
        )

        mic_scroll = tk.Scrollbar(mic_list_frame, orient="vertical")
        mic_scroll.pack(side="right", fill="y")

        mic_canvas = tk.Canvas(
            mic_list_frame,
            bg="#121A16",
            highlightthickness=0,
            bd=0,
            yscrollincrement=20,
            yscrollcommand=mic_scroll.set,
        )
        mic_canvas.pack(side="left", fill="both", expand=True)
        mic_scroll.configure(command=mic_canvas.yview)

        mic_inner = tk.Frame(mic_canvas, bg="#121A16")
        mic_inner_window = mic_canvas.create_window(
            (0, 0),
            window=mic_inner,
            anchor="nw",
        )

        mic_canvas.zanel_skip = True
        mic_inner.zanel_skip = True

        def sync_mic_region(_event=None):
            try:
                mic_canvas.configure(
                    scrollregion=mic_canvas.bbox("all") or (0, 0, 0, 0)
                )
            except tk.TclError:
                pass

        def sync_mic_width(event):
            try:
                mic_canvas.itemconfigure(
                    mic_inner_window,
                    width=max(1, event.width),
                )
            except tk.TclError:
                pass

        mic_inner.bind("<Configure>", sync_mic_region)
        mic_canvas.bind("<Configure>", sync_mic_width)

        def wheel_mic(event):
            try:
                if mic_inner.winfo_reqheight() > mic_canvas.winfo_height():
                    mic_canvas.yview_scroll(
                        -1 if event.delta > 0 else 1,
                        "units",
                    )
            except tk.TclError:
                pass

            return "break"

        mic_canvas.bind("<MouseWheel>", wheel_mic)

        def update_mic_button(_event=None):
            arrow = "▴" if mic_state["open"] else "▾"
            name = mic_dev_var.get() or "Default microphone"

            try:
                width = mic_button.winfo_width()

                if width > 60:
                    wrap = width - 50

                    if wrap != mic_state["wrap"]:
                        mic_state["wrap"] = wrap
                        mic_button.configure(wraplength=wrap)

                text = f"{name}   {arrow}"

                if mic_button.cget("text") != text:
                    mic_button.configure(text=text)
            except tk.TclError:
                pass

        def close_mic_list():
            mic_state["open"] = False

            try:
                mic_list_frame.place_forget()
            except tk.TclError:
                pass

            update_mic_button()

        def pick_mic(name):
            mic_dev_var.set(name)
            close_mic_list()

        def paint_mic_row(label, name, hover):
            selected = name == mic_dev_var.get()

            if selected:
                label.configure(bg=self.theme["accent"], fg="#071019")
            elif hover:
                label.configure(bg=self.theme["button_hover"], fg="#FFFFFF")
            else:
                label.configure(bg=self.theme["field"], fg="#E8F5ED")

        def build_mic_rows(wrap):
            for child in mic_inner.winfo_children():
                child.destroy()

            mic_inner.configure(bg=self.theme["field"])
            mic_canvas.configure(bg=self.theme["field"])

            for name in mic_names:
                label = tk.Label(
                    mic_inner,
                    text=name or "Default microphone",
                    anchor="w",
                    justify="left",
                    wraplength=wrap,
                    padx=10,
                    pady=6,
                    cursor="hand2",
                    font=("Segoe UI", 9),
                )
                label.pack(fill="x")
                paint_mic_row(label, name, False)

                label.bind(
                    "<Enter>",
                    lambda _e, l=label, n=name: paint_mic_row(l, n, True),
                )
                label.bind(
                    "<Leave>",
                    lambda _e, l=label, n=name: paint_mic_row(l, n, False),
                )
                label.bind(
                    "<Button-1>",
                    lambda _e, n=name: pick_mic(n),
                )
                label.bind("<MouseWheel>", wheel_mic)

        def toggle_mic_list():
            if mic_state["open"]:
                close_mic_list()
                return

            mic_names[:] = [""] + list_input_devices()

            current = mic_dev_var.get()

            if current and current not in mic_names:
                mic_names.append(current)

            frame.update_idletasks()

            list_width = max(220, frame.winfo_width() - 44)

            build_mic_rows(list_width - 40)
            mic_inner.update_idletasks()

            list_height = min(mic_inner.winfo_reqheight(), 190) + 2

            button_top = mic_button.winfo_rooty() - frame.winfo_rooty()
            below = button_top + mic_button.winfo_height()

            if below + list_height > frame.winfo_height() - 8:
                y = max(0, button_top - list_height)
            else:
                y = below

            mic_list_frame.place(
                x=22,
                y=y,
                width=list_width,
                height=list_height,
            )
            mic_list_frame.lift()

            mic_canvas.yview_moveto(0)

            mic_state["open"] = True
            update_mic_button()

        mic_button.configure(command=toggle_mic_list)
        mic_button.bind("<Configure>", update_mic_button)
        mic_dev_var.trace_add("write", lambda *_args: update_mic_button())
        update_mic_button()

        adv_row = tk.Frame(adv_body, bg="#0B0E14")
        adv_row.pack(anchor="w", fill="x")

        adv_status = tk.Label(
            adv_body,
            text="",
            fg="#8290A8",
            bg="#0B0E14",
            font=("Segoe UI", 9),
            wraplength=380,
            justify="left",
        )

        adv_status_job = {"id": None}

        def show_adv_status(text, color="#8290A8"):
            if adv_status_job["id"] is not None:
                try:
                    adv_status.after_cancel(adv_status_job["id"])
                except tk.TclError:
                    pass

                adv_status_job["id"] = None

            def clear_adv_status():
                adv_status_job["id"] = None

                try:
                    adv_status.configure(text="")
                except tk.TclError:
                    pass

            try:
                adv_status.configure(text=text, fg=color)
                adv_status_job["id"] = adv_status.after(
                    4000,
                    clear_adv_status,
                )
            except tk.TclError:
                pass

        def reset_advanced_defaults():
            opacity_var.set(int(round(DEFAULT_OPACITY * 100)))
            top_var.set(True)
            font_var.set(DEFAULT_FONT_SIZE)
            sens_var.set(DEFAULT_MIC_SENSITIVITY)
            mic_dev_var.set("")
            auto_allow_var.set(False)
            show_adv_status("Defaults restored. Press Save.")

        tk.Button(
            adv_row,
            text="Restore defaults",
            command=reset_advanced_defaults,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 12))

        tk.Button(
            adv_row,
            text="Theme",
            command=self.open_theme_editor,
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 12))

        tk.Button(
            adv_row,
            text="Reset size",
            command=self.reset_window_size,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        adv_status.pack(anchor="w", pady=(6, 0))

        auto_allow_card = tk.Frame(
            adv_body,
            bg="#171216",
            highlightthickness=1,
            highlightbackground="#67333B",
        )
        auto_allow_card.pack(fill="x", pady=(10, 8))

        tk.Checkbutton(
            auto_allow_card,
            text="Auto-Allow actions",
            variable=auto_allow_var,
            anchor="w",
            fg="#FF8793",
            bg="#171216",
            selectcolor="#121A16",
            activeforeground="#FF9AA4",
            activebackground="#171216",
            highlightthickness=0,
            borderwidth=0,
            padx=10,
            pady=7,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        ).pack(fill="x")

        tk.Label(
            auto_allow_card,
            text="Runs action requests without asking you to confirm each one.",
            anchor="w",
            fg="#A8A0A4",
            bg="#171216",
            font=("Segoe UI", 8),
        ).pack(fill="x", padx=34, pady=(0, 8))

        def preview_opacity(*_args):
            try:
                value = int(opacity_var.get())
                opacity_label.configure(
                    text=f"Window opacity: {value}%"
                )
                self.apply_window_settings(opacity=value / 100.0)
            except (tk.TclError, ValueError):
                pass

        def preview_top(*_args):
            try:
                self.apply_window_settings(
                    topmost=bool(top_var.get())
                )
            except (tk.TclError, ValueError):
                pass

        def preview_font(*_args):
            try:
                value = int(font_var.get())
                font_label.configure(
                    text=f"Chat text size: {value}"
                )
                self.apply_chat_font(value)
            except (tk.TclError, ValueError):
                pass

        opacity_var.trace_add("write", preview_opacity)
        top_var.trace_add("write", preview_top)
        font_var.trace_add("write", preview_font)

        tab_state = {"page": "general"}

        general_tab = tk.Button(
            header,
            text="General",
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            borderwidth=0,
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

        advanced_tab = tk.Button(
            header,
            text="Advanced",
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

        advanced_tab.pack(side="right")
        general_tab.pack(side="right", padx=(0, 6))

        def style_tabs():
            active = {
                "bg": self.theme["accent"],
                "fg": "#071019",
                "activebackground": self.theme["accent_hover"],
                "activeforeground": "#071019",
            }

            inactive = {
                "bg": self.theme["button"],
                "fg": "#DDF8E8",
                "activebackground": self.theme["button_hover"],
                "activeforeground": "white",
            }

            try:
                general_tab.configure(
                    **(
                        active
                        if tab_state["page"] == "general"
                        else inactive
                    )
                )

                advanced_tab.configure(
                    **(
                        active
                        if tab_state["page"] == "advanced"
                        else inactive
                    )
                )
            except tk.TclError:
                pass

        def show_tab(page):
            if page == tab_state["page"]:
                return

            if list_state["open"]:
                close_voice_list()

            if mic_state["open"]:
                close_mic_list()

            try:
                if page == "advanced":
                    body.pack_forget()
                    adv_scroll_frame.pack(
                        fill="both",
                        expand=True,
                        padx=22,
                        pady=(12, 0),
                    )
                else:
                    adv_scroll_frame.pack_forget()
                    body.pack(
                        fill="both",
                        expand=True,
                        padx=22,
                        pady=(12, 0),
                    )
            except tk.TclError:
                return

            tab_state["page"] = page
            style_tabs()

        general_tab.configure(
            command=lambda: show_tab("general")
        )
        advanced_tab.configure(
            command=lambda: show_tab("advanced")
        )

        status = tk.Label(
            body,
            text="",
            fg="#8290A8",
            bg="#0B0E14",
            font=("Segoe UI", 9),
        )

        status_job = {"id": None}

        def clear_status():
            status_job["id"] = None

            try:
                status.configure(text="")
            except tk.TclError:
                pass

        def show_status(text, color="#8290A8"):
            if status_job["id"] is not None:
                try:
                    status.after_cancel(status_job["id"])
                except tk.TclError:
                    pass

            try:
                status.configure(
                    text=text,
                    fg=color,
                    wraplength=380,
                    justify="left",
                )

                status_job["id"] = status.after(
                    4000,
                    clear_status,
                )
            except tk.TclError:
                pass

        def open_data_folder():
            def restore_topmost():
                try:
                    self.root.attributes(
                        "-topmost",
                        bool(self.always_on_top),
                    )
                except tk.TclError:
                    pass

            try:
                folder = find_data_folder()

                folder.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                self.root.attributes("-topmost", False)

                subprocess.Popen(
                    [
                        "explorer.exe",
                        os.path.normpath(str(folder)),
                    ]
                )

            except Exception as exc:
                show_status(
                    f"Could not open folder: {exc}",
                    "#FF6B7A",
                )

            finally:
                self.root.after(3000, restore_topmost)

        button_row = tk.Frame(body, bg="#0B0E14")
        button_row.pack(anchor="w", fill="x", pady=(14, 0))

        tk.Button(
            button_row,
            text="Open Data File",
            command=open_data_folder,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        check_button = tk.Button(
            button_row,
            text="Check for updates",
            width=15,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            disabledforeground="#8290A8",
            borderwidth=0,
            relief="flat",
            padx=8,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        check_button.pack(side="left", padx=(8, 0))

        update_button = tk.Button(
            button_row,
            text="Get update",
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

        official_website_button = tk.Button(
            button_row,
            text="Official Website",
            command=self.open_official_website,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        official_website_button.pack(
            side="left",
            padx=(8, 0),
        )

        version_label = tk.Label(
            body,
            text="",
            fg="#8290A8",
            bg="#0B0E14",
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
        )
        version_label.zanel_keep_fg = True
        version_label.pack(anchor="w", pady=(6, 0))

        status.pack(anchor="w", pady=(2, 0))

        check_cooldown_seconds = 10.0
        check_min_display_seconds = 0.8
        auto_check_interval_ms = 300000
        check_state = {
            "until": 0.0,
            "min_until": 0.0,
            "manual": False,
        }
        version_job = {"id": None}
        auto_job = {"id": None}
        update_visible = {"value": False}

        def open_release_page():
            with self.update_lock:
                url = (
                    self.update_info.get("url")
                    or GITHUB_RELEASES_URL
                )

            try:
                webbrowser.open(url)
            except Exception as exc:
                show_status(
                    f"Could not open page: {exc}",
                    "#FF6B7A",
                )

        def render_version():
            previous_job = version_job["id"]
            version_job["id"] = None

            if previous_job is not None:
                try:
                    frame.after_cancel(previous_job)
                except tk.TclError:
                    pass

            if self.settings_frame is not frame:
                return

            try:
                with self.update_lock:
                    info = dict(self.update_info)

                now = time.time()
                state_value = info.get("status")
                checking = bool(info.get("checking"))
                failed = bool(info.get("failed"))
                latest_value = str(
                    info.get("latest") or "Unknown"
                ).lstrip("vV")
                version_text = f"Version {ZANEL_VERSION}"

                showing_check = (
                    check_state["manual"]
                    and (
                        checking
                        or now < check_state["min_until"]
                    )
                )

                if (
                    check_state["manual"]
                    and not checking
                    and now >= check_state["min_until"]
                ):
                    check_state["manual"] = False

                if showing_check or (
                    checking and state_value == "unknown"
                ):
                    text = (
                        f"{version_text}  •  "
                        "Checking for updates…"
                    )
                    color = "#8290A8"
                elif failed:
                    text = (
                        f"{version_text}  •  "
                        "Check failed. Check your connection."
                    )
                    color = "#FF6B7A"
                elif state_value == "outdated":
                    text = (
                        f"{version_text}  •  "
                        f"Update available: {latest_value}"
                    )
                    color = "#FFB347"
                elif state_value == "current":
                    text = (
                        f"{version_text}  •  Up to date"
                    )
                    color = "#5CFF9D"
                else:
                    text = (
                        f"{version_text}  •  "
                        "Not checked yet"
                    )
                    color = "#8290A8"

                if IS_MODIFIED:
                    text = f"{text}  •  Modified Client"
                    color = "#FFB347"

                version_label.configure(
                    text=text,
                    fg=color,
                )

                remaining = check_state["until"] - now
                cooling = remaining > 0

                if showing_check or checking:
                    check_button.configure(
                        text="Checking…",
                        state="disabled",
                        cursor="arrow",
                    )
                elif cooling:
                    check_button.configure(
                        text=f"Wait {math.ceil(remaining)}s",
                        state="disabled",
                        cursor="arrow",
                    )
                else:
                    check_button.configure(
                        text="Check for updates",
                        state="normal",
                        cursor="hand2",
                    )

                should_show_update = (
                    state_value == "outdated"
                    and not showing_check
                )

                if should_show_update:
                    if not update_visible["value"]:
                        update_button.pack(
                            side="left",
                            padx=(8, 0),
                        )
                        official_website_button.pack(
                            side="left",
                            padx=(8, 0),
                        )
                        update_visible["value"] = True
                else:
                    if update_visible["value"]:
                        update_button.pack_forget()
                        update_visible["value"] = False

                if checking or showing_check or cooling:
                    version_job["id"] = frame.after(
                        250,
                        render_version,
                    )

            except tk.TclError:
                pass

        def start_check():
            now = time.time()

            if now < check_state["until"]:
                return

            if self.start_update_check_async():
                check_state["until"] = (
                    now + check_cooldown_seconds
                )
                check_state["min_until"] = (
                    now + check_min_display_seconds
                )
                check_state["manual"] = True

            render_version()

        def auto_check():
            auto_job["id"] = None

            if self.settings_frame is not frame:
                return

            try:
                self.start_update_check_async()
                render_version()

                auto_job["id"] = frame.after(
                    auto_check_interval_ms,
                    auto_check,
                )

            except tk.TclError:
                pass

        check_button.configure(command=start_check)
        update_button.configure(command=open_release_page)

        with self.update_lock:
            last_status = self.update_info.get("status")
            last_failed = self.update_info.get("failed")
            last_checked = self.update_info.get(
                "checked_at",
                0.0,
            )

        if (
            last_status == "unknown"
            or last_failed
            or time.time() - last_checked > 60
        ):
            self.start_update_check_async()

        render_version()

        auto_job["id"] = frame.after(
            auto_check_interval_ms,
            auto_check,
        )

        test_button = tk.Button(
            buttons,
            text="Test voice",
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            disabledforeground="#5B6660",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        test_button.pack(side="left")

        def test_voice():
            if self.tts_busy:
                return

            test_button.configure(
                state="disabled",
                text="Speaking…",
            )

            threading.Thread(
                target=self._speak,
                args=(
                    "Hello, this is how I sound.",
                    voice_var.get(),
                ),
                daemon=True,
            ).start()

        test_button.configure(command=test_voice)

        saved_state = {
            "voice": self.tts_voice,
            "speak": not self.silent_mode,
            "multi": self.multi_actions,
            "mic": not self.settings_mic_was_muted,
            "opacity": int(round(self.opacity * 100)),
            "top": self.always_on_top,
            "font": self.font_size,
            "sens": self.mic_sensitivity,
            "mic_device": self.mic_device,
            "startup": self.check_updates_start,
            "close": self.confirm_close,
            "stamps": self.show_timestamps,
            "auto_allow": self.auto_allow_actions,
        }

        last_loaded = load_settings()

        save_cooldown_seconds = 3.0
        cooldown_state = {
            "until": 0.0,
            "job": None,
        }

        def in_cooldown():
            return time.time() < cooldown_state["until"]

        def has_changes():
            return (
                voice_var.get() != saved_state["voice"]
                or bool(speak_var.get()) != saved_state["speak"]
                or bool(mic_var.get()) != saved_state["mic"]
                or int(opacity_var.get()) != saved_state["opacity"]
                or bool(top_var.get()) != saved_state["top"]
                or int(font_var.get()) != saved_state["font"]
                or sens_var.get() != saved_state["sens"]
                or bool(multi_var.get()) != saved_state["multi"]
                or mic_dev_var.get() != saved_state["mic_device"]
                or bool(startup_var.get()) != saved_state["startup"]
                or bool(close_var.get()) != saved_state["close"]
                or bool(stamp_var.get()) != saved_state["stamps"]
                or bool(auto_allow_var.get()) != saved_state["auto_allow"]
            )

        def reset_general_defaults():
            voice_var.set(DEFAULT_TTS_VOICE)
            speak_var.set(True)
            mic_var.set(True)
            multi_var.set(True)
            startup_var.set(True)
            close_var.set(True)
            stamp_var.set(False)
            update_voice_arrow()
            show_status("Defaults restored. Press Save.")

        tk.Button(
            buttons,
            text="Restore defaults",
            command=reset_general_defaults,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(10, 0))

        save_button = tk.Button(
            buttons,
            text="Save",
            fg="#071019",
            bg="#1A2520",
            activeforeground="#071019",
            activebackground="#72FFAB",
            disabledforeground="#5B6660",
            borderwidth=0,
            relief="flat",
            padx=18,
            pady=8,
            cursor="arrow",
            font=("Segoe UI", 9, "bold"),
            state="disabled",
        )
        save_button.pack(side="right")

        def update_save_button(*_args):
            try:
                if in_cooldown():
                    save_button.configure(
                        text="Wait…",
                        state="disabled",
                        bg=self.theme["button"],
                        cursor="arrow",
                    )
                elif has_changes():
                    save_button.configure(
                        text="Save",
                        state="normal",
                        bg=self.theme["accent"],
                        cursor="hand2",
                    )
                else:
                    save_button.configure(
                        text="Save",
                        state="disabled",
                        bg=self.theme["button"],
                        cursor="arrow",
                    )
            except tk.TclError:
                pass

        def end_cooldown():
            cooldown_state["job"] = None
            cooldown_state["until"] = 0.0
            update_save_button()

        def start_cooldown():
            if cooldown_state["job"] is not None:
                try:
                    save_button.after_cancel(cooldown_state["job"])
                except tk.TclError:
                    pass

                cooldown_state["job"] = None

            cooldown_state["until"] = (
                time.time() + save_cooldown_seconds
            )

            try:
                cooldown_state["job"] = save_button.after(
                    int(save_cooldown_seconds * 1000),
                    end_cooldown,
                )
            except tk.TclError:
                cooldown_state["job"] = None
                cooldown_state["until"] = 0.0

        def save_changes():
            if in_cooldown():
                return

            if not has_changes():
                return

            previous = (
                self.tts_voice,
                self.silent_mode,
                self.settings_mic_was_muted,
                self.saved_mic_muted,
                self.opacity,
                self.always_on_top,
                self.font_size,
                self.mic_sensitivity,
                self.multi_actions,
                self.mic_device,
                self.check_updates_start,
                self.confirm_close,
                self.show_timestamps,
                self.auto_allow_actions,
            )

            self.tts_voice = voice_var.get()
            self.silent_mode = not speak_var.get()
            self.settings_mic_was_muted = not mic_var.get()
            self.saved_mic_muted = self.settings_mic_was_muted
            self.opacity = round(int(opacity_var.get()) / 100.0, 2)
            self.always_on_top = bool(top_var.get())
            self.font_size = int(font_var.get())
            self.mic_sensitivity = sens_var.get()
            self.multi_actions = bool(multi_var.get())
            self.mic_device = mic_dev_var.get().strip()
            self.check_updates_start = bool(startup_var.get())
            self.confirm_close = bool(close_var.get())
            self.show_timestamps = bool(stamp_var.get())
            self.auto_allow_actions = bool(auto_allow_var.get())
            stamps_changed = previous[12] != self.show_timestamps

            saved = self.persist_settings()

            if not saved:
                (
                    self.tts_voice,
                    self.silent_mode,
                    self.settings_mic_was_muted,
                    self.saved_mic_muted,
                    self.opacity,
                    self.always_on_top,
                    self.font_size,
                    self.mic_sensitivity,
                    self.multi_actions,
                    self.mic_device,
                    self.check_updates_start,
                    self.confirm_close,
                    self.show_timestamps,
                    self.auto_allow_actions,
                ) = previous

                show_status(
                    "Could not save settings.",
                    "#FF6B7A",
                )
                show_adv_status(
                    "Could not save settings.",
                    "#FF6B7A",
                )
                return

            saved_state["voice"] = self.tts_voice
            saved_state["speak"] = not self.silent_mode
            saved_state["mic"] = not self.settings_mic_was_muted
            saved_state["opacity"] = int(round(self.opacity * 100))
            saved_state["top"] = self.always_on_top
            saved_state["font"] = self.font_size
            saved_state["sens"] = self.mic_sensitivity
            saved_state["multi"] = self.multi_actions
            saved_state["mic_device"] = self.mic_device
            saved_state["startup"] = self.check_updates_start
            saved_state["close"] = self.confirm_close
            saved_state["stamps"] = self.show_timestamps
            saved_state["auto_allow"] = self.auto_allow_actions

            try:
                last_loaded.update(load_settings())
            except Exception:
                pass

            if list_state["open"]:
                close_voice_list()

            start_cooldown()
            update_save_button()

            show_status(
                "Settings saved.",
                "#5CFF9D",
            )
            show_adv_status(
                "Settings saved.",
                "#5CFF9D",
            )
            render_version()

            if (
                stamps_changed
                and not self.chat_loading
                and self.active_chat_id
            ):
                self.activate_chat(self.active_chat_id, force=True)

        save_button.configure(command=save_changes)

        voice_var.trace_add("write", update_save_button)
        speak_var.trace_add("write", update_save_button)
        mic_var.trace_add("write", update_save_button)
        opacity_var.trace_add("write", update_save_button)
        top_var.trace_add("write", update_save_button)
        multi_var.trace_add("write", update_save_button)
        font_var.trace_add("write", update_save_button)
        sens_var.trace_add("write", update_save_button)
        mic_dev_var.trace_add("write", update_save_button)
        startup_var.trace_add("write", update_save_button)
        close_var.trace_add("write", update_save_button)
        stamp_var.trace_add("write", update_save_button)
        auto_allow_var.trace_add("write", update_save_button)

        def refresh_settings():
            if self.settings_frame is not frame:
                return

            try:
                current = load_settings()

                if current != last_loaded:
                    last_loaded.update(current)

                    saved_state["voice"] = current["voice"]
                    saved_state["speak"] = not current["silent_mode"]
                    saved_state["mic"] = not current["mic_muted"]
                    saved_state["opacity"] = int(
                        round(current["opacity"] * 100)
                    )
                    saved_state["top"] = current["always_on_top"]
                    saved_state["font"] = current["font_size"]
                    saved_state["sens"] = current["mic_sensitivity"]
                    saved_state["multi"] = current["multi_actions"]
                    saved_state["mic_device"] = current["mic_device"]
                    saved_state["startup"] = current["check_updates_start"]
                    saved_state["close"] = current["confirm_close"]
                    saved_state["stamps"] = current["show_timestamps"]
                    saved_state["auto_allow"] = current["auto_allow_actions"]

                    voice_var.set(current["voice"])
                    speak_var.set(not current["silent_mode"])
                    mic_var.set(not current["mic_muted"])
                    opacity_var.set(
                        int(round(current["opacity"] * 100))
                    )
                    top_var.set(current["always_on_top"])
                    font_var.set(current["font_size"])
                    sens_var.set(current["mic_sensitivity"])
                    multi_var.set(current["multi_actions"])
                    mic_dev_var.set(current["mic_device"])
                    startup_var.set(current["check_updates_start"])
                    close_var.set(current["confirm_close"])
                    stamp_var.set(current["show_timestamps"])
                    auto_allow_var.set(current["auto_allow_actions"])
                    self.settings_mic_was_muted = current["mic_muted"]

                    update_voice_arrow()
                    update_save_button()

                frame.after(5000, refresh_settings)

            except tk.TclError:
                pass

        frame.after(5000, refresh_settings)

        def refresh_test_button():
            if self.settings_frame is not frame:
                return

            try:
                if self.tts_busy:
                    test_button.configure(
                        state="disabled",
                        text="Speaking…",
                    )
                else:
                    test_button.configure(
                        state="normal",
                        text="Test voice",
                    )

                frame.after(150, refresh_test_button)

            except tk.TclError:
                pass

        refresh_test_button()

        self.recolor_tree(frame, DEFAULT_THEME, self.theme)

    def recolor_tree(self, widget, source, target):
        mapping = theme_color_map(source, target)

        if mapping:
            self.recolor_widget(widget, mapping)

    def recolor_widget(self, widget, mapping):
        if getattr(widget, "zanel_skip", False):
            return

        keep_fg = getattr(widget, "zanel_keep_fg", False)

        for option in THEME_WIDGET_OPTIONS:
            if keep_fg and option in (
                "fg",
                "activeforeground",
                "disabledforeground",
            ):
                continue

            try:
                current = str(widget.cget(option)).lower()
                replacement = mapping.get(current)

                if replacement:
                    widget.configure(**{option: replacement})
            except tk.TclError:
                continue

        if isinstance(widget, ModernSlider):
            for attribute in (
                "bg_color",
                "track_color",
                "fill_color",
                "handle_color",
                "glow_color",
            ):
                replacement = mapping.get(
                    str(getattr(widget, attribute)).lower()
                )

                if replacement:
                    setattr(widget, attribute, replacement)

            widget.draw()
            return

        if isinstance(widget, tk.Canvas):
            try:
                items = widget.find_all()
            except tk.TclError:
                items = ()

            for item in items:
                for option in ("fill", "outline"):
                    try:
                        current = str(
                            widget.itemcget(item, option)
                        ).lower()
                        replacement = mapping.get(current)

                        if replacement:
                            widget.itemconfigure(
                                item,
                                **{option: replacement},
                            )
                    except tk.TclError:
                        continue

        try:
            children = widget.winfo_children()
        except tk.TclError:
            return

        for child in children:
            self.recolor_widget(child, mapping)

    def apply_theme(self, new_theme):
        self.recolor_tree(self.root, self.theme, new_theme)
        self.theme = dict(new_theme)
        self.recolor_compact_window()
        self.rebuild_skip_pulse()
        self.sync_window_background()

    def recolor_compact_window(self):
        canvas = getattr(
            self,
            "compact_canvas",
            None
        )

        if canvas is None:
            return

        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return

        canvas.itemconfigure(
            "compact_border",
            fill=self.theme["border"],
        )

        canvas.itemconfigure(
            "compact_accent",
            fill=self.theme["accent"],
        )

    def rebuild_skip_pulse(self):
        start_color = blend_color(
            self.theme["title"],
            self.theme["accent"],
            0.4,
        )

        forward = [
            blend_color(
                start_color,
                self.theme["accent"],
                step / 10,
            )
            for step in range(11)
        ]

        self.skip_pulse_colors = tuple(
            forward + forward[-2:0:-1]
        )

        self.reset_skip_button_style()

    def open_theme_editor(self):
        parent = self.settings_frame

        if parent is None or self.theme_editor is not None:
            return

        editor = tk.Frame(parent, bg="#0B0E14")
        editor.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        editor.lift()
        self.theme_editor = editor

        sv_width = 210
        sv_height = 110
        hue_width = 406

        start_accent = THEME_PRESETS.get(
            self.theme_name,
            self.theme_accent,
        )

        start_h, start_s, start_v = hex_to_hsv(start_accent)

        state = {
            "h": min(start_h, 0.999),
            "s": start_s,
            "v": start_v,
            "name": self.theme_name,
            "job": None,
        }

        images = {"sv": None, "hue": None}
        holders = {}

        def current_hex():
            return hsv_to_hex(state["h"], state["s"], state["v"])

        def current_rgb():
            value = current_hex()

            return tuple(
                int(value[index:index + 2], 16)
                for index in (1, 3, 5)
            )

        save_state = {"until": 0.0, "job": None}
        save_cooldown_seconds = 3.0

        def close_editor(save):
            for job_holder in (state, save_state):
                if job_holder["job"] is not None:
                    try:
                        editor.after_cancel(job_holder["job"])
                    except tk.TclError:
                        pass

                    job_holder["job"] = None

            self.theme_editor = None

            self.apply_theme(
                get_theme(
                    self.theme_name,
                    self.theme_accent,
                )
            )

            try:
                editor.destroy()
            except tk.TclError:
                pass

        header = tk.Frame(editor, bg="#0B0E14")
        header.pack(fill="x", padx=16, pady=(10, 0))

        tk.Button(
            header,
            text="←  Back",
            command=lambda: close_editor(False),
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI Symbol", 9, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text="Theme",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=(12, 0))

        footer = tk.Frame(editor, bg="#0B0E14")
        footer.pack(side="bottom", fill="x", padx=22, pady=(10, 14))

        body = tk.Frame(editor, bg="#0B0E14")
        body.pack(fill="both", expand=True, padx=22, pady=(10, 0))

        presets_row = tk.Frame(body, bg="#0B0E14")
        presets_row.pack(fill="x")

        tk.Label(
            presets_row,
            text="Presets",
            fg="#F2F6FF",
            bg="#0B0E14",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        name_label = tk.Label(
            presets_row,
            text="",
            fg="#8290A8",
            bg="#0B0E14",
            font=("Segoe UI", 9),
        )
        name_label.pack(side="right")

        swatches = tk.Frame(body, bg="#0B0E14")
        swatches.pack(anchor="w", pady=(4, 8))

        picker_row = tk.Frame(body, bg="#0B0E14")
        picker_row.pack(fill="x")

        sv_canvas = tk.Canvas(
            picker_row,
            width=sv_width,
            height=sv_height,
            bg="#0B0E14",
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        sv_canvas.zanel_skip = True
        sv_canvas.pack(side="left")

        preview = tk.Frame(
            picker_row,
            height=sv_height,
            bg="#101713",
            highlightthickness=1,
            highlightbackground="#293830",
        )
        preview.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(14, 0),
        )
        preview.pack_propagate(False)

        tk.Label(
            preview,
            text="PREVIEW",
            fg="#8290A8",
            bg="#101713",
            font=("Segoe UI", 7, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 0))

        tk.Label(
            preview,
            text="Zanel: Hello there!",
            fg="#E8F5ED",
            bg="#101713",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=12, pady=(6, 0))

        preview_buttons = tk.Frame(preview, bg="#101713")
        preview_buttons.pack(
            side="bottom",
            fill="x",
            padx=12,
            pady=(0, 12),
        )

        tk.Button(
            preview_buttons,
            text="● Mic",
            fg="#DDF8E8",
            bg="#17241D",
            activeforeground="white",
            activebackground="#013220",
            borderwidth=0,
            relief="flat",
            pady=5,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", fill="x", expand=True)

        tk.Button(
            preview_buttons,
            text="Clear",
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            pady=5,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        tk.Button(
            preview_buttons,
            text="Send",
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            borderwidth=0,
            relief="flat",
            pady=5,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        hue_canvas = tk.Canvas(
            body,
            width=hue_width,
            height=12,
            bg="#0B0E14",
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        hue_canvas.zanel_skip = True
        hue_canvas.pack(anchor="w", pady=(10, 0))

        fields = tk.Frame(body, bg="#0B0E14")
        fields.pack(fill="x", pady=(10, 0))

        hex_var = tk.StringVar()
        r_var = tk.StringVar()
        g_var = tk.StringVar()
        b_var = tk.StringVar()

        def make_field(label, variable, width):
            tk.Label(
                fields,
                text=label,
                fg="#8290A8",
                bg="#0B0E14",
                font=("Segoe UI", 8, "bold"),
            ).pack(side="left", padx=(0, 5))

            entry = tk.Entry(
                fields,
                textvariable=variable,
                width=width,
                justify="center",
                bg="#121A16",
                fg="#E8F5ED",
                insertbackground="white",
                relief="flat",
                borderwidth=0,
                font=("Segoe UI", 10),
            )
            entry.pack(side="left", ipady=4, padx=(0, 12))

            return entry

        hex_entry = make_field("HEX", hex_var, 8)
        r_entry = make_field("R", r_var, 4)
        g_entry = make_field("G", g_var, 4)
        b_entry = make_field("B", b_var, 4)

        chip = tk.Frame(
            fields,
            width=34,
            height=26,
            bg=current_hex(),
        )
        chip.zanel_skip = True
        chip.pack(side="right")
        chip.pack_propagate(False)

        hue_image = tk.PhotoImage(width=hue_width // 2, height=1)
        hue_image.put(
            "{"
            + " ".join(
                hsv_to_hex(x / float(hue_width // 2), 1.0, 1.0)
                for x in range(hue_width // 2)
            )
            + "}"
        )
        images["hue"] = hue_image.zoom(2, 12)

        hue_canvas.create_image(
            0,
            0,
            image=images["hue"],
            anchor="nw",
        )

        def draw_hue_marker():
            hue_canvas.delete("marker")
            x = state["h"] * (hue_width - 1)

            hue_canvas.create_rectangle(
                x - 3,
                0,
                x + 3,
                12,
                outline="#FFFFFF",
                width=2,
                tags="marker",
            )

        def draw_sv_marker():
            sv_canvas.delete("marker")
            x = state["s"] * (sv_width - 1)
            y = (1.0 - state["v"]) * (sv_height - 1)

            sv_canvas.create_oval(
                x - 7,
                y - 7,
                x + 7,
                y + 7,
                outline="#000000",
                width=2,
                tags="marker",
            )

            sv_canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                outline="#FFFFFF",
                width=2,
                tags="marker",
            )

        def render_sv():
            small_width = sv_width // 2
            small_height = sv_height // 2

            image = tk.PhotoImage(
                width=small_width,
                height=small_height,
            )

            rows = []

            for y in range(small_height):
                value = 1.0 - y / (small_height - 1)

                rows.append(
                    "{"
                    + " ".join(
                        hsv_to_hex(
                            state["h"],
                            x / (small_width - 1),
                            value,
                        )
                        for x in range(small_width)
                    )
                    + "}"
                )

            image.put(" ".join(rows))
            images["sv"] = image.zoom(2, 2)

            sv_canvas.delete("all")

            sv_canvas.create_image(
                0,
                0,
                image=images["sv"],
                anchor="nw",
            )

            draw_sv_marker()

        def refresh_swatches():
            for preset_name, holder in holders.items():
                try:
                    holder.configure(
                        bg=(
                            "#FFFFFF"
                            if state["name"] == preset_name
                            else self.theme["bg"]
                        )
                    )
                except tk.TclError:
                    pass

        def update_info():
            red, green, blue = current_rgb()

            hex_var.set(current_hex().upper())
            r_var.set(str(red))
            g_var.set(str(green))
            b_var.set(str(blue))

            try:
                chip.configure(bg=current_hex())
            except tk.TclError:
                pass

            name_label.configure(text=state["name"])

        def schedule_preview():
            if state["job"] is not None:
                return

            def run():
                state["job"] = None

                if self.theme_editor is not editor:
                    return

                self.apply_theme(
                    get_theme(
                        state["name"],
                        current_hex(),
                    )
                )

                refresh_swatches()

            try:
                state["job"] = editor.after(40, run)
            except tk.TclError:
                state["job"] = None

        def refresh_all():
            render_sv()
            draw_hue_marker()
            update_info()
            refresh_swatches()
            schedule_preview()

        def choose_preset(name):
            h, s, v = hex_to_hsv(THEME_PRESETS[name])

            state["name"] = name
            state["h"] = min(h, 0.999)
            state["s"] = s
            state["v"] = v

            refresh_all()

        def set_sv(event):
            state["s"] = max(0.0, min(1.0, event.x / float(sv_width - 1)))
            state["v"] = max(
                0.0,
                min(1.0, 1.0 - event.y / float(sv_height - 1)),
            )
            state["name"] = "Custom"

            draw_sv_marker()
            update_info()
            refresh_swatches()
            schedule_preview()

        def set_hue(event):
            state["h"] = max(
                0.0,
                min(0.999, event.x / float(hue_width - 1)),
            )
            state["name"] = "Custom"

            render_sv()
            draw_hue_marker()
            update_info()
            refresh_swatches()
            schedule_preview()

        def apply_hex(_event=None):
            if self.theme_editor is not editor:
                return

            raw = hex_var.get().strip()

            if not raw.startswith("#"):
                raw = "#" + raw

            value = normalize_hex(raw)

            if not value:
                update_info()
                return

            h, s, v = hex_to_hsv(value)

            state["h"] = min(h, 0.999)
            state["s"] = s
            state["v"] = v
            state["name"] = "Custom"

            refresh_all()

        def apply_rgb(_event=None):
            if self.theme_editor is not editor:
                return

            try:
                red = max(0, min(255, int(r_var.get().strip())))
                green = max(0, min(255, int(g_var.get().strip())))
                blue = max(0, min(255, int(b_var.get().strip())))
            except ValueError:
                update_info()
                return

            h, s, v = colorsys.rgb_to_hsv(
                red / 255.0,
                green / 255.0,
                blue / 255.0,
            )

            if s > 0 and v > 0:
                state["h"] = min(h, 0.999)

            state["s"] = s
            state["v"] = v
            state["name"] = "Custom"

            refresh_all()

        def step_channel(variable, amount):
            try:
                value = int(variable.get().strip())
            except ValueError:
                value = 0

            variable.set(str(max(0, min(255, value + amount))))
            apply_rgb()

        for entry, variable in (
            (r_entry, r_var),
            (g_entry, g_var),
            (b_entry, b_var),
        ):
            entry.bind("<Return>", apply_rgb)
            entry.bind("<FocusOut>", apply_rgb)

            entry.bind(
                "<MouseWheel>",
                lambda event, v=variable: step_channel(
                    v,
                    (1 if event.delta > 0 else -1)
                    * (10 if event.state & 0x1 else 1),
                ),
            )

            entry.bind(
                "<Up>",
                lambda event, v=variable: (
                    step_channel(
                        v,
                        10 if event.state & 0x1 else 1,
                    ),
                    "break",
                )[1],
            )

            entry.bind(
                "<Down>",
                lambda event, v=variable: (
                    step_channel(
                        v,
                        -10 if event.state & 0x1 else -1,
                    ),
                    "break",
                )[1],
            )

        hex_entry.bind("<Return>", apply_hex)
        hex_entry.bind("<FocusOut>", apply_hex)

        for preset_name, preset_accent in THEME_PRESETS.items():
            holder = tk.Frame(swatches, bg="#0B0E14")
            holder.pack(side="left", padx=(0, 6))
            holders[preset_name] = holder

            swatch = tk.Frame(
                holder,
                width=34,
                height=20,
                bg=preset_accent,
                cursor="hand2",
            )
            swatch.zanel_skip = True
            swatch.pack(padx=2, pady=2)

            swatch.bind(
                "<Button-1>",
                lambda _event, n=preset_name: choose_preset(n),
            )

            swatch.bind(
                "<Enter>",
                lambda _event, n=preset_name: name_label.configure(
                    text=n
                ),
            )

            swatch.bind(
                "<Leave>",
                lambda _event: name_label.configure(
                    text=state["name"]
                ),
            )

        sv_canvas.bind("<ButtonPress-1>", set_sv)
        sv_canvas.bind("<B1-Motion>", set_sv)
        hue_canvas.bind("<ButtonPress-1>", set_hue)
        hue_canvas.bind("<B1-Motion>", set_hue)

        tk.Button(
            footer,
            text="Reset to default",
            command=lambda: choose_preset(DEFAULT_THEME_NAME),
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        save_button = tk.Button(
            footer,
            text="Apply & Save",
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            disabledforeground="#5B6660",
            borderwidth=0,
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        save_button.pack(side="right")

        def update_save_button():
            save_state["job"] = None

            if self.theme_editor is not editor:
                return

            remaining = save_state["until"] - time.time()

            try:
                if remaining > 0:
                    save_button.configure(
                        text=f"Wait {math.ceil(remaining)}s",
                        state="disabled",
                        bg=self.theme["button"],
                        cursor="arrow",
                    )

                    save_state["job"] = editor.after(
                        250,
                        update_save_button,
                    )
                else:
                    save_button.configure(
                        text="Apply & Save",
                        state="normal",
                        bg=self.theme["accent"],
                        cursor="hand2",
                    )
            except tk.TclError:
                save_state["job"] = None

        def save_theme():
            if time.time() < save_state["until"]:
                return

            if self.theme_editor is not editor:
                return

            accent = current_hex()

            if state["name"] in THEME_PRESETS:
                accent = THEME_PRESETS[state["name"]]

            self.theme_name = state["name"]
            self.theme_accent = accent
            self.persist_settings()

            self.apply_theme(
                get_theme(
                    self.theme_name,
                    self.theme_accent,
                )
            )

            refresh_swatches()

            save_state["until"] = (
                time.time() + save_cooldown_seconds
            )

            if save_state["job"] is not None:
                try:
                    editor.after_cancel(save_state["job"])
                except tk.TclError:
                    pass

                save_state["job"] = None

            update_save_button()

        save_button.configure(command=save_theme)

        render_sv()
        draw_hue_marker()
        update_info()

        self.recolor_tree(editor, DEFAULT_THEME, self.theme)

        refresh_swatches()
