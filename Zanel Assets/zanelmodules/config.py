import tempfile
import getpass
import re
from pathlib import Path
import platform


AI_URL = "https://evil-poppy-hardiness.ngrok-free.dev/chat"

TRANSCRIBE_URL = "https://evil-poppy-hardiness.ngrok-free.dev/transcribe"

TTS_URL = "https://evil-poppy-hardiness.ngrok-free.dev/tts"

TTS_FORMAT = "wav"

DEFAULT_TTS_VOICE = "en_GB-alan-medium"

TTS_VOICES = [
    "en_GB-alan-medium",
    "en_GB-alba-medium",
    "en_GB-cori-high",
    "en_GB-cori-medium",
    "en_GB-jenny_dioco-medium",
    "en_GB-northern_english_male-medium",
    "en_US-amy-medium",
    "en_US-bryce-medium",
    "en_US-danny-low",
    "en_US-joe-medium",
    "en_US-john-medium",
    "en_US-kristin-medium",
    "en_US-lessac-high",
    "en_US-lessac-medium",
    "en_US-miles-medium",
    "en_US-mike-medium",
    "en_US-norman-medium",
    "en_US-ryan-high",
    "en_US-sam-medium",
]

ZANEL_VERSION = "1.37"

IS_MODIFIED = False

GITHUB_LATEST_RELEASE_API = (
    "https://api.github.com/repos/"
    "lameman12/Zanel-AI-Assistant/releases/latest"
)

GITHUB_RELEASES_URL = "https://github.com/lameman12/Zanel-AI-Assistant/releases"

OFFICIAL_WEBSITE_URL = "https://zanel-assistant.pages.dev/"

APP_DATA_DIR = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "ZanelDATA00"
)

API_KEY_FILE = (
    APP_DATA_DIR
    / "api_key.txt"
)

SETTINGS_FILE = (
    APP_DATA_DIR
    / "settings.json"
)

WINDOW_FILE = APP_DATA_DIR / "window.json"

DRAFTS_FILE = APP_DATA_DIR / "drafts.json"

DEFAULT_WINDOW_WIDTH = 560

DEFAULT_WINDOW_HEIGHT = 480

MIN_WINDOW_WIDTH = 380

MIN_WINDOW_HEIGHT = 320

SIDEBAR_WIDTH = 215

RAIL_WIDTH = 18

MAX_CHATS = 10

CHAT_CREATE_COOLDOWN = 4.0

CHAT_SWITCH_COOLDOWN = 1.2

CHAT_DELETE_COOLDOWN = 1.5

HISTORY_INITIAL = 40

HISTORY_PAGE = 30

HISTORY_BATCH = 8

RECENT_IMAGE_LIMIT = 6

MAX_STORED_MESSAGES = 2000

PASTE_THRESHOLD_CHARS = 300

PASTE_THRESHOLD_LINES = 5

PASTE_MAX_CHARS = 6000

MAX_PASTES = 8

MAX_SERVER_MESSAGE_CHARS = 6500

VIEWER_CHUNK_CHARS = 6000

LONG_REPLY_CHARS = 700

LONG_REPLY_LINES = 14

LONG_REPLY_MAX_CHARS = 60000

PREVIEW_CHARS = 240

INPUT_PLACEHOLDER = "Ask Zanel anything"

DEFAULT_CHAT_NAME = "New chat"

ANON_CHAT_NAME = "Anonymous chat"

MESSAGES_CLEAR_URL = "https://evil-poppy-hardiness.ngrok-free.dev/messages/clear"

ANON_ID = "Un--set404"

RENAME_MAX_CHARS = 32

RENAME_COOLDOWN = 5.0

SEND_COOLDOWN = 4.0

HEX_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")

CHAT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

USER_ID = getpass.getuser()

PLATFORM = platform.system()

BOT_NAME = "Zanel"

MUSIC_URLS = {
    "chill-bossa-nova": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Chill-bossa-nova.mp3",
    "chill": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Chill-bossa-nova.mp3",
    "bossa-nova": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Chill-bossa-nova.mp3",
    "chill-nova": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Chill-bossa-nova.mp3",
    "lo-fi": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Lo-fi.mp3",
    "study-music": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Lo-fi.mp3",
    "soft-techno": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Soft-techno.mp3",
    "techno-soft": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/Soft-techno.mp3",
    "dance": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/electronic-dance.mp3",
    "electronic-dance": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/electronic-dance.mp3",
    "dance-electro": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/electronic-dance.mp3",
    "groove-electronic": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/GrooveElectronic.mp3",
    "groove-electro": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/GrooveElectronic.mp3",
    "electro-groove": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/GrooveElectronic.mp3",
    "electronic-groove": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/GrooveElectronic.mp3",
    "groovy-hip-hop": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/groovy-hip-hop.mp3",
    "hip-hop": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/groovy-hip-hop.mp3",
    "hip-hop-groovy": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/groovy-hip-hop.mp3",
    "groove-hip-hop": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/groovy-hip-hop.mp3",
    "electro-dance": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/electronic-dance.mp3",
    "soft-jazz": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/soft-jazz.mp3",
    "jazz": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/soft-jazz.mp3",
    "jazz-soft": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/soft-jazz.mp3",
    "8-bit": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/8-bit-chiptune.mp3",
    "eight-bit": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/8-bit-chiptune.mp3",
    "eight-bit-chiptune": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/8-bit-chiptune.mp3",
    "8-bit-chiptune": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/8-bit-chiptune.mp3",
    "chiptune": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/8-bit-chiptune.mp3",
    "dance-electronic": "https://github.com/lameman12/Zanel-AI-Assistant/raw/refs/heads/main/Music/electronic-dance.mp3",
}

MUSIC_TEMP_DIR = (
    Path(tempfile.gettempdir())
    / "ZanelMusic"
)

SAMPLE_RATE = 16000

CHANNELS = 1

BLOCK_SECONDS = 0.1

ENERGY_THRESHOLD = 0.005

START_SPEECH_BLOCKS = 2

SILENCE_BLOCKS_TO_STOP = 8

PRE_ROLL_BLOCKS = 4

MAX_RECORD_SECONDS = 30

MAX_IDLE_SECONDS = 30

TARGET_PEAK = 0.7

MAX_GAIN = 10.0

DEFAULT_OPACITY = 0.96

MIN_OPACITY = 0.5

FONT_SIZES = (9, 10, 11, 12, 13, 14)

DEFAULT_FONT_SIZE = 10

MIC_SENSITIVITY_LEVELS = {
    "low": 0.010,
    "medium": 0.005,
    "high": 0.0025,
}

DEFAULT_MIC_SENSITIVITY = "medium"

DEFAULT_THEME_NAME = "Emerald"

DEFAULT_THEME_ACCENT = "#5CFF9D"

DEFAULT_THEME = {
    "bg": "#0B0E14",
    "title": "#0D1713",
    "panel": "#101713",
    "field": "#121A16",
    "button": "#1A2520",
    "button_hover": "#22312A",
    "mic": "#17241D",
    "upload": "#17211D",
    "mic_press": "#013220",
    "skip": "#0F1A15",
    "border": "#293830",
    "track": "#24332B",
    "glow": "#2F8F63",
    "accent": "#5CFF9D",
    "accent_hover": "#72FFAB",
    "accent_press": "#3FD07F",
}

THEME_PRESETS = {
    "Emerald": "#5CFF9D",
    "Ocean": "#4DA3FF",
    "Violet": "#A66CFF",
    "Rose": "#FF5C8A",
    "Amber": "#FFB347",
    "Cyan": "#3FE0E0",
    "Crimson": "#FF4D4D",
    "Slate": "#B0B8C4",
}

THEME_WIDGET_OPTIONS = (
    "bg",
    "fg",
    "activebackground",
    "activeforeground",
    "highlightbackground",
    "highlightcolor",
    "selectcolor",
    "selectbackground",
    "selectforeground",
    "insertbackground",
    "disabledforeground",
    "troughcolor",
)

ALLOW_SHELL_COMMANDS = True

MAX_ACTIONS_PER_MESSAGE = 8

WINGET_ALREADY_INSTALLED = 0x8A150061

SKIP_DIRECTORIES = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "windows.old",
    "program files",
    "program files (x86)",
    "programdata",
    "windowsapps",
    "appdata",
    "node_modules",
    ".git",
    "__pycache__",
}

PROTECTED_PROGRAM_FOLDERS = {
    "windowsapps",
    "common files",
    "windows defender",
    "windows nt",
    "windows mail",
    "windows media player",
    "windows photo viewer",
    "windowspowershell",
    "microsoft",
    "internet explorer",
    "modifiablewindowsapps",
    "msbuild",
    "reference assemblies",
    "dotnet",
}
