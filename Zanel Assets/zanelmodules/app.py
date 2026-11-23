import os
import queue
import threading
import time
import tkinter as tk
from collections import deque
import uuid
import ctypes.wintypes
from tkinter import filedialog
import ctypes
import sounddevice as sd
from zanelmodules.config import (
    APP_DATA_DIR,
    DEFAULT_THEME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    GITHUB_RELEASES_URL,
    INPUT_PLACEHOLDER,
    MAX_CHATS,
    RAIL_WIDTH,
    SEND_COOLDOWN,
    SIDEBAR_WIDTH,
)
from zanelmodules.resources import resource_path
from zanelmodules.widgets import ThemedScrollbar
from zanelmodules.storage import (
    ChatStore,
    load_drafts,
    load_settings,
    load_window_state,
)
from zanelmodules.theme import get_theme
from zanelmodules.action_parser import ParserMixin
from zanelmodules.network import NetworkMixin
from zanelmodules.voice import VoiceMixin
from zanelmodules.popups import PopupMixin
from zanelmodules.pastes import PasteMixin
from zanelmodules.window import WindowMixin
from zanelmodules.chat_view import ChatViewMixin
from zanelmodules.sidebar import SidebarMixin
from zanelmodules.settings_ui import SettingsMixin
from zanelmodules.updates import UpdateMixin
from zanelmodules.api_key import ApiKeyMixin


class ZanelApp(ParserMixin, NetworkMixin, VoiceMixin, PopupMixin, PasteMixin, WindowMixin, ChatViewMixin, SidebarMixin, SettingsMixin, UpdateMixin, ApiKeyMixin):

    toast_window = None
    toast_token = 0
    resizing = False
    _bg_brush = None
    _bg_brush_color = None
    rename_window = None
    last_rename_time = 0.0
    toast_bar = None
    edge_cursor = ""
    sidebar_reopen = False
    invalid_key_active = False
    key_lock = threading.Lock()
    taskbar_window = None
    taskbar_ready = False
    taskbar_busy = False
    taskbar_suspended = False

    def __init__(self):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Zanel.Assistant.App"
            )
        except Exception:
            pass

        self.root = tk.Tk()

        try:
            self.root.iconbitmap(default=resource_path("zanelicon.ico"))
        except Exception:
            pass
        self.root.title("")
        self.root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}+40+80")
        self.root.configure(bg="#0b0e14")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)

        self.running = True
        self.root.zanel_app = self
        self.confirm_queue = deque()
        self.confirm_active = None
        self.permission_status_lock = threading.Lock()
        self.pending_permission_count = 0
        self.mic_muted = False
        self.busy_chats = set()
        self.response_lock = threading.Lock()
        self.current_cancel_event = None
        self.current_request_chat_id = None
        self.current_turn_id = None
        self.current_request_dispatched = False
        self.cancelled_turn_ids = set()
        self.preserved_turn_ids = set()
        self.last_message_time = 0.0
        self.message_cooldown = SEND_COOLDOWN
        self.last_clear_time = 0.0
        self.clear_cooldown = 7.0
        self.tts_busy = False
        self.tts_skip = False
        self.skip_visible = False
        self.silent_mode = False
        self.audio_level = 0.0
        self.messages = queue.Queue()
        self.last_action_feedback = ""
        self.last_feedback_time = 0
        self.drag_x = 0
        self.drag_y = 0
        settings = load_settings()
        self.tts_voice = settings["voice"]
        self.silent_mode = settings["silent_mode"]
        self.opacity = settings["opacity"]
        self.always_on_top = settings["always_on_top"]
        self.font_size = settings["font_size"]
        self.mic_sensitivity = settings["mic_sensitivity"]
        self.multi_actions = settings["multi_actions"]
        self.mic_device = settings["mic_device"]
        self.check_updates_start = settings["check_updates_start"]
        self.confirm_close = settings["confirm_close"]
        self.show_timestamps = settings["show_timestamps"]
        self.auto_allow_actions = settings["auto_allow_actions"]
        self.web_search = settings["web_search"]
        self.theme_name = settings["theme_name"]
        self.theme_accent = settings["theme_accent"]
        self.theme = dict(DEFAULT_THEME)
        self.theme_editor = None
        self.settings_frame = None
        self.settings_mic_was_muted = False
        self.saved_mic_muted = settings["mic_muted"]
        self.mic_muted = self.saved_mic_muted
        self.last_settings_toggle = 0.0
        self.tts_lock = threading.Lock()
        self.music_process = None
        self.music_temp_file = None
        self.music_cleanup_thread = None
        self.music_lock = threading.Lock()
        self.feedback_id = uuid.uuid4().hex
        self.music_stopped_by_zanel = False
        self.attached_image_path = None
        self.last_image_select_time = 0.0
        self.screenshot_status_until = 0.0
        self.compact_window = None
        self.normal_geometry = None
        self.compact_saved_geometry = None
        self.compact_width = 270
        self.compact_height = 230
        self.compact_drag_x = 0
        self.compact_drag_y = 0
        self.rickroll_process = None
        self.rickroll_lock = threading.Lock()
        self.update_lock = threading.Lock()
        self.update_info = {
            "status": "unknown",
            "checking": False,
            "failed": False,
            "latest": "",
            "url": GITHUB_RELEASES_URL,
            "checked_at": 0.0,
        }
        self.compact_dragging = False
        self.minimize_transition = False
        self.restore_transition = False
        self.api_key = self.load_api_key()
        self.chat_store = ChatStore(APP_DATA_DIR)
        self.window_state = load_window_state()
        self.sidebar_open = self.window_state["sidebar_open"]
        self.sidebar_job = None
        self.sidebar_px = 0
        self.sidebar_toggle_cooldown_until = 0.0
        self.sidebar_toggle_cooldown_job = None
        self.toast_job = None
        self.viewer_window = None
        self.win_mode = "normal"
        self.normal_rect = None
        self.geometry_job = None
        self.resize_data = None
        self.resize_handles = {}
        self.resize_specs = {}
        self.sidebar_rows = {}
        self.active_chat_id = None
        self.chat_loading = False
        self.load_token = 0
        self.deferred_entries = []
        self.history_entries = []
        self.history_start = 0
        self.loading_older = False
        self.chat_scroll_job = None
        self.chat_scroll_target = None
        self.older_load_job = None
        self.last_chat_create = 0.0
        self.last_chat_switch = 0.0
        self.last_chat_delete = 0.0
        self.pending_pastes = []
        self.paste_chip_widgets = []
        self.paste_columns = None
        self.draft_job = None
        self.drafts = {
            chat_id: draft
            for chat_id, draft in load_drafts().items()
            if self.chat_store.get_chat(chat_id) is not None
        }
        self.name_lock = threading.Lock()
        self.cleanup_lock = threading.Lock()
        self.cleanup_running = False
        self.shutdown_done = False
        self._chat_images = []
        self._emoji_images = []
        self._emoji_cache = {}
        self._emoji_failed = set()
        self._emoji_pending = {}
        self._emoji_loading = set()
        self._emoji_network = True

        self.build_ui()
        self.apply_window_settings()
        self.apply_chat_font()
        self.apply_theme(
            get_theme(
                self.theme_name,
                self.theme_accent,
            )
        )

        self.build_resize_handles()
        self.apply_saved_window()
        self.init_chats()
        self.root.bind("<Configure>", self.on_root_configure, add="+")
        self.root.bind("<Destroy>", self.on_root_destroy, add="+")
        self.root.after(1500, self.keep_handles_on_top)

        if self.api_key:
            self.start_server_cleanup()

        if self.mic_muted:
            self.set_mic(True)

        if not self.api_key:
            self.mic_muted = True
            self.root.withdraw()

            self.root.after(
                100,
                self.show_api_key_window,
            )

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<Map>", self.on_root_map)
        self.root.after(300, self.create_taskbar_icon)
        self.root.after(5000, self.watch_taskbar_icon)

        threading.Thread(
            target=self.load_audio_systems,
            daemon=True,
        ).start()

        threading.Thread(
            target=self.message_pump,
            daemon=True,
        ).start()

    def shutdown_cleanup(self):
        if self.shutdown_done:
            return

        self.shutdown_done = True

        try:
            self.store_draft(self.active_chat_id)
        except Exception:
            pass

        try:
            self.persist_drafts()
        except Exception:
            pass

        try:
            self.save_window_now()
        except Exception:
            pass

        try:
            self.chat_store.flush()
        except Exception:
            pass

        pending = self.chat_store.pending_items()

        if not pending or not self.api_key:
            return

        finished = threading.Event()

        def run():
            try:
                for item in pending:
                    if self._server_clear(item):
                        self.chat_store.remove_pending(item)
            finally:
                finished.set()

        threading.Thread(target=run, daemon=True).start()
        finished.wait(4)

    def on_root_destroy(self, event):
        if event.widget is not self.root:
            return

        self.running = False
        self.shutdown_cleanup()

    def toggle_screenshot(self):
        now = time.time()

        if (
            now - getattr(
                self,
                "last_image_select_time",
                0.0,
            )
            < 2.0
        ):
            return

        self.last_image_select_time = now

        if getattr(
            self,
            "attached_image_path",
            None,
        ):
            self.reset_screenshot_button()

            self.screenshot_status_until = (
                time.time() + 3.0
            )

            self.messages.put(
                (
                    "state",
                    "Screenshot removed.",
                )
            )

            return

        self.upload_screenshot()

    def upload_screenshot(self):
        if getattr(
            self,
            "attached_image_path",
            None,
        ):
            return

        path = filedialog.askopenfilename(
            title="Select screenshot",
            filetypes=[
                (
                    "Images",
                    "*.png *.jpg *.jpeg",
                ),
                (
                    "PNG files",
                    "*.png",
                ),
                (
                    "JPEG files",
                    "*.jpg *.jpeg",
                ),
            ],
        )

        if not path:
            return

        self.attached_image_path = path

        self.upload_button.configure(
            text="×",
            fg="#FFD9DD",
            bg="#351B20",
            activeforeground="#FFFFFF",
            activebackground="#472229",
            highlightbackground="#593038",
            highlightcolor="#FF6B78",
        )
        
        self.screenshot_status_until = (
            time.time() + 3.0
        )

        self.messages.put(
            (
                "state",
                (
                    f"Screenshot ready: "
                    f"{os.path.basename(path)}"
                ),
            )
        )

    def build_ui(self):
        self.titlebar = tk.Frame(
            self.root,
            bg="#0D1713",
            height=42,
        )
        self.titlebar.pack(fill="x", side="top")
        self.titlebar.pack_propagate(False)

        self.titlebar.bind(
            "<ButtonPress-1>",
            self.start_drag,
        )
        self.titlebar.bind(
            "<B1-Motion>",
            self.drag_window,
        )

        icon = tk.Label(
            self.titlebar,
            text="⌬",
            fg="#5CFF9D",
            bg="#0D1713",
            font=("Segoe UI Symbol", 15, "bold"),
        )
        icon.pack(side="left", padx=(13, 7))
        icon.bind("<ButtonPress-1>", self.start_drag)
        icon.bind("<B1-Motion>", self.drag_window)

        title = tk.Label(
            self.titlebar,
            text="Zanel",
            fg="#f2f6ff",
            bg="#0D1713",
            font=("Segoe UI", 11, "bold"),
        )
        title.pack(side="left")
        title.bind("<ButtonPress-1>", self.start_drag)
        title.bind("<B1-Motion>", self.drag_window)

        self.titlebar_pixel = tk.PhotoImage(
            width=1,
            height=1,
        )

        close_button = tk.Button(
            self.titlebar,
            text="×",
            command=self.close,
            image=self.titlebar_pixel,
            compound="center",
            width=38,
            height=42,
            fg="#b9c2d0",
            bg="#0D1713",
            activeforeground="white",
            activebackground="#c43f52",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=("Segoe UI Symbol", 13),
            cursor="hand2",
        )
        close_button.pack(
            side="right",
            fill="y",
        )

        minimize = tk.Button(
            self.titlebar,
            text="—",
            command=self.minimize_window,
            image=self.titlebar_pixel,
            compound="center",
            width=38,
            height=42,
            fg="#b9c2d0",
            bg="#0D1713",
            activeforeground="white",
            activebackground="#ffa500",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=("Segoe UI Symbol", 13),
            cursor="hand2",
        )
        minimize.pack(
            side="right",
            fill="y",
        )

        settings_button = tk.Button(
            self.titlebar,
            text="⚙",
            command=self.open_settings,
            image=self.titlebar_pixel,
            compound="center",
            width=38,
            height=42,
            fg="#b9c2d0",
            bg="#0D1713",
            activeforeground="white",
            activebackground="#2d405c",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=("Segoe UI Symbol", 13),
            cursor="hand2",
        )
        settings_button.pack(
            side="right",
            fill="y",
        )

        info_button = tk.Button(
            self.titlebar,
            text="ⓘ",
            command=self.show_disclaimer,
            image=self.titlebar_pixel,
            compound="center",
            width=38,
            height=42,
            fg="#b9c2d0",
            bg="#0D1713",
            activeforeground="white",
            activebackground="#2d405c",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=("Segoe UI Symbol", 13),
            cursor="hand2",
        )
        info_button.pack(
            side="right",
            fill="y",
        )

        self.state = tk.Label(
            self.titlebar,
            text="Starting…",
            fg="#8290a8",
            bg="#0D1713",
            font=("Segoe UI", 8),
        )
        self.state.pack(
            side="right",
            padx=(8, 6),
        )

        self.skip_hover = False
        self.skip_phase = 0
        self.skip_pulse_job = None

        pulse_start = (0x24, 0x5A, 0x41)
        pulse_end = (0x5C, 0xFF, 0x9D)
        pulse_steps = 10

        pulse_forward = [
            "#%02x%02x%02x" % tuple(
                int(
                    pulse_start[channel]
                    + (pulse_end[channel] - pulse_start[channel])
                    * step
                    / pulse_steps
                )
                for channel in range(3)
            )
            for step in range(pulse_steps + 1)
        ]

        self.skip_pulse_colors = tuple(
            pulse_forward + pulse_forward[-2:0:-1]
        )

        self.skip_button = tk.Frame(
            self.titlebar,
            bg=self.skip_pulse_colors[0],
            highlightthickness=0,
            bd=0,
        )

        self.skip_inner = tk.Button(
            self.skip_button,
            text="⏭  Skip TTS",
            command=self.skip_tts,
            fg="#5CFF9D",
            bg="#0F1A15",
            activeforeground="#071019",
            activebackground="#3FD07F",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            padx=9,
            pady=2,
            cursor="hand2",
            font=("Segoe UI Symbol", 8, "bold"),
        )

        self.skip_inner.pack(
            padx=1,
            pady=1,
        )

        self.skip_inner.bind(
            "<Enter>",
            self.skip_hover_enter,
        )

        self.skip_inner.bind(
            "<Leave>",
            self.skip_hover_leave,
        )

        body = tk.Frame(
            self.root,
            bg="#0B0E14",
        )

        body.pack(
            fill="both",
            expand=True,
        )

        self.rail = tk.Frame(
            body,
            bg="#0D1713",
            width=RAIL_WIDTH,
        )
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)

        self.sidebar_toggle = tk.Button(
            self.rail,
            text="›",
            command=self.toggle_sidebar,
            fg="#B9C2D0",
            bg="#0D1713",
            activeforeground="white",
            activebackground="#1A2520",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            padx=0,
            pady=0,
            cursor="hand2",
            font=("Segoe UI Symbol", 12, "bold"),
        )
        self.sidebar_toggle.pack(side="top", fill="x", pady=(10, 0), ipady=4)

        self.sidebar = tk.Frame(
            body,
            bg="#101713",
            width=SIDEBAR_WIDTH,
        )
        self.sidebar.pack_propagate(False)

        side_head = tk.Frame(self.sidebar, bg="#101713")
        side_head.pack(fill="x", padx=14, pady=(14, 8))

        tk.Label(
            side_head,
            text="Chats",
            fg="#F2F6FF",
            bg="#101713",
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        self.sidebar_count = tk.Label(
            side_head,
            text=f"0/{MAX_CHATS}",
            fg="#8290A8",
            bg="#101713",
            font=("Segoe UI", 8),
        )
        self.sidebar_count.pack(side="right")

        self.new_chat_button = tk.Button(
            self.sidebar,
            text="+  New chat",
            command=lambda: self.new_chat(False),
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            borderwidth=0,
            relief="flat",
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        self.new_chat_button.pack(fill="x", padx=12)

        self.anon_chat_button = tk.Button(
            self.sidebar,
            text="◌  Anonymous chat",
            command=lambda: self.new_chat(True),
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            pady=8,
            cursor="hand2",
            font=("Segoe UI Symbol", 9, "bold"),
        )
        self.anon_chat_button.pack(fill="x", padx=12, pady=(6, 0))

        tk.Frame(
            self.sidebar,
            bg="#293830",
            height=1,
        ).pack(fill="x", padx=12, pady=(12, 6))

        list_holder = tk.Frame(self.sidebar, bg="#101713")
        list_holder.pack(fill="both", expand=True, padx=(6, 4), pady=(0, 8))

        self.chat_canvas = tk.Canvas(
            list_holder,
            bg="#101713",
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.chat_canvas.pack(fill="both", expand=True)

        self.chat_list = tk.Frame(self.chat_canvas, bg="#101713")
        self.chat_list_window = self.chat_canvas.create_window(
            (0, 0),
            window=self.chat_list,
            anchor="nw",
        )

        def sync_scroll(_event=None):
            try:
                self.chat_canvas.configure(
                    scrollregion=self.chat_canvas.bbox("all") or (0, 0, 0, 0)
                )
            except tk.TclError:
                pass

        def sync_width(event):
            try:
                self.chat_canvas.itemconfigure(
                    self.chat_list_window,
                    width=max(1, event.width),
                )
            except tk.TclError:
                pass

        self.chat_list.bind("<Configure>", sync_scroll)
        self.chat_canvas.bind("<Configure>", sync_width)

        self.content = tk.Frame(body, bg="#0B0E14")
        self.content.pack(side="left", fill="both", expand=True)

        controls = tk.Frame(self.content, bg="#0B0E14")
        controls.pack(side="bottom", fill="x", padx=12, pady=(0, 12))

        top_row = tk.Frame(controls, bg="#0B0E14")
        top_row.pack(side="top", fill="x")

        tool_row = tk.Frame(controls, bg="#0B0E14")
        tool_row.pack(side="top", fill="x", pady=(8, 0))

        self.send_button = tk.Button(
            top_row,
            text="Send",
            command=self.send_manual,
            fg="#071019",
            bg="#5CFF9D",
            activeforeground="#071019",
            activebackground="#72FFAB",
            borderwidth=0,
            relief="flat",
            padx=20,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            highlightthickness=0,
        )
        self.send_button.pack(side="right", padx=(8, 0), fill="y")

        self.upload_button = tk.Button(
            top_row,
            text="+",
            command=self.toggle_screenshot,
            fg="#C8D8D0",
            bg="#17211D",
            activeforeground="#FFFFFF",
            activebackground="#22312A",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 11, "bold"),
            highlightthickness=1,
            highlightbackground="#293830",
            highlightcolor="#5CFF9D",
        )
        self.upload_button.pack(side="right", padx=(8, 0), fill="y")

        entry_wrap = tk.Frame(
            top_row,
            bg="#121A16",
            highlightthickness=1,
            highlightbackground="#293830",
            highlightcolor="#5CFF9D",
        )
        entry_wrap.pack(side="left", fill="x", expand=True)

        self.manual = tk.Entry(
            entry_wrap,
            bg="#121A16",
            fg="#E8F5ED",
            insertbackground="white",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self.manual.pack(fill="x", padx=12, pady=9)

        self.manual.bind("<<Paste>>", self.on_paste)
        self.manual.insert(0, INPUT_PLACEHOLDER)
        self.manual.configure(fg="#6F7A74")

        def focus_in(_event=None):
            if self.manual.get() == INPUT_PLACEHOLDER:
                self.manual.delete(0, tk.END)
                self.manual.configure(fg="#E8F5ED")

            entry_wrap.configure(highlightbackground=self.theme["accent"])

        def focus_out(_event=None):
            if not self.manual.get().strip():
                self.manual.delete(0, tk.END)
                self.manual.insert(0, INPUT_PLACEHOLDER)
                self.manual.configure(fg="#6F7A74")

            entry_wrap.configure(highlightbackground=self.theme["border"])

        self.manual.bind("<FocusIn>", focus_in)
        self.manual.bind("<FocusOut>", focus_out)
        self.manual.bind("<Return>", lambda _event: self.send_manual())
        self.manual.bind("<KeyRelease>", self.on_draft_key)

        self.attachment_label = tk.Label(
            tool_row,
            text="",
            fg="#5CFF9D",
            bg="#0B0E14",
            font=("Segoe UI", 8),
        )

        self.mic_button = tk.Button(
            tool_row,
            text="●  Mic ON",
            command=self.toggle_mic,
            fg="#DDF8E8",
            bg="#17241D",
            activeforeground="white",
            activebackground="#013220",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        self.mic_button.pack(side="left")

        clear_button = tk.Button(
            tool_row,
            text="Clear",
            command=self.clear_chat,
            fg="#DDF8E8",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#c43f52",
            borderwidth=0,
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        clear_button.pack(side="left", padx=(8, 0))

        tk.Label(
            tool_row,
            text="Enter to send",
            fg="#56677A",
            bg="#0B0E14",
            font=("Segoe UI", 8),
        ).pack(side="right")

        self.paste_bar = tk.Frame(
            self.content,
            bg="#1A2520",
            highlightthickness=1,
            highlightbackground="#293830",
        )

        paste_head = tk.Frame(self.paste_bar, bg="#1A2520")
        paste_head.pack(fill="x")

        self.paste_summary = tk.Label(
            paste_head,
            text="",
            fg="#5CFF9D",
            bg="#1A2520",
            anchor="w",
            padx=10,
            pady=5,
            font=("Segoe UI", 8, "bold"),
        )
        self.paste_summary.pack(side="left", fill="x", expand=True)

        tk.Button(
            paste_head,
            text="Clear all",
            command=self.clear_pending_paste,
            fg="#B9C2D0",
            bg="#1A2520",
            activeforeground="white",
            activebackground="#c43f52",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right", fill="y")

        self.paste_chips = tk.Frame(self.paste_bar, bg="#1A2520")
        self.paste_chips.pack(fill="x", padx=6, pady=(0, 4))
        self.paste_chips.bind("<Configure>", self.layout_paste_chips)

        self.chat_holder = tk.Frame(
            self.content,
            bg="#0B0E14",
        )
        self.chat_holder.pack(
            side="top",
            fill="both",
            expand=True,
            padx=12,
            pady=(12, 10),
        )

        self.chat = tk.Text(
            self.chat_holder,
            height=1,
            width=1,
            wrap="word",
            state="disabled",
            bg="#101713",
            fg="#E8F5ED",
            insertbackground="white",
            selectbackground="#2d405c",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=("Segoe UI", 10),
            yscrollcommand=self.on_chat_yscroll,
        )

        self.chat.tag_configure(
            "bold",
            font=("Segoe UI", 10, "bold"),
        )

        self.chat.tag_configure(
            "italic",
            font=("Segoe UI", 10, "italic"),
        )
        self.chat.bind(
            "<MouseWheel>",
            self.on_chat_mousewheel,
            add="+",
        )

        self.chat.pack(
            side="left",
            fill="both",
            expand=True,
        )

        self.chat_scrollbar = ThemedScrollbar(
            self.chat_holder,
            orient="vertical",
            command=self.scroll_chat,
            bg=self.theme["track"],
            track=self.theme["panel"],
            thumb=self.theme["accent"],
            width=6,
        )
        self.chat_scrollbar.pack(
            side="right",
            fill="y",
        )

        self.chat_latest_button = tk.Frame(
            self.chat_holder,
            bg=self.theme["track"],
            highlightthickness=0,
        )

        self.chat_latest_pill = tk.Frame(
            self.chat_latest_button,
            bg=self.theme["panel"],
            highlightthickness=1,
            highlightbackground=self.theme["accent"],
            highlightcolor=self.theme["accent"],
        )
        self.chat_latest_pill.pack(
            fill="both",
            expand=True,
            padx=(0, 3),
            pady=(0, 3),
        )

        self.chat_latest_label = tk.Label(
            self.chat_latest_pill,
            text="↓  Latest",
            fg=self.theme["accent"],
            bg=self.theme["panel"],
            padx=12,
            pady=5,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        self.chat_latest_label.pack(fill="both", expand=True)
        self.chat_latest_label.bind(
            "<ButtonRelease-1>",
            lambda _event: self.scroll_chat_to_bottom(),
            add="+",
        )
        self.chat_latest_label.bind(
            "<Enter>",
            lambda _event: self.set_chat_latest_hover(True),
            add="+",
        )
        self.chat_latest_label.bind(
            "<Leave>",
            lambda _event: self.set_chat_latest_hover(False),
            add="+",
        )
        self.chat_latest_button.place(
            relx=0.5,
            rely=1.0,
            y=-14,
            anchor="s",
        )
        self.chat_latest_button.place_forget()

        self.older_loading_label = tk.Label(
            self.chat_holder,
            text="Loading earlier messages…",
            fg="#DDF8E8",
            bg="#1A2520",
            padx=10,
            pady=5,
            font=("Segoe UI", 8, "bold"),
        )
        self.older_loading_label.place(
            relx=0.5,
            y=10,
            anchor="n",
        )
        self.older_loading_label.place_forget()

        self.loading_label = tk.Label(
            self.content,
            text="Loading chat…",
            fg="#8290A8",
            bg="#101713",
            font=("Segoe UI", 10, "bold"),
        )

        self.root.bind_all("<MouseWheel>", self.on_global_wheel, add="+")

    def close(self, force=False):
        if self.confirm_close and self.running and not force:
            self.preempt_info_confirmation()
            self.confirm(
                "Close Zanel",
                "Are you sure you want to close Zanel?",
                lambda ok: self.close(force=True) if ok else None,
                yes_text="Close",
                no_text="Stay",
                danger=True,
                dedupe=True,
                priority=True,
            )
            return

        if getattr(self, "closed", False):
            return

        self.closed = True
        self.stop_rickroll()
        self.running = False
        self.mic_muted = True

        try:
            self.root.withdraw()
        except tk.TclError:
            pass

        self.shutdown_cleanup()

        try:
            self.cleanup_music_file()
        except Exception:
            pass

        try:
            sd.stop()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    @property
    def ai_busy(self):
        return self.active_chat_id in self.busy_chats

    def reset_screenshot_button(self):
        self.attached_image_path = None

        self.upload_button.configure(
            text="+",
            fg="#C8D8D0",
            bg=self.theme["upload"],
            activeforeground="#FFFFFF",
            activebackground=self.theme["button_hover"],
            highlightbackground=self.theme["border"],
            highlightcolor=self.theme["accent"],
        )

    def run(self):
        self.root.mainloop()
