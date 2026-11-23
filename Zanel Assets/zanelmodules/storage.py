import json
import os
import shutil
import threading
import time
import hashlib
from pathlib import Path
from PIL import Image, ImageTk
import platform
from zanelmodules.config import (
    ANON_CHAT_NAME,
    ANON_ID,
    APP_DATA_DIR,
    CHAT_ID_PATTERN,
    DEFAULT_CHAT_NAME,
    DEFAULT_FONT_SIZE,
    DEFAULT_MIC_SENSITIVITY,
    DEFAULT_OPACITY,
    DEFAULT_THEME_ACCENT,
    DEFAULT_THEME_NAME,
    DEFAULT_TTS_VOICE,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    DRAFTS_FILE,
    FONT_SIZES,
    HEX_ID_PATTERN,
    MAX_CHATS,
    MAX_PASTES,
    MAX_SERVER_MESSAGE_CHARS,
    MAX_STORED_MESSAGES,
    MIC_SENSITIVITY_LEVELS,
    MIN_OPACITY,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    SETTINGS_FILE,
    THEME_PRESETS,
    TTS_VOICES,
    WINDOW_FILE,
)
from zanelmodules.theme import normalize_hex


def new_hash():
    return hashlib.sha256(os.urandom(32)).hexdigest()


def new_chat_id():
    return os.urandom(16).hex()


def make_entry(who, text, paste=None, image=None, pastes=None, turn_id=None):
    entry = {
        "who": str(who)[:40],
        "text": str(text),
        "paste": paste or None,
        "pastes": list(pastes) if pastes else None,
        "image": image or None,
        "time": time.time(),
    }

    if isinstance(turn_id, str) and turn_id:
        entry["turn_id"] = turn_id

    return entry


def load_window_state():
    state = {
        "width": DEFAULT_WINDOW_WIDTH,
        "height": DEFAULT_WINDOW_HEIGHT,
        "x": None,
        "y": None,
        "maximized": False,
        "sidebar_open": False,
    }

    try:
        if WINDOW_FILE.is_file():
            data = json.loads(WINDOW_FILE.read_text(encoding="utf-8"))

            if isinstance(data, dict):
                for key, low in (
                    ("width", MIN_WINDOW_WIDTH),
                    ("height", MIN_WINDOW_HEIGHT),
                ):
                    value = data.get(key)

                    if (
                        isinstance(value, int)
                        and not isinstance(value, bool)
                        and low <= value <= 10000
                    ):
                        state[key] = value

                for key in ("x", "y"):
                    value = data.get(key)

                    if (
                        isinstance(value, int)
                        and not isinstance(value, bool)
                        and -10000 <= value <= 20000
                    ):
                        state[key] = value

                state["maximized"] = bool(data.get("maximized", False))
                state["sidebar_open"] = bool(data.get("sidebar_open", False))

    except Exception:
        pass

    return state


def save_window_state(state):
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp = WINDOW_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temp, WINDOW_FILE)
        return True
    except Exception:
        return False


def load_drafts():
    drafts = {}

    try:
        if DRAFTS_FILE.is_file():
            data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))

            if isinstance(data, dict):
                for chat_id, item in data.items():
                    if (
                        not CHAT_ID_PATTERN.match(str(chat_id))
                        or not isinstance(item, dict)
                    ):
                        continue

                    text = item.get("text")
                    text = text if isinstance(text, str) else ""
                    raw = item.get("pastes")
                    raw = raw if isinstance(raw, list) else []

                    pastes = [
                        value
                        for value in raw
                        if isinstance(value, str) and value.strip()
                    ][:MAX_PASTES]

                    if text.strip() or pastes:
                        drafts[str(chat_id)] = {
                            "text": text[:MAX_SERVER_MESSAGE_CHARS],
                            "pastes": pastes,
                        }
    except Exception:
        pass

    return drafts


def save_drafts(drafts):
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp = DRAFTS_FILE.with_suffix(".tmp")
        temp.write_text(
            json.dumps(drafts, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temp, DRAFTS_FILE)
        return True
    except Exception:
        return False


class ChatStore:
    def __init__(self, base_dir):
        self.base = Path(base_dir)
        self.dir = self.base / "chats"
        self.images_dir = self.base / "chat_images"
        self.index_file = self.dir / "index.json"
        self.pending_file = self.dir / "pending_clear.json"
        self.lock = threading.RLock()
        self.chats = {}
        self.anon = {}
        self.anon_messages = {}
        self.pending = []
        self.last_active = None
        self.dirty = False
        self._load()

    @staticmethod
    def _read_json(path, default):
        try:
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass

        return default

    @staticmethod
    def _write_json(path, data):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            os.replace(temp, path)
            return True
        except Exception:
            return False

    @staticmethod
    def _clean_meta(chat_id, meta):
        if not CHAT_ID_PATTERN.match(str(chat_id)) or not isinstance(meta, dict):
            return None

        user_id = str(meta.get("user_id", ""))
        platform = str(meta.get("platform", ""))

        if not HEX_ID_PATTERN.match(user_id) or not HEX_ID_PATTERN.match(platform):
            return None

        now = time.time()

        def number(value, default):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)

            return default

        name = " ".join(
            str(meta.get("name") or DEFAULT_CHAT_NAME).split()
        )[:60] or DEFAULT_CHAT_NAME

        return {
            "id": chat_id,
            "name": name,
            "created": number(meta.get("created"), now),
            "updated": number(meta.get("updated"), now),
            "user_id": user_id,
            "platform": platform,
            "named": bool(meta.get("named", False)),
            "anonymous": False,
            "server_used": bool(meta.get("server_used", False)),
        }

    @staticmethod
    def _normalize_entry(item):
        if not isinstance(item, dict):
            return None

        who = item.get("who")
        text = item.get("text")

        if not isinstance(who, str) or not who or not isinstance(text, str):
            return None

        paste = item.get("paste")
        image = item.get("image")
        stamp = item.get("time")
        pastes = item.get("pastes")

        if isinstance(pastes, list):
            pastes = [
                value
                for value in pastes
                if isinstance(value, str) and value
            ][:MAX_PASTES]
        else:
            pastes = None

        entry = {
            "who": who[:40],
            "text": text,
            "paste": paste if isinstance(paste, str) and paste else None,
            "pastes": pastes or None,
            "image": image if isinstance(image, str) and image else None,
            "time": float(stamp)
            if isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
            else time.time(),
        }

        turn_id = item.get("turn_id")
        if isinstance(turn_id, str) and turn_id.isalnum() and len(turn_id) <= 64:
            entry["turn_id"] = turn_id

        return entry

    def _chat_file(self, chat_id):
        return self.dir / f"{chat_id}.jsonl"

    def _load(self):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        data = self._read_json(self.index_file, {})

        if not isinstance(data, dict):
            data = {}

        raw = data.get("chats", {})

        if isinstance(raw, dict):
            for chat_id, meta in raw.items():
                cleaned = self._clean_meta(chat_id, meta)

                if cleaned and len(self.chats) < MAX_CHATS:
                    self.chats[chat_id] = cleaned

        last = data.get("last_active")

        if isinstance(last, str) and last in self.chats:
            self.last_active = last

        pending = self._read_json(self.pending_file, [])

        if isinstance(pending, list):
            for item in pending:
                if (
                    isinstance(item, dict)
                    and HEX_ID_PATTERN.match(str(item.get("user_id", "")))
                    and HEX_ID_PATTERN.match(str(item.get("platform", "")))
                ):
                    entry = {
                        "user_id": str(item["user_id"]),
                        "platform": str(item["platform"]),
                    }

                    if entry not in self.pending:
                        self.pending.append(entry)

        self._remove_orphans()

    def _remove_orphans(self):
        try:
            for path in self.dir.glob("*.jsonl"):
                if path.stem not in self.chats:
                    path.unlink()
        except OSError:
            pass

        try:
            if self.images_dir.is_dir():
                for sub in self.images_dir.iterdir():
                    if sub.is_dir() and sub.name not in self.chats:
                        shutil.rmtree(sub, ignore_errors=True)
        except OSError:
            pass

    def _save_index(self):
        self._write_json(
            self.index_file,
            {
                "version": 1,
                "last_active": self.last_active,
                "chats": self.chats,
            },
        )
        self.dirty = False

    def _add_pending_locked(self, meta):
        item = {
            "user_id": meta["user_id"],
            "platform": meta["platform"],
        }

        if item not in self.pending:
            self.pending.append(item)
            self._write_json(self.pending_file, self.pending)

    def flush(self):
        with self.lock:
            if self.dirty:
                self._save_index()

    def count(self):
        with self.lock:
            return len(self.chats) + len(self.anon)

    def list_chats(self):
        with self.lock:
            items = [dict(meta) for meta in self.chats.values()]
            items.extend(dict(meta) for meta in self.anon.values())

        items.sort(key=lambda meta: meta["created"], reverse=True)
        return items

    def get_chat(self, chat_id):
        with self.lock:
            meta = self.chats.get(chat_id) or self.anon.get(chat_id)
            return dict(meta) if meta else None

    def create(self, anonymous=False):
        with self.lock:
            if len(self.chats) + len(self.anon) >= MAX_CHATS:
                return None

            if anonymous and self.anon:
                return None

            chat_id = new_chat_id()

            while chat_id in self.chats or chat_id in self.anon:
                chat_id = new_chat_id()

            now = time.time()

            meta = {
                "id": chat_id,
                "name": ANON_CHAT_NAME if anonymous else DEFAULT_CHAT_NAME,
                "created": now,
                "updated": now,
                "user_id": ANON_ID if anonymous else new_hash(),
                "platform": ANON_ID if anonymous else new_hash(),
                "named": bool(anonymous),
                "anonymous": bool(anonymous),
                "server_used": False,
            }

            if anonymous:
                self.anon[chat_id] = meta
                self.anon_messages[chat_id] = []
            else:
                self.chats[chat_id] = meta
                self._save_index()

            return dict(meta)

    def anonymous_id(self):
        with self.lock:
            for chat_id in self.anon:
                return chat_id

            return None

    def has_messages(self, chat_id):
        with self.lock:
            if chat_id in self.anon:
                return bool(self.anon_messages.get(chat_id))

            if chat_id not in self.chats:
                return False

            try:
                path = self._chat_file(chat_id)
                return path.is_file() and path.stat().st_size > 0
            except OSError:
                return False

    def messages(self, chat_id):
        with self.lock:
            if chat_id in self.anon:
                return list(self.anon_messages.get(chat_id, []))

            if chat_id not in self.chats:
                return []

            path = self._chat_file(chat_id)
            items = []

            if not path.is_file():
                return items

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as file:
                    for line in file:
                        line = line.strip()

                        if not line:
                            continue

                        try:
                            entry = self._normalize_entry(json.loads(line))
                        except ValueError:
                            continue

                        if entry:
                            items.append(entry)
            except OSError:
                return items

            if len(items) > MAX_STORED_MESSAGES + 500:
                items = items[-MAX_STORED_MESSAGES:]

                try:
                    temp = path.with_suffix(".tmp")

                    with open(temp, "w", encoding="utf-8") as file:
                        for entry in items:
                            file.write(
                                json.dumps(entry, ensure_ascii=False) + "\n"
                            )

                    os.replace(temp, path)
                except OSError:
                    pass

            return items

    def append(self, chat_id, entry):
        with self.lock:
            entry = self._normalize_entry(entry)

            if entry is None:
                return False

            if chat_id in self.anon:
                items = self.anon_messages.setdefault(chat_id, [])
                items.append(entry)

                if len(items) > MAX_STORED_MESSAGES:
                    del items[: len(items) - MAX_STORED_MESSAGES]

                self.anon[chat_id]["updated"] = time.time()
                return True

            meta = self.chats.get(chat_id)

            if meta is None:
                return False

            try:
                self.dir.mkdir(parents=True, exist_ok=True)

                with open(
                    self._chat_file(chat_id),
                    "a",
                    encoding="utf-8",
                ) as file:
                    file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                return False

            meta["updated"] = time.time()
            self.dirty = True
            return True

    def remove_turn(self, chat_id, turn_id):
        if not isinstance(turn_id, str) or not turn_id:
            return 0

        with self.lock:
            if chat_id in self.anon:
                items = self.anon_messages.get(chat_id, [])
                retained = [
                    entry
                    for entry in items
                    if entry.get("turn_id") != turn_id
                ]
                removed = len(items) - len(retained)

                if removed:
                    self.anon_messages[chat_id] = retained
                    self.anon[chat_id]["updated"] = time.time()

                return removed

            if chat_id not in self.chats:
                return 0

            path = self._chat_file(chat_id)
            retained = []
            removed = 0

            try:
                with open(
                    path,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as file:
                    for line in file:
                        try:
                            entry = json.loads(line)
                        except ValueError:
                            retained.append(line)
                            continue

                        if (
                            isinstance(entry, dict)
                            and entry.get("turn_id") == turn_id
                        ):
                            removed += 1
                        else:
                            retained.append(line)
            except FileNotFoundError:
                return 0

            if not removed:
                return 0

            temporary_path = path.with_suffix(".tmp")

            with open(temporary_path, "w", encoding="utf-8") as file:
                file.writelines(retained)

            os.replace(temporary_path, path)
            self.chats[chat_id]["updated"] = time.time()
            self.dirty = True
            return removed

    def mark_server_used(self, chat_id):
        with self.lock:
            meta = self.anon.get(chat_id) or self.chats.get(chat_id)

            if meta is None or meta.get("server_used"):
                return

            meta["server_used"] = True

            if chat_id in self.anon:
                return

            self._save_index()

    def rename(self, chat_id, name, named=True):
        name = " ".join(str(name).split())[:60] or DEFAULT_CHAT_NAME

        with self.lock:
            meta = self.chats.get(chat_id)

            if meta is not None:
                meta["name"] = name
                meta["named"] = bool(named)
                self._save_index()
                return True

            meta = self.anon.get(chat_id)

            if meta is not None:
                meta["name"] = name
                meta["named"] = bool(named)
                return True

            return False

    def set_last_active(self, chat_id):
        with self.lock:
            if chat_id in self.chats and self.last_active != chat_id:
                self.last_active = chat_id
                self._save_index()

    def delete(self, chat_id):
        with self.lock:
            meta = self.chats.pop(chat_id, None)
            anonymous = False

            if meta is None:
                meta = self.anon.pop(chat_id, None)
                self.anon_messages.pop(chat_id, None)
                anonymous = True

            if meta is None:
                return None

            if not anonymous:
                try:
                    self._chat_file(chat_id).unlink()
                except OSError:
                    pass

                shutil.rmtree(self.images_dir / chat_id, ignore_errors=True)

                if self.last_active == chat_id:
                    self.last_active = None

                if meta.get("server_used"):
                    self._add_pending_locked(meta)

                self._save_index()

            return meta

    def save_thumbnail(self, chat_id, source):
        with self.lock:
            if chat_id in self.anon or not source or not os.path.isfile(source):
                return source

            if chat_id not in self.chats:
                return None

            try:
                folder = self.images_dir / chat_id
                folder.mkdir(parents=True, exist_ok=True)

                image = Image.open(source).convert("RGB")
                image.thumbnail((280, 200), Image.Resampling.LANCZOS)

                target = folder / f"{int(time.time() * 1000)}.jpg"
                image.save(target, "JPEG", quality=80)

                return str(target)
            except Exception:
                return None

    def pending_items(self):
        with self.lock:
            return [dict(item) for item in self.pending]

    def remove_pending(self, item):
        with self.lock:
            target = {
                "user_id": item["user_id"],
                "platform": item["platform"],
            }

            if target in self.pending:
                self.pending.remove(target)
                self._write_json(self.pending_file, self.pending)


def load_settings():
    settings = {
        "voice": DEFAULT_TTS_VOICE,
        "silent_mode": False,
        "mic_muted": False,
        "opacity": DEFAULT_OPACITY,
        "always_on_top": True,
        "font_size": DEFAULT_FONT_SIZE,
        "mic_sensitivity": DEFAULT_MIC_SENSITIVITY,
        "theme_name": DEFAULT_THEME_NAME,
        "theme_accent": DEFAULT_THEME_ACCENT,
        "multi_actions": True,
        "mic_device": "",
        "check_updates_start": True,
        "confirm_close": True,
        "show_timestamps": False,
        "auto_allow_actions": False,
        "web_search": True,
    }

    try:
        if SETTINGS_FILE.is_file():
            data = json.loads(
                SETTINGS_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(data, dict):
                voice = data.get("voice")

                if voice in TTS_VOICES:
                    settings["voice"] = voice

                settings["silent_mode"] = bool(
                    data.get("silent_mode", False)
                )

                settings["mic_muted"] = bool(
                    data.get("mic_muted", False)
                )

                try:
                    opacity = float(
                        data.get("opacity", DEFAULT_OPACITY)
                    )

                    if MIN_OPACITY <= opacity <= 1.0:
                        settings["opacity"] = round(opacity, 2)
                except (TypeError, ValueError):
                    pass

                settings["always_on_top"] = bool(
                    data.get("always_on_top", True)
                )

                settings["multi_actions"] = bool(
                    data.get("multi_actions", True)
                )

                settings["check_updates_start"] = bool(
                    data.get("check_updates_start", True)
                )

                settings["confirm_close"] = bool(
                    data.get("confirm_close", True)
                )

                settings["show_timestamps"] = bool(
                    data.get("show_timestamps", False)
                )

                settings["auto_allow_actions"] = (
                    data.get("auto_allow_actions") is True
                )

                settings["web_search"] = data.get("web_search") is not False

                try:
                    font_size = int(
                        data.get("font_size", DEFAULT_FONT_SIZE)
                    )

                    if font_size in FONT_SIZES:
                        settings["font_size"] = font_size
                except (TypeError, ValueError):
                    pass

                sensitivity = data.get("mic_sensitivity")

                if sensitivity in MIC_SENSITIVITY_LEVELS:
                    settings["mic_sensitivity"] = sensitivity

                mic_device = data.get("mic_device")

                if isinstance(mic_device, str) and len(mic_device) <= 200:
                    settings["mic_device"] = mic_device.strip()

                theme_name = data.get("theme_name")

                if theme_name in THEME_PRESETS or theme_name == "Custom":
                    settings["theme_name"] = theme_name

                theme_accent = normalize_hex(
                    data.get("theme_accent")
                )

                if theme_accent:
                    settings["theme_accent"] = theme_accent

    except Exception:
        pass

    return settings


def save_settings(settings):
    try:
        APP_DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        SETTINGS_FILE.write_text(
            json.dumps(
                settings,
                indent=2,
            ),
            encoding="utf-8",
        )

        return True

    except Exception:
        return False


def find_data_folder():
    candidates = []

    try:
        packages = Path.home() / "AppData" / "Local" / "Packages"

        for package in packages.glob("PythonSoftwareFoundation.Python.*"):
            candidates.append(
                package / "LocalCache" / "Roaming" / "ZanelDATA00"
            )
    except Exception:
        pass

    candidates.append(APP_DATA_DIR)

    for candidate in candidates:
        try:
            if (
                (candidate / "api_key.txt").is_file()
                or (candidate / "settings.json").is_file()
            ):
                return candidate
        except OSError:
            continue

    return APP_DATA_DIR
