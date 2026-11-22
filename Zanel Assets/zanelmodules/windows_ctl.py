import json
import os
import difflib
import subprocess
import threading
import time
import re
import uuid
import ctypes.wintypes
import ctypes
from zanelmodules.apps import normalize_app_text, winget_tail


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


def application_is_running(program):
    requested = str(program).lower().strip()

    requested_clean = "".join(
        character
        for character in requested
        if character.isalnum() or character == " "
    )

    requested_words = set(requested_clean.split())

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process | "
                "Select-Object ProcessName,MainWindowTitle | "
                "ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if result.returncode != 0:
            return False

        data = json.loads(result.stdout)

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            return False

        for process in data:
            if not isinstance(process, dict):
                continue

            process_name = str(
                process.get("ProcessName", "")
            ).strip()

            window_title = str(
                process.get("MainWindowTitle", "")
            ).strip()

            process_clean = "".join(
                character
                for character in process_name.lower()
                if character.isalnum() or character == " "
            )

            title_clean = "".join(
                character
                for character in window_title.lower()
                if character.isalnum() or character == " "
            )

            if (
                requested_clean
                and (
                    requested_clean in process_clean
                    or requested_clean in title_clean
                )
            ):
                return True

            process_words = set(process_clean.split())
            title_words = set(title_clean.split())

            if requested_words:
                if requested_words.intersection(process_words):
                    return True

                if requested_words.intersection(title_words):
                    return True

        return False

    except Exception:
        return False


def get_process_snapshot():
    try:
        output = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Get-Process | Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Csv -NoTypeInformation",
            ],
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        processes = {}

        for line in output.splitlines()[1:]:
            parts = line.strip().strip('"').split('","')

            if len(parts) < 3:
                continue

            try:
                pid = int(
                    parts[0].strip('"')
                )
            except ValueError:
                continue

            processes[pid] = {
                "name": parts[1].strip('"'),
                "title": parts[2].strip('"'),
            }

        return processes

    except Exception:
        return {}


def find_rickroll_process(before):
    deadline = time.time() + 8

    while time.time() < deadline:
        after = get_process_snapshot()

        new_processes = {
            pid: info
            for pid, info in after.items()
            if pid not in before
        }

        for pid, info in new_processes.items():
            name = info["name"].lower()
            title = info["title"].lower()

            if (
                "wmplayer" in name
                or "media player" in name
                or "windows media player" in name
                or "media player" in title
                or "windows media player" in title
            ):
                return pid

        time.sleep(0.25)

    return None


WINDOW_ENUM_PROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LPARAM,
)


BLUETOOTH_SCRIPT = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
$access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
if ($access -ne 'Allowed') { 'DENIED'; exit }
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$bluetooth = $radios | Where-Object { $_.Kind -eq 'Bluetooth' } | Select-Object -First 1
if (-not $bluetooth) { 'NO_RADIO'; exit }
Await ($bluetooth.SetStateAsync('__STATE__')) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$bluetooth.State
"""


def window_user32():
    user32 = ctypes.windll.user32
    hwnd_type = ctypes.wintypes.HWND

    user32.IsWindowVisible.argtypes = [hwnd_type]
    user32.IsWindowVisible.restype = ctypes.wintypes.BOOL

    user32.IsIconic.argtypes = [hwnd_type]
    user32.IsIconic.restype = ctypes.wintypes.BOOL

    user32.GetWindowTextLengthW.argtypes = [hwnd_type]
    user32.GetWindowTextLengthW.restype = ctypes.c_int

    user32.GetWindowTextW.argtypes = [
        hwnd_type,
        ctypes.wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int

    user32.GetWindow.argtypes = [hwnd_type, ctypes.wintypes.UINT]
    user32.GetWindow.restype = hwnd_type

    user32.GetWindowLongW.argtypes = [hwnd_type, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long

    user32.GetWindowThreadProcessId.argtypes = [
        hwnd_type,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

    user32.ShowWindow.argtypes = [hwnd_type, ctypes.c_int]
    user32.ShowWindow.restype = ctypes.wintypes.BOOL

    user32.BringWindowToTop.argtypes = [hwnd_type]
    user32.BringWindowToTop.restype = ctypes.wintypes.BOOL

    user32.SetForegroundWindow.argtypes = [hwnd_type]
    user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL

    user32.EnumWindows.argtypes = [
        WINDOW_ENUM_PROC,
        ctypes.wintypes.LPARAM,
    ]
    user32.EnumWindows.restype = ctypes.wintypes.BOOL

    return user32


def window_is_cloaked(hwnd):
    try:
        cloaked = ctypes.wintypes.DWORD(0)

        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.wintypes.HWND(hwnd),
            14,
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )

        return result == 0 and cloaked.value != 0
    except Exception:
        return False


def list_top_windows():
    user32 = window_user32()
    found = []

    def callback(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            if user32.GetWindow(hwnd, 4):
                return True

            if user32.GetWindowLongW(hwnd, -20) & 0x80:
                return True

            if window_is_cloaked(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)

            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()

            if not title or title == "Program Manager":
                return True

            found.append((hwnd, title))
        except Exception:
            pass

        return True

    enum_proc = WINDOW_ENUM_PROC(callback)
    user32.EnumWindows(enum_proc, 0)

    return found


def window_process_info(hwnd):
    user32 = window_user32()
    kernel32 = ctypes.windll.kernel32

    kernel32.OpenProcess.argtypes = [
        ctypes.wintypes.DWORD,
        ctypes.wintypes.BOOL,
        ctypes.wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.LPWSTR,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.wintypes.BOOL

    pid = ctypes.wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    if not pid.value:
        return "", 0

    handle = kernel32.OpenProcess(0x1000, False, pid.value)

    if not handle:
        return "", pid.value

    try:
        size = ctypes.wintypes.DWORD(520)
        buffer = ctypes.create_unicode_buffer(520)

        if kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            name = os.path.splitext(os.path.basename(buffer.value))[0]
            return name, pid.value
    finally:
        kernel32.CloseHandle(handle)

    return "", pid.value


def find_window_match(requested):
    wanted = normalize_app_text(requested)

    if not wanted:
        return None

    own_pid = os.getpid()
    best = None
    best_score = 0.0

    for hwnd, title in list_top_windows():
        process_name, pid = window_process_info(hwnd)

        if pid == own_pid:
            continue

        for text in (title, process_name):
            clean = normalize_app_text(text)

            if not clean:
                continue

            if text is process_name and clean == wanted:
                score = 1.0
            else:
                score = difflib.SequenceMatcher(
                    None,
                    wanted,
                    clean,
                ).ratio()

                if wanted in clean:
                    score = max(
                        score,
                        0.95 - min(0.2, 0.002 * (len(clean) - len(wanted))),
                    )

            if score > best_score:
                best_score = score
                best = (hwnd, title)

    if best is None or best_score < 0.55:
        return None

    return best


def control_window(requested, mode):
    match = find_window_match(requested)

    if match is None:
        return f"Could not find an open window similar to '{requested}'."

    hwnd, title = match
    parts = [part.strip() for part in title.split(" - ") if part.strip()]
    title = (parts[-1] if parts else title)[:80]
    user32 = window_user32()

    if mode == "minimize":
        user32.ShowWindow(hwnd, 6)
        label = "Minimised"
    elif mode == "maximize":
        user32.ShowWindow(hwnd, 3)
        label = "Maximised"
    else:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)

        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        label = "Focused"

    return f"{label} {title}."


def set_bluetooth_state(enabled):
    import base64

    target = "On" if enabled else "Off"
    script = BLUETOOTH_SCRIPT.replace("__STATE__", target)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=40,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return "Bluetooth change timed out."
    except Exception as exc:
        return f"Could not change Bluetooth: {exc}"

    lines = [
        line.strip()
        for line in (completed.stdout or "").splitlines()
        if line.strip()
    ]

    result = lines[-1] if lines else ""

    if result == "NO_RADIO":
        return "No Bluetooth adapter was found on this PC."

    if result == "DENIED":
        return (
            "Windows denied access to the Bluetooth radio. "
            "Check Settings > Privacy > Radios."
        )

    if result.lower() == target.lower():
        return f"Bluetooth turned {target.lower()}."

    detail = winget_tail(completed.stderr or completed.stdout)

    return f"Could not change Bluetooth. {detail or 'Unknown error.'}"

BT_SERVICE_GUIDS = (
    "0000110B-0000-1000-8000-00805F9B34FB",
    "0000110E-0000-1000-8000-00805F9B34FB",
    "0000110C-0000-1000-8000-00805F9B34FB",
    "0000111E-0000-1000-8000-00805F9B34FB",
    "00001108-0000-1000-8000-00805F9B34FB",
    "00001124-0000-1000-8000-00805F9B34FB",
)

BT_FILLER_WORDS = {
    "my",
    "the",
    "a",
    "an",
    "to",
    "with",
    "connect",
    "please",
    "bluetooth",
    "wireless",
    "portable",
    "device",
    "speaker",
    "speakers",
    "headphones",
    "headphone",
    "headset",
    "earbuds",
    "earphones",
}

class BT_GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class BT_SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", ctypes.c_ushort),
        ("wMonth", ctypes.c_ushort),
        ("wDayOfWeek", ctypes.c_ushort),
        ("wDay", ctypes.c_ushort),
        ("wHour", ctypes.c_ushort),
        ("wMinute", ctypes.c_ushort),
        ("wSecond", ctypes.c_ushort),
        ("wMilliseconds", ctypes.c_ushort),
    ]


class BT_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("Address", ctypes.c_ulonglong),
        ("ulClassofDevice", ctypes.c_ulong),
        ("fConnected", ctypes.wintypes.BOOL),
        ("fRemembered", ctypes.wintypes.BOOL),
        ("fAuthenticated", ctypes.wintypes.BOOL),
        ("stLastSeen", BT_SYSTEMTIME),
        ("stLastUsed", BT_SYSTEMTIME),
        ("szName", ctypes.c_wchar * 248),
    ]


class BT_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("fReturnAuthenticated", ctypes.wintypes.BOOL),
        ("fReturnRemembered", ctypes.wintypes.BOOL),
        ("fReturnUnknown", ctypes.wintypes.BOOL),
        ("fReturnConnected", ctypes.wintypes.BOOL),
        ("fIssueInquiry", ctypes.wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", ctypes.wintypes.HANDLE),
    ]


class BT_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
    ]


def bluetooth_library():
    library = ctypes.WinDLL("bthprops.cpl")
    handle = ctypes.wintypes.HANDLE
    boolean = ctypes.wintypes.BOOL
    dword = ctypes.wintypes.DWORD

    library.BluetoothFindFirstRadio.argtypes = [
        ctypes.POINTER(BT_FIND_RADIO_PARAMS),
        ctypes.POINTER(handle),
    ]
    library.BluetoothFindFirstRadio.restype = handle

    library.BluetoothFindRadioClose.argtypes = [handle]
    library.BluetoothFindRadioClose.restype = boolean

    library.BluetoothFindFirstDevice.argtypes = [
        ctypes.POINTER(BT_SEARCH_PARAMS),
        ctypes.POINTER(BT_DEVICE_INFO),
    ]
    library.BluetoothFindFirstDevice.restype = handle

    library.BluetoothFindNextDevice.argtypes = [
        handle,
        ctypes.POINTER(BT_DEVICE_INFO),
    ]
    library.BluetoothFindNextDevice.restype = boolean

    library.BluetoothFindDeviceClose.argtypes = [handle]
    library.BluetoothFindDeviceClose.restype = boolean

    library.BluetoothSetServiceState.argtypes = [
        handle,
        ctypes.POINTER(BT_DEVICE_INFO),
        ctypes.POINTER(BT_GUID),
        dword,
    ]
    library.BluetoothSetServiceState.restype = dword

    library.BluetoothAuthenticateDeviceEx.argtypes = [
        ctypes.wintypes.HWND,
        handle,
        ctypes.POINTER(BT_DEVICE_INFO),
        ctypes.c_void_p,
        dword,
    ]
    library.BluetoothAuthenticateDeviceEx.restype = dword

    library.BluetoothFindNextRadio.argtypes = [
        handle,
        ctypes.POINTER(handle),
    ]
    library.BluetoothFindNextRadio.restype = boolean

    return library


def bluetooth_make_guid(text):
    value = uuid.UUID(text)

    return BT_GUID(
        value.time_low,
        value.time_mid,
        value.time_hi_version,
        (ctypes.c_ubyte * 8)(*value.bytes[8:]),
    )


def bluetooth_scan(library, radio, inquiry, timeout=4):
    params = BT_SEARCH_PARAMS()
    params.dwSize = ctypes.sizeof(BT_SEARCH_PARAMS)
    params.fReturnAuthenticated = True
    params.fReturnRemembered = True
    params.fReturnUnknown = bool(inquiry)
    params.fReturnConnected = True
    params.fIssueInquiry = bool(inquiry)
    params.cTimeoutMultiplier = max(1, min(int(timeout), 48))
    params.hRadio = radio

    info = BT_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(BT_DEVICE_INFO)
    devices = []

    found = library.BluetoothFindFirstDevice(
        ctypes.byref(params),
        ctypes.byref(info),
    )

    if not found:
        return devices

    try:
        while True:
            copy = BT_DEVICE_INFO()

            ctypes.memmove(
                ctypes.byref(copy),
                ctypes.byref(info),
                ctypes.sizeof(BT_DEVICE_INFO),
            )

            devices.append(copy)

            if not library.BluetoothFindNextDevice(
                found,
                ctypes.byref(info),
            ):
                break
    finally:
        library.BluetoothFindDeviceClose(found)

    return devices


def bluetooth_clean(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)

    return " ".join(text.split())


def bluetooth_query_variants(requested):
    full = bluetooth_clean(requested)
    variants = []

    def add(value):
        value = value.strip()

        if value and value not in variants:
            variants.append(value)

    add(full)

    core = [
        word
        for word in full.split()
        if word not in BT_FILLER_WORDS
    ]

    add(" ".join(core))

    for word in sorted(core, key=len, reverse=True):
        if len(word) >= 2:
            add(word)

    return variants


def bluetooth_name_score(variant, name):
    if not variant or not name:
        return 0.0

    if variant == name:
        return 1.0

    compact_variant = variant.replace(" ", "")
    compact_name = name.replace(" ", "")

    if compact_variant == compact_name:
        return 0.99

    score = difflib.SequenceMatcher(None, variant, name).ratio()

    if len(compact_variant) >= 2:
        if compact_name.startswith(compact_variant):
            score = max(score, 0.95)
        elif variant in name.split():
            score = max(score, 0.93)
        elif compact_variant in compact_name:
            score = max(score, 0.9)

    if len(compact_name) >= 3 and compact_name in compact_variant:
        score = max(score, 0.88)

    variant_words = set(variant.split())
    name_words = set(name.split())

    if variant_words:
        overlap = len(variant_words & name_words) / len(variant_words)

        if overlap > 0:
            score = max(score, 0.6 + 0.25 * overlap)

    return score


def bluetooth_best_match(devices, requested, minimum=0.6):
    variants = bluetooth_query_variants(requested)

    if not variants:
        return None

    best = None
    best_key = (0.0, 0, 0)

    for device in devices:
        name = bluetooth_clean(device.szName)

        if not name:
            continue

        score = max(
            bluetooth_name_score(variant, name)
            for variant in variants
        )

        if score < minimum:
            continue

        key = (
            round(score, 3),
            int(bool(device.fAuthenticated or device.fRemembered)),
            int(bool(device.fConnected)),
        )

        if best is None or key > best_key:
            best = device
            best_key = key

    return best


def bluetooth_pair(library, radio, device):
    outcome = {"code": None}

    def worker():
        outcome["code"] = library.BluetoothAuthenticateDeviceEx(
            None,
            radio,
            ctypes.byref(device),
            None,
            2,
        )

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(25)

    return outcome["code"] == 0


def bluetooth_enable_services(library, radio, device):
    enabled = False

    for text in BT_SERVICE_GUIDS:
        guid = bluetooth_make_guid(text)

        library.BluetoothSetServiceState(
            radio,
            ctypes.byref(device),
            ctypes.byref(guid),
            0,
        )

        time.sleep(0.3)

        result = library.BluetoothSetServiceState(
            radio,
            ctypes.byref(device),
            ctypes.byref(guid),
            1,
        )

        if result == 0:
            enabled = True

    return enabled


def bluetooth_audio_active(name):
    safe = re.sub(r"[^A-Za-z0-9 ]+", "", str(name)).strip()

    if not safe:
        return False

    script = (
        "$n = '" + safe + "'; "
        "$items = Get-PnpDevice -PresentOnly "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { "
        "$_.FriendlyName -like ('*' + $n + '*') "
        "-and $_.Status -eq 'OK' "
        "-and $_.Class -eq 'AudioEndpoint' }; "
        "if ($items) { 'YES' } else { 'NO' }"
    )

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        return "YES" in (completed.stdout or "")
    except Exception:
        return False


def bluetooth_is_connected(library, radio, address, name=""):
    for item in bluetooth_scan(library, radio, False):
        if item.Address == address and item.fConnected:
            return True

    if name:
        return bluetooth_audio_active(name)

    return False


def bluetooth_refresh(library, radio, device):
    for item in bluetooth_scan(library, radio, False):
        if item.Address == device.Address:
            return item

    return device


def bluetooth_open_radios(library):
    handles = []
    params = BT_FIND_RADIO_PARAMS()
    params.dwSize = ctypes.sizeof(BT_FIND_RADIO_PARAMS)
    radio = ctypes.wintypes.HANDLE()

    finder = library.BluetoothFindFirstRadio(
        ctypes.byref(params),
        ctypes.byref(radio),
    )

    if not finder:
        return handles

    try:
        while True:
            handles.append(ctypes.wintypes.HANDLE(radio.value))
            radio = ctypes.wintypes.HANDLE()

            if not library.BluetoothFindNextRadio(
                finder,
                ctypes.byref(radio),
            ):
                break
    finally:
        library.BluetoothFindRadioClose(finder)

    return handles


def bluetooth_wait_for_radios(library, attempts):
    for _ in range(attempts):
        radios = bluetooth_open_radios(library)

        if radios:
            return radios

        time.sleep(1)

    return []


def connect_bluetooth_device(requested, confirm, confirm_enable=None):
    try:
        library = bluetooth_library()
    except OSError:
        return "Bluetooth is not available on this PC."

    radios = bluetooth_wait_for_radios(library, 2)
    note = ""

    if not radios:
        if confirm_enable is None:
            return (
                "No Bluetooth adapter was found, or Bluetooth is turned off. "
                "Turn Bluetooth on first."
            )

        if not confirm_enable():
            return "User declined turning on Bluetooth."

        state = set_bluetooth_state(True)
        radios = bluetooth_wait_for_radios(library, 10)

        if not radios:
            return f"Bluetooth could not be made available. {state}"

        time.sleep(1.5)
        note = "Bluetooth was turned on. "

    try:
        known = {}
        match = None
        match_radio = None

        plans = (
            (False, 4, 0.85),
            (True, 4, 0.85),
            (True, 10, 0.6),
        )

        for inquiry, timeout, minimum in plans:
            for radio in radios:
                bucket = known.setdefault(str(radio.value), {})

                for device in bluetooth_scan(
                    library,
                    radio,
                    inquiry,
                    timeout,
                ):
                    bucket[device.Address] = device

                found = bluetooth_best_match(
                    list(bucket.values()),
                    requested,
                    minimum,
                )

                if found is not None:
                    match = found
                    match_radio = radio
                    break

            if match is not None:
                break

        if match is None:
            names = sorted(
                {
                    device.szName.strip()
                    for bucket in known.values()
                    for device in bucket.values()
                    if device.szName.strip()
                }
            )

            message = (
                f"{note}Could not find a Bluetooth device similar to "
                f"'{requested}'. Make sure it is turned on, in range and "
                f"in pairing mode."
            )

            if names:
                message += " Devices seen: " + ", ".join(names[:10]) + "."

            return message

        name = match.szName.strip() or requested
        paired = bool(match.fAuthenticated)

        if bluetooth_is_connected(
            library,
            match_radio,
            match.Address,
            name,
        ):
            return f"{note}{name} is already connected."

        if not confirm(name, paired):
            return "User declined connecting to the Bluetooth device."

        if not paired:
            if not bluetooth_pair(library, match_radio, match):
                return (
                    f"Could not pair with {name}. It may need a PIN, "
                    f"password or confirmation, so the pairing was denied. "
                    f"The user can pair it manually in Windows Settings."
                )

            match = bluetooth_refresh(library, match_radio, match)

        started = False

        for _ in range(3):
            if bluetooth_enable_services(library, match_radio, match):
                started = True

            for _ in range(8):
                time.sleep(1)

                if bluetooth_is_connected(
                    library,
                    match_radio,
                    match.Address,
                    name,
                ):
                    return f"{note}Connected to {name}."

            match = bluetooth_refresh(library, match_radio, match)

        if not started:
            return (
                f"{note}Windows would not start a connection to {name}. "
                f"Make sure it is turned on, in range and not already "
                f"connected to another device."
            )

        return (
            f"{note}Sent the connection request to {name}, but Windows did "
            f"not report it as connected. Make sure it is in range and not "
            f"connected to a phone or another device."
        )
    finally:
        for radio in radios:
            ctypes.windll.kernel32.CloseHandle(radio)


def run_on_main(root, function):
    box = {"value": None, "error": None}
    finished = threading.Event()

    def runner():
        try:
            box["value"] = function()
        except Exception as exc:
            box["error"] = exc
        finally:
            finished.set()

    root.after(0, runner)
    finished.wait(120)

    if box["error"] is not None:
        raise box["error"]

    return box["value"]
