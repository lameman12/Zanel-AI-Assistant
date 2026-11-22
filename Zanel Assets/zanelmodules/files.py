import os
import difflib
import shutil
import time
import ctypes.wintypes
import re
from datetime import datetime
import ctypes
import sys
from zanelmodules.apps import normalize_app_text
from zanelmodules.config import APP_DATA_DIR, PROTECTED_PROGRAM_FOLDERS, SKIP_DIRECTORIES
from zanelmodules.dialogs import ask_local_confirmation


class SHFILEOPSTRUCTW(ctypes.Structure):
    _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8
    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("wFunc", ctypes.wintypes.UINT),
        ("pFrom", ctypes.wintypes.LPCWSTR),
        ("pTo", ctypes.wintypes.LPCWSTR),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", ctypes.wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.wintypes.LPCWSTR),
    ]


def format_size(size):
    value = float(size)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{value:.0f} {unit}"

            return f"{value:.1f} {unit}"

        value /= 1024

    return ""


def user_folder_roots():
    home = os.path.expanduser("~")
    roots = []
    seen = set()

    def add(path):
        if not path or not os.path.isdir(path):
            return

        key = os.path.normcase(os.path.abspath(path))

        if key in seen:
            return

        seen.add(key)
        roots.append(path)

    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        add(os.environ.get(variable, ""))

    try:
        for entry in os.listdir(home):
            if entry.lower().startswith("onedrive"):
                add(os.path.join(home, entry))
    except OSError:
        pass

    return roots


def drive_roots():
    drives = []

    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZAB":
        drive = f"{letter}:\\"

        if os.path.isdir(drive):
            drives.append(drive)

    return drives


def hinted_directories(hint):
    hint_text = str(hint or "").strip()
    results = []
    seen = set()

    def add(path):
        if not path or not os.path.isdir(path):
            return

        key = os.path.normcase(os.path.abspath(path))

        if key in seen:
            return

        seen.add(key)
        results.append(path)

    if hint_text:
        add(
            os.path.expandvars(
                os.path.expanduser(hint_text.strip('"').strip("'"))
            )
        )

    lowered = hint_text.lower()
    home = os.path.expanduser("~")
    onedrive_roots = user_folder_roots()

    names = [
        folder
        for folder in (
            "desktop",
            "downloads",
            "documents",
            "pictures",
            "videos",
            "music",
        )
        if folder in lowered
    ]

    if "onedrive" in lowered:
        for base in onedrive_roots:
            for folder in names:
                add(os.path.join(base, folder.capitalize()))

            add(base)

    for folder in names:
        add(os.path.join(home, folder.capitalize()))

        for base in onedrive_roots:
            add(os.path.join(base, folder.capitalize()))

    drive_match = re.search(r"\b([a-z])\s+drive\b", lowered)

    if drive_match:
        add(f"{drive_match.group(1).upper()}:\\")

    return results


def default_search_directories():
    home = os.path.expanduser("~")
    onedrive_roots = user_folder_roots()
    roots = []

    for base in [home] + onedrive_roots:
        for folder in (
            "Desktop",
            "Documents",
            "Downloads",
            "Pictures",
            "Videos",
            "Music",
        ):
            roots.append(os.path.join(base, folder))

    roots.extend(onedrive_roots)
    roots.append(home)

    return [path for path in roots if os.path.isdir(path)]


def score_item_name(requested, candidate, folder=False):
    requested = str(requested or "").strip().lower()
    candidate = str(candidate or "").strip().lower()

    if not requested or not candidate:
        return 0.0

    if requested == candidate:
        return 1.0

    if folder:
        requested_stem, requested_extension = requested, ""
        candidate_stem, candidate_extension = candidate, ""
    else:
        requested_stem, requested_extension = os.path.splitext(requested)
        candidate_stem, candidate_extension = os.path.splitext(candidate)

    left = normalize_app_text(requested_stem)
    right = normalize_app_text(candidate_stem)

    if not left or not right:
        return 0.0

    if left == right:
        score = 0.99
    else:
        score = difflib.SequenceMatcher(None, left, right).ratio()

        if len(left) >= 4 and left in right:
            score = max(
                score,
                0.9 - min(0.1, 0.01 * (len(right) - len(left))),
            )

        left_tokens = set(re.split(r"[^a-z0-9]+", requested_stem)) - {""}
        right_tokens = set(re.split(r"[^a-z0-9]+", candidate_stem)) - {""}

        if left_tokens and left_tokens <= right_tokens:
            score = max(score, 0.88)

    if requested_extension and requested_extension != candidate_extension:
        score -= 0.25

    return max(0.0, min(1.0, score))


def search_local_items(requested, folder, hint):
    deadline = time.monotonic() + 45
    scanned = set()
    seen = set()
    scored = []

    def scan(base):
        key = os.path.normcase(os.path.abspath(base))

        if key in scanned:
            return

        scanned.add(key)

        for current, directories, files in os.walk(base, topdown=True):
            if time.monotonic() > deadline:
                return

            directories[:] = [
                directory
                for directory in directories
                if directory.lower() not in SKIP_DIRECTORIES
                and not directory.startswith("$")
                and os.path.normcase(
                    os.path.abspath(os.path.join(current, directory))
                )
                not in scanned
            ]

            for item in (directories if folder else files):
                score = score_item_name(requested, item, folder)

                if score < 0.8:
                    continue

                path = os.path.join(current, item)
                path_key = os.path.normcase(os.path.abspath(path))

                if path_key in seen:
                    continue

                seen.add(path_key)
                scored.append((score, path))

    tiers = (
        hinted_directories(hint),
        default_search_directories(),
        drive_roots(),
    )

    for tier in tiers:
        for base in tier:
            if time.monotonic() > deadline:
                break

            try:
                scan(base)
            except OSError:
                continue

        if (
            any(score >= 0.9 for score, _path in scored)
            or time.monotonic() > deadline
        ):
            break

    scored.sort(key=lambda item: (-item[0], len(item[1])))

    return scored[:10]


def protected_reason(path):
    try:
        target = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    except (OSError, ValueError):
        return "The path is invalid."

    if not os.path.splitdrive(target)[1].strip("\\/"):
        return "Drive roots cannot be deleted."

    def inside(parent, child):
        parent = parent.rstrip("\\/")
        return child == parent or child.startswith(parent + os.sep)

    home = os.path.normcase(os.path.realpath(os.path.expanduser("~")))
    protected_folders = {home, os.path.dirname(home)}

    bases = [home]

    for root_path in user_folder_roots():
        bases.append(os.path.normcase(os.path.realpath(root_path)))

    for base in bases:
        protected_folders.add(base)

        for folder in (
            "Desktop",
            "Documents",
            "Downloads",
            "Pictures",
            "Videos",
            "Music",
            "AppData",
        ):
            protected_folders.add(
                os.path.normcase(os.path.join(base, folder))
            )

    if target in protected_folders:
        return "That is a protected user folder."

    windows = os.path.normcase(
        os.path.realpath(os.environ.get("SystemRoot", r"C:\Windows"))
    )

    if inside(windows, target):
        return "System files cannot be deleted."

    for variable, default in (
        ("ProgramFiles", r"C:\Program Files"),
        ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ("ProgramW6432", r"C:\Program Files"),
        ("ProgramData", r"C:\ProgramData"),
    ):
        program_root = os.path.normcase(
            os.path.realpath(os.environ.get(variable, default))
        )

        if target == program_root:
            return "Program folders cannot be deleted."

        if inside(program_root, target):
            first = (
                target[len(program_root):].strip("\\/").split(os.sep)[0]
            )

            if first in PROTECTED_PROGRAM_FOLDERS:
                return "That is a protected system folder."

    try:
        data_dir = os.path.normcase(os.path.realpath(str(APP_DATA_DIR)))

        if inside(data_dir, target):
            return "Zanel's own data cannot be deleted."
    except OSError:
        pass

    own_paths = []

    for value in (
        getattr(sys, "executable", ""),
        sys.argv[0] if sys.argv else "",
        globals().get("__file__", ""),
    ):
        if value:
            try:
                own_paths.append(
                    os.path.normcase(os.path.realpath(os.path.abspath(value)))
                )
            except (OSError, ValueError):
                continue

    for own in own_paths:
        if inside(target, own):
            return "Zanel's own files cannot be deleted."

    return ""


def describe_item(path):
    try:
        info = os.stat(path)
        modified = datetime.fromtimestamp(info.st_mtime).strftime(
            "%Y-%m-%d %H:%M"
        )
    except (OSError, ValueError):
        return "Unknown size"

    if os.path.isdir(path):
        count = 0

        for _current, directories, files in os.walk(path):
            count += len(files) + len(directories)

            if count > 5000:
                return f"Folder, over 5000 items, modified {modified}"

        return f"Folder, {count} items, modified {modified}"

    return f"{format_size(info.st_size)}, modified {modified}"


def clear_read_only(path):
    try:
        if os.path.isdir(path):
            for current, directories, files in os.walk(path):
                for item in directories + files:
                    try:
                        os.chmod(os.path.join(current, item), 0o666)
                    except OSError:
                        pass

        os.chmod(path, 0o666)
    except OSError:
        pass


def send_to_recycle_bin(path):
    try:
        target = os.path.abspath(path)

        operation = SHFILEOPSTRUCTW()
        operation.hwnd = None
        operation.wFunc = 3
        operation.pFrom = target + "\0"
        operation.pTo = None
        operation.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400
        operation.fAnyOperationsAborted = False
        operation.hNameMappings = None
        operation.lpszProgressTitle = None

        result = ctypes.windll.shell32.SHFileOperationW(
            ctypes.byref(operation)
        )
    except Exception:
        return False

    return (
        result == 0
        and not operation.fAnyOperationsAborted
        and not os.path.lexists(path)
    )


def permanent_delete(path):
    absolute = os.path.abspath(path)
    attempts = [absolute]

    if not absolute.startswith("\\\\?\\"):
        attempts.append("\\\\?\\" + absolute)

    last_error = ""

    def retry_after_chmod(function, target, _info):
        os.chmod(target, 0o666)
        function(target)

    for target in attempts:
        for _ in range(3):
            try:
                if os.path.isdir(target) and not os.path.islink(target):
                    shutil.rmtree(target, onerror=retry_after_chmod)
                else:
                    try:
                        os.chmod(target, 0o666)
                    except OSError:
                        pass

                    os.remove(target)
            except FileNotFoundError:
                return True, ""
            except PermissionError:
                last_error = "The item is in use or access was denied."
                time.sleep(0.6)
                continue
            except OSError as exc:
                last_error = str(exc)
                time.sleep(0.6)
                continue

            if not os.path.lexists(absolute):
                return True, ""

    return False, last_error


def find_leftover_folders(name, location):
    wanted = normalize_app_text(name)
    found = []
    seen = set()

    def add(path):
        key = os.path.normcase(os.path.abspath(path))

        if key in seen or not os.path.isdir(path):
            return

        if protected_reason(path):
            return

        seen.add(key)
        found.append(path)

    local = os.environ.get("LOCALAPPDATA", "")
    bases = [
        os.environ.get("APPDATA", ""),
        local,
        os.path.join(local, "Programs") if local else "",
    ]

    for base in bases:
        if not base or not os.path.isdir(base):
            continue

        try:
            entries = os.listdir(base)
        except OSError:
            continue

        for entry in entries:
            path = os.path.join(base, entry)

            if os.path.isdir(path) and normalize_app_text(entry) == wanted:
                add(path)

    if location and os.path.isdir(location):
        folder_name = normalize_app_text(os.path.basename(location.rstrip("\\/")))

        if folder_name and (wanted in folder_name or folder_name in wanted):
            add(location)

    return found


def cleanup_leftovers(root, name, location):
    folders = find_leftover_folders(name, location)

    if not folders:
        return " No leftover folders were found."

    listing = "\n".join(folders[:5])

    if not ask_local_confirmation(
        root,
        "Zanel wants to delete leftover files",
        "Move these leftover folders to the Recycle Bin?\n\n" + listing,
    ):
        return " The user declined removing the leftover folders."

    removed = 0

    for folder in folders:
        if send_to_recycle_bin(folder):
            removed += 1
            continue

        clear_read_only(folder)

        if send_to_recycle_bin(folder) or not os.path.lexists(folder):
            removed += 1

    return (
        f" Moved {removed} of {len(folders)} leftover folders "
        "to the Recycle Bin."
    )
