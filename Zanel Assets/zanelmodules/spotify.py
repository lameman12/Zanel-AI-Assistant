import base64
import ctypes
import ctypes.wintypes
import difflib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse

import pyautogui
import pyperclip

from zanelmodules.windows_ctl import control_window, find_window_match


OCR_SCRIPT = r"""
$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = 'Stop'
[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
$path = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__PATH__'))
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1)
function Await-Operation($operation, $resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait() | Out-Null
    $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) {
    throw 'Windows OCR is unavailable for the current user languages.'
}
$file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = Await-Operation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
    $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = New-Object System.Collections.ArrayList
    foreach ($line in $result.Lines) {
        $words = @($line.Words)
        if ($words.Count -eq 0) {
            continue
        }
        $left = [double]::MaxValue
        $top = [double]::MaxValue
        $right = [double]::MinValue
        $bottom = [double]::MinValue
        foreach ($word in $words) {
            $rect = $word.BoundingRect
            if ($rect.X -lt $left) { $left = [double]$rect.X }
            if ($rect.Y -lt $top) { $top = [double]$rect.Y }
            if (($rect.X + $rect.Width) -gt $right) { $right = [double]($rect.X + $rect.Width) }
            if (($rect.Y + $rect.Height) -gt $bottom) { $bottom = [double]($rect.Y + $rect.Height) }
        }
        [void]$lines.Add([PSCustomObject]@{
            text = [string]$line.Text
            x = [int][math]::Round($left)
            y = [int][math]::Round($top)
            width = [int][math]::Round($right - $left)
            height = [int][math]::Round($bottom - $top)
        })
    }
    $json = ConvertTo-Json -InputObject @($lines.ToArray()) -Compress -Depth 3
    if ([string]::IsNullOrWhiteSpace($json)) {
        $json = '[]'
    }
    $json = [regex]::Replace($json, '[^\x20-\x7E]', { param($m) '\u{0:x4}' -f [int][char]$m.Value })
    [Console]::Out.WriteLine("OCR_RESULT:$json")
}
finally {
    $stream.Dispose()
}
"""


def _normalize_text(text):
    return "".join(
        character.casefold()
        for character in str(text or "")
        if character.isalnum()
    )


class _SpotifyCancelled(Exception):
    pass


def _raise_if_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise _SpotifyCancelled("Action canceled.")


def _wait_or_cancel(cancel_event, seconds):
    _raise_if_cancelled(cancel_event)

    if cancel_event is None:
        time.sleep(seconds)
        return

    if cancel_event.wait(seconds):
        raise _SpotifyCancelled("Action canceled.")

    _raise_if_cancelled(cancel_event)


def _stop_process(process):
    if process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass

    try:
        process.communicate(timeout=0.5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _run_cancellable_process(command, cancel_event=None, timeout=15, **kwargs):
    _raise_if_cancelled(cancel_event)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    deadline = time.monotonic() + timeout

    try:
        while True:
            _raise_if_cancelled(cancel_event)
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)

            try:
                stdout, stderr = process.communicate(
                    timeout=min(0.1, remaining)
                )
                return subprocess.CompletedProcess(
                    command,
                    process.returncode,
                    stdout,
                    stderr,
                )
            except subprocess.TimeoutExpired:
                continue
    except _SpotifyCancelled:
        _stop_process(process)
        raise
    except Exception:
        _stop_process(process)
        raise


def _recognize_text(image_path, cancel_event=None):
    _raise_if_cancelled(cancel_event)
    path_token = base64.b64encode(
        image_path.encode("utf-8")
    ).decode("ascii")
    script = OCR_SCRIPT.replace("__PATH__", path_token)
    encoded_script = base64.b64encode(
        script.encode("utf-16-le")
    ).decode("ascii")

    try:
        completed = _run_cancellable_process(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                encoded_script,
            ],
            cancel_event=cancel_event,
            timeout=15,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Local screen text detection timed out.") from exc

    _raise_if_cancelled(cancel_event)

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-1000:]
        raise RuntimeError(
            detail or "Windows local text detection failed."
        )

    output = (completed.stdout or "").replace("\ufeff", "").strip()
    marker = "OCR_RESULT:"
    marker_index = output.rfind(marker)

    if marker_index != -1:
        output = output[marker_index + len(marker):].strip()
    else:
        starts = [
            index
            for index in (output.find("["), output.find("{"))
            if index != -1
        ]

        if starts:
            output = output[min(starts):]

    if not output:
        return []

    try:
        detected, _ = json.JSONDecoder().raw_decode(output)
    except json.JSONDecodeError as exc:
        snippet = output[:200].replace("\r", " ").replace("\n", " ")
        raise RuntimeError(
            "Windows local text detection returned invalid data: "
            f"{snippet}"
        ) from exc

    if isinstance(detected, str):
        try:
            detected = json.loads(detected)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Windows local text detection returned invalid data."
            ) from exc

    if detected is None:
        return []

    if isinstance(detected, dict):
        detected = [detected]

    if not isinstance(detected, list):
        raise RuntimeError(
            "Windows local text detection returned an invalid result."
        )

    lines = []

    for item in detected:
        if not isinstance(item, dict):
            continue

        text = str(item.get("text") or "").strip()

        if not text:
            continue

        try:
            bounds = {
                key: int(round(float(item[key])))
                for key in ("x", "y", "width", "height")
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

        lines.append(
            {
                "text": text,
                **bounds,
            }
        )

    return lines


def _window_rectangle(hwnd):
    user32 = ctypes.windll.user32
    rectangle = ctypes.wintypes.RECT()
    user32.GetWindowRect.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(ctypes.wintypes.RECT),
    ]
    user32.GetWindowRect.restype = ctypes.wintypes.BOOL

    if not user32.GetWindowRect(hwnd, ctypes.byref(rectangle)):
        raise RuntimeError("Could not read the Spotify window bounds.")

    return (
        rectangle.left,
        rectangle.top,
        rectangle.right,
        rectangle.bottom,
    )


def _capture_spotify_window(hwnd, cancel_event=None):
    _raise_if_cancelled(cancel_event)
    screen_width, screen_height = pyautogui.size()
    window_left, window_top, window_right, window_bottom = _window_rectangle(hwnd)
    left = max(0, window_left)
    top = max(0, window_top)
    right = min(screen_width, window_right)
    bottom = min(screen_height, window_bottom)

    if right - left < 200 or bottom - top < 200:
        raise RuntimeError(
            "The Spotify window is not visible on the primary display."
        )

    cropped = pyautogui.screenshot(
        region=(left, top, right - left, bottom - top)
    )
    file_descriptor, image_path = tempfile.mkstemp(suffix=".png")
    os.close(file_descriptor)

    try:
        cropped.save(image_path, format="PNG")
        lines = _recognize_text(image_path, cancel_event)
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    _raise_if_cancelled(cancel_event)

    for line in lines:
        line["x"] += left
        line["y"] += top

    visible = [line for line in lines if _belongs_to_window(line, hwnd)]

    if lines and not visible:
        raise RuntimeError("Another window is covering Spotify.")

    return visible, (left, top, right - left, bottom - top)


def _foreground_window():
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
    return int(user32.GetForegroundWindow() or 0)


def _force_foreground(hwnd):
    try:
        user32 = ctypes.WinDLL("user32")
        user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
        user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
        user32.BringWindowToTop.argtypes = [ctypes.wintypes.HWND]
        user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)

        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _set_topmost(hwnd, enabled):
    try:
        user32 = ctypes.WinDLL("user32")
        user32.SetWindowPos.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = ctypes.wintypes.BOOL
        insert_after = ctypes.wintypes.HWND(-1 if enabled else -2)
        user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    except Exception:
        pass


def _belongs_to_window(line, hwnd):
    try:
        user32 = ctypes.WinDLL("user32")
        user32.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]
        user32.WindowFromPoint.restype = ctypes.wintypes.HWND
        user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.wintypes.HWND
        point = ctypes.wintypes.POINT(
            int(line["x"] + line["width"] // 2),
            int(line["y"] + line["height"] // 2),
        )
        found = user32.WindowFromPoint(point)

        if not found:
            return False

        owners = {
            int(found),
            int(user32.GetAncestor(found, 2) or 0),
            int(user32.GetAncestor(found, 3) or 0),
        }
        return int(hwnd) in owners
    except Exception:
        return True


def _ensure_spotify_foreground(hwnd, cancel_event=None):
    for attempt in range(5):
        _raise_if_cancelled(cancel_event)

        if _foreground_window() == int(hwnd):
            return

        _force_foreground(hwnd)

        if attempt % 2:
            try:
                control_window("Spotify", "focus")
            except Exception:
                pass

        _wait_or_cancel(cancel_event, 0.5)

    raise RuntimeError(
        "Spotify lost focus and could not be brought back to the front."
    )

def _read_spotify_window(hwnd, cancel_event=None):
    last_error = None

    for attempt in range(6):
        _raise_if_cancelled(cancel_event)

        try:
            current = _find_spotify_window() or hwnd
            _force_foreground(current)
            _ensure_spotify_foreground(current, cancel_event)
            _wait_or_cancel(cancel_event, 0.25)
            lines, bounds = _capture_spotify_window(current, cancel_event)

            if _foreground_window() == int(current):
                return lines, bounds

            last_error = RuntimeError(
                "Spotify did not stay in front long enough to read its screen."
            )
        except _SpotifyCancelled:
            raise
        except Exception as exc:
            last_error = exc

        _wait_or_cancel(cancel_event, 0.6 + attempt * 0.3)

    raise RuntimeError(str(last_error))

def _find_search_field(lines, window_bounds):
    left, top, width, height = window_bounds
    target = "whatdoyouwanttoplay"
    matches = []

    for line in lines:
        center_y = line["y"] + line["height"] / 2

        if center_y > top + height * 0.42:
            continue

        normalized = _normalize_text(line["text"])
        score = difflib.SequenceMatcher(
            None,
            target,
            normalized,
        ).ratio()

        if target in normalized:
            score = 1.0

        if score >= 0.72:
            matches.append((score, line))

    if matches:
        return max(
            matches,
            key=lambda item: (item[0], -item[1]["y"]),
        )[1]

    static_labels = {
        "home",
        "search",
        "spotify",
        "yourlibrary",
        "premium",
        "installapp",
        "whatsnew",
        "profile",
    }
    candidates = []

    for line in lines:
        normalized = _normalize_text(line["text"])
        center_x = line["x"] + line["width"] / 2
        center_y = line["y"] + line["height"] / 2
        relative_x = (center_x - left) / width
        relative_y = (center_y - top) / height

        if (
            len(normalized) < 3
            or normalized in static_labels
            or not 0.25 <= relative_x <= 0.8
            or not 0.03 <= relative_y <= 0.28
        ):
            continue

        distance = abs(relative_x - 0.5) + abs(relative_y - 0.12)
        candidates.append((distance, line))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def _track_match_score(text, query):
    query_words = [
        _normalize_text(word)
        for word in str(query or "").split()
        if _normalize_text(word)
    ]
    line_words = {
        _normalize_text(word)
        for word in str(text or "").split()
        if _normalize_text(word)
    }

    if not query_words or not line_words:
        return 0.0

    normalized_query = _normalize_text(query)
    normalized_line = _normalize_text(text)

    if normalized_query == normalized_line:
        return 1.2

    if normalized_query in normalized_line:
        return 1.0

    if len(query_words) == 1:
        return 1.0 if query_words[0] in line_words else 0.0

    overlap = len(set(query_words).intersection(line_words)) / len(
        set(query_words)
    )
    similarity = difflib.SequenceMatcher(
        None,
        normalized_query,
        normalized_line,
    ).ratio()
    return max(overlap, similarity)


def _find_track_result(lines, query, window_bounds, search_field=None):
    left, top, width, height = window_bounds
    minimum_y = top + height * 0.18
    minimum_x = left + width * 0.12

    if search_field is not None:
        minimum_y = max(
            minimum_y,
            search_field["y"] + search_field["height"] + 8,
        )

    song_sections = [
        line["y"] + line["height"] / 2
        for line in lines
        if (
            _normalize_text(line["text"]) in ("song", "songs")
            and line["x"] >= minimum_x
            and line["y"] >= minimum_y
        )
    ]
    section_y = min(song_sections) if song_sections else None
    candidates = []

    for line in lines:
        center_y = line["y"] + line["height"] / 2

        if line["x"] < minimum_x or center_y < minimum_y:
            continue

        if section_y is not None and center_y <= section_y:
            continue

        score = _track_match_score(line["text"], query)

        if score >= 0.68:
            candidates.append((score, line))

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: (-item[0], item[1]["y"], item[1]["x"]),
    )[1]


def _is_playing_result(lines, query, window_bounds):
    left, top, width, height = window_bounds
    minimum_y = top + height * 0.84
    maximum_y = top + height * 0.99

    return any(
        line["y"] + line["height"] / 2 >= minimum_y
        and line["y"] + line["height"] / 2 <= maximum_y
        and line["x"] < left + width * 0.38
        and _track_match_score(line["text"], query) >= 0.68
        for line in lines
    )


def _list_spotify_windows():
    wintypes = ctypes.wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.RECT),
    ]
    user32.GetClassNameW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    found = []

    def callback(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)

            if class_buffer.value != "Chrome_WidgetWin_1":
                return True

            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            handle = kernel32.OpenProcess(0x1000, False, process_id.value)

            if not handle:
                return True

            try:
                size = wintypes.DWORD(1024)
                buffer = ctypes.create_unicode_buffer(1024)
                ok = kernel32.QueryFullProcessImageNameW(
                    handle,
                    0,
                    buffer,
                    ctypes.byref(size),
                )
            finally:
                kernel32.CloseHandle(handle)

            if not ok:
                return True

            if os.path.basename(buffer.value).lower() != "spotify.exe":
                return True

            if user32.IsIconic(hwnd):
                found.append((1, int(hwnd)))
                return True

            rectangle = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rectangle))
            width = rectangle.right - rectangle.left
            height = rectangle.bottom - rectangle.top

            if width < 300 or height < 300:
                return True

            found.append((width * height, int(hwnd)))
        except Exception:
            pass

        return True

    enum_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    user32.EnumWindows.argtypes = [enum_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(enum_type(callback), 0)
    found.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in found]


def _find_spotify_window():
    try:
        windows = _list_spotify_windows()
    except Exception:
        windows = []

    if windows:
        return windows[0]

    match = find_window_match("Spotify")

    if match is not None:
        return match[0]

    return None


def _window_title(hwnd):
    try:
        user32 = ctypes.WinDLL("user32")
        user32.GetWindowTextW.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPWSTR,
            ctypes.c_int,
        ]
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, 512)
        return buffer.value
    except Exception:
        return ""


def _launch_via_protocol(cancel_event=None):
    _raise_if_cancelled(cancel_event)
    os.startfile("spotify:")


def _launch_via_exe(cancel_event=None):
    _raise_if_cancelled(cancel_event)
    candidates = [
        os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Microsoft",
            "WindowsApps",
            "Spotify.exe",
        ),
    ]

    for candidate in candidates:
        _raise_if_cancelled(cancel_event)

        if candidate and os.path.isfile(candidate):
            subprocess.Popen([candidate], shell=False)
            return

    raise RuntimeError("Spotify.exe was not found.")


def _launch_via_store(cancel_event=None):
    _raise_if_cancelled(cancel_event)
    subprocess.Popen(
        [
            "explorer.exe",
            "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
        ],
        shell=False,
    )


def _launch_via_start_menu(cancel_event=None):
    completed = _run_cancellable_process(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-StartApps | Where-Object { $_.Name -like '*Spotify*' } "
            "| Select-Object -First 1).AppID",
        ],
        cancel_event=cancel_event,
        timeout=15,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    app_id = (completed.stdout or "").strip()

    if not app_id:
        raise RuntimeError("Spotify is not in the Start menu.")

    _raise_if_cancelled(cancel_event)
    subprocess.Popen(
        ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
        shell=False,
    )


def _ensure_spotify_window(cancel_event=None):
    _raise_if_cancelled(cancel_event)
    existing = _find_spotify_window()

    if existing is not None:
        return existing

    methods = (
        _launch_via_protocol,
        _launch_via_exe,
        _launch_via_store,
        _launch_via_start_menu,
    )

    for method in methods:
        _raise_if_cancelled(cancel_event)

        try:
            method(cancel_event)
        except _SpotifyCancelled:
            raise
        except Exception:
            continue

        deadline = time.monotonic() + 18

        while time.monotonic() < deadline:
            _raise_if_cancelled(cancel_event)
            hwnd = _find_spotify_window()

            if hwnd is not None:
                _wait_or_cancel(cancel_event, 2)
                return _find_spotify_window() or hwnd

            _wait_or_cancel(cancel_event, 0.5)

    return None


def _focus_spotify(cancel_event=None):
    _raise_if_cancelled(cancel_event)
    hwnd = _find_spotify_window()

    if hwnd is None:
        return None, "Could not find an open Spotify window."

    for attempt in range(5):
        _raise_if_cancelled(cancel_event)
        _force_foreground(hwnd)

        if attempt == 3:
            try:
                control_window("Spotify", "focus")
            except Exception:
                pass

        _wait_or_cancel(cancel_event, 0.35)
        hwnd = _find_spotify_window() or hwnd

        if _foreground_window() == int(hwnd):
            _wait_or_cancel(cancel_event, 0.3)
            return hwnd, ""

    return None, "Windows did not allow Spotify to take focus."


def _enter_search_query(query, cancel_event=None):
    _raise_if_cancelled(cancel_event)
    pyautogui.hotkey("ctrl", "a")

    if query.isascii():
        for character in query:
            _raise_if_cancelled(cancel_event)
            pyautogui.write(character, interval=0.02)

        return

    _raise_if_cancelled(cancel_event)
    previous_clipboard = pyperclip.paste()

    try:
        pyperclip.copy(query)
        _raise_if_cancelled(cancel_event)
        pyautogui.hotkey("ctrl", "v")
        _wait_or_cancel(cancel_event, 0.1)
    finally:
        pyperclip.copy(previous_clipboard)


def _open_search(query):
    os.startfile("spotify:search:" + urllib.parse.quote(query, safe=""))


def _type_search(hwnd, query, cancel_event=None):
    _ensure_spotify_foreground(hwnd, cancel_event)
    _raise_if_cancelled(cancel_event)
    pyautogui.hotkey("ctrl", "l")
    _wait_or_cancel(cancel_event, 0.4)
    _enter_search_query(query, cancel_event)
    _wait_or_cancel(cancel_event, 0.2)
    _raise_if_cancelled(cancel_event)
    pyautogui.press("enter")
    _wait_or_cancel(cancel_event, 1.2)


SECTION_NAMES = {
    "artists",
    "albums",
    "playlists",
    "episodes",
    "podcasts",
    "shows",
    "profiles",
    "audiobooks",
    "genresmoods",
}
HEADER_NAMES = SECTION_NAMES | {
    "songs",
    "song",
    "topresult",
    "popular",
    "title",
    "chapters",
    "tracks",
    "allepisodes",
}
LOADED_NAMES = {
    "topresult",
    "songs",
    "artists",
    "albums",
    "playlists",
    "audiobooks",
    "podcasts",
    "profiles",
}
GENERIC_TITLES = {"", "spotify", "spotifyfree", "spotifypremium"}
PAYMENT_LABELS = {
    "buy",
    "buynow",
    "purchase",
    "purchaseaudiobook",
    "buyaudiobook",
    "addtocart",
    "checkout",
}
PAYMENT_PHRASES = (
    "notincluded",
    "purchaserequired",
    "requirespurchase",
    "availabletopurchase",
    "buytolisten",
)
PREMIUM_PHRASES = (
    "getpremium",
    "upgradetopremium",
    "premiumonly",
    "listenwithpremium",
)
PRICE_PATTERN = re.compile(
    r"[$£€¥]\s?\d|\b\d{1,3}[.,]\d{2}\s?(?:usd|gbp|eur)\b",
    re.IGNORECASE,
)

PRICE_ONLY_PATTERN = re.compile(r"^\W?[A-Za-z]?\s?\d{1,3}[.,]\d{2}$")
BOOK_LENGTH_PATTERN = re.compile(r"\d+hr(\d+min)?")


class _PaymentRequired(Exception):
    pass


def _is_secondary_line(line, lines):
    for other in lines:
        if other is line:
            continue

        if _normalize_text(other["text"]) in HEADER_NAMES:
            continue

        if abs(other["x"] - line["x"]) > 14:
            continue

        gap = line["y"] - (other["y"] + other["height"])

        if -4 <= gap <= max(8, line["height"] * 0.5):
            return True

    return False


def _find_song_row(lines, query, window_bounds, search_field=None):
    left, top, width, height = window_bounds
    headers = [
        line
        for line in lines
        if (
            _normalize_text(line["text"]) in ("song", "songs")
            and line["x"] >= left + width * 0.12
            and line["y"] >= top + height * 0.12
        )
    ]
    usable = [line for line in lines if not _is_secondary_line(line, lines)]

    if headers:
        header = min(headers, key=lambda item: item["y"])
        column_x = header["x"] - 40
        start_y = header["y"] + header["height"]
        end_y = start_y + height * 0.5
        later = [
            line["y"]
            for line in lines
            if (
                _normalize_text(line["text"]) in SECTION_NAMES
                and line["y"] > start_y + 20
            )
        ]

        if later:
            end_y = min(end_y, min(later))

        rows = []

        for line in usable:
            if line["x"] < column_x or not start_y <= line["y"] < end_y:
                continue

            score = _track_match_score(line["text"], query)

            if score >= 0.68:
                rows.append((score, line))

        if rows:
            return min(
                rows,
                key=lambda item: (-item[0], item[1]["y"], item[1]["x"]),
            )[1]

        return None

    return _find_track_result(usable, query, window_bounds, search_field)


def _find_top_result(lines, query, window_bounds):
    left, top, width, height = window_bounds
    headers = [
        line
        for line in lines
        if (
            _normalize_text(line["text"]) == "topresult"
            and line["x"] >= left + width * 0.12
        )
    ]

    if not headers:
        return None

    header = min(headers, key=lambda item: item["y"])
    start_y = header["y"] + header["height"]
    end_y = start_y + height * 0.4
    max_x = header["x"] + width * 0.4
    candidates = []

    for line in lines:
        if line["x"] < header["x"] - 30 or line["x"] > max_x:
            continue

        if not start_y <= line["y"] < end_y:
            continue

        score = _track_match_score(line["text"], query)

        if score >= 0.68:
            candidates.append((score, line))

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: (-item[0], item[1]["y"], item[1]["x"]),
    )[1]


def _find_first_row(lines, window_bounds):
    left, top, width, height = window_bounds
    names = {"popular", "title", "chapters", "episodes", "allepisodes", "tracks"}
    headers = [
        line
        for line in lines
        if (
            _normalize_text(line["text"]) in names
            and line["x"] >= left + width * 0.12
            and line["y"] >= top + height * 0.15
        )
    ]

    if not headers:
        return None

    header = min(headers, key=lambda item: item["y"])
    start_y = header["y"] + header["height"]
    rows = []

    for line in lines:
        normalized = _normalize_text(line["text"])

        if not normalized or normalized.isdigit():
            continue

        if normalized in HEADER_NAMES:
            continue

        if line["x"] < header["x"] - 10 or line["x"] > header["x"] + width * 0.35:
            continue

        if not start_y <= line["y"] <= start_y + height * 0.4:
            continue

        if _is_secondary_line(line, lines):
            continue

        rows.append(line)

    if not rows:
        return None

    return min(rows, key=lambda item: (item["y"], item["x"]))


def _search_loaded(lines):
    return any(_normalize_text(line["text"]) in LOADED_NAMES for line in lines)


def _no_results(lines):
    for line in lines:
        normalized = _normalize_text(line["text"])

        if normalized.startswith("noresultsfound") or normalized.startswith(
            "couldntfind"
        ):
            return True

    return False


def _payment_message(lines, window_bounds, title):
    left, top, width, height = window_bounds
    is_book = False

    for line in lines:
        normalized = _normalize_text(line["text"])

        if (
            "narratedby" in normalized
            or BOOK_LENGTH_PATTERN.search(normalized)
            or (
                normalized.startswith("audiobook")
                and not normalized.startswith("audiobooks")
            )
        ):
            is_book = True
            break

    if not is_book:
        return None

    for line in lines:
        text = line["text"].strip()
        normalized = _normalize_text(text)

        if line["y"] < top + height * 0.08 or line["y"] > top + height * 0.88:
            continue

        shown = text if len(text) <= 60 else text[:57] + "..."

        if PRICE_ONLY_PATTERN.match(text):
            shown = "price " + re.sub(r"^\W?[A-Za-z]?\s?", "", text)

        if (
            PRICE_PATTERN.search(text)
            or PRICE_ONLY_PATTERN.match(text)
            or normalized in PAYMENT_LABELS
            or (
                len(normalized) <= 30
                and normalized.startswith(("buy", "purchase"))
            )
            or any(phrase in normalized for phrase in PAYMENT_PHRASES)
        ):
            return (
                f"'{title}' on Spotify requires a payment or purchase "
                f"(Spotify shows '{shown}'), so it was not played."
            )

        if any(phrase in normalized for phrase in PREMIUM_PHRASES):
            return (
                f"'{title}' on Spotify requires Spotify Premium or a "
                f"purchase (Spotify shows '{shown}'), so it was not played."
            )

    return None


def _raise_if_payment_required(hwnd, title, cancel_event=None):
    try:
        lines, bounds = _read_spotify_window(hwnd, cancel_event)
    except _SpotifyCancelled:
        raise
    except Exception:
        return

    message = _payment_message(lines, bounds, title)

    if message:
        raise _PaymentRequired(message)


def _click_line(hwnd, line, double=False, cancel_event=None):
    for _ in range(4):
        _raise_if_cancelled(cancel_event)

        try:
            _ensure_spotify_foreground(hwnd, cancel_event)
        except _SpotifyCancelled:
            raise
        except RuntimeError:
            _focus_spotify(cancel_event)
            continue

        if _belongs_to_window(line, hwnd):
            break

        _force_foreground(hwnd)
        _wait_or_cancel(cancel_event, 0.6)
    else:
        raise RuntimeError(
            "Spotify is being covered by another window, so nothing was "
            "clicked."
        )

    x = line["x"] + max(1, line["width"] // 2)
    y = line["y"] + max(1, line["height"] // 2)
    _raise_if_cancelled(cancel_event)
    pyautogui.moveTo(
        x,
        y,
        duration=0.5,
        tween=pyautogui.easeInOutQuad,
    )
    _raise_if_cancelled(cancel_event)

    if double:
        pyautogui.doubleClick(x=x, y=y, interval=0.1)
    else:
        pyautogui.click(x=x, y=y)


def _confirm_playback(
    hwnd,
    texts,
    title_before,
    timeout=10,
    cancel_event=None,
):
    wanted = [
        value
        for value in (_normalize_text(text) for text in texts)
        if value
    ]
    before = _normalize_text(title_before)
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        _raise_if_cancelled(cancel_event)
        title = _normalize_text(_window_title(hwnd))

        if title and title not in GENERIC_TITLES:
            if any(value in title for value in wanted):
                return True

            if title != before:
                return True

        _wait_or_cancel(cancel_event, 0.5)

    try:
        lines, bounds = _read_spotify_window(hwnd, cancel_event)
    except _SpotifyCancelled:
        raise
    except Exception:
        return False

    return any(
        _is_playing_result(lines, text, bounds) for text in texts if text
    )


def _type_search(hwnd, query, cancel_event=None):
    _ensure_spotify_foreground(hwnd, cancel_event)
    _raise_if_cancelled(cancel_event)
    pyautogui.hotkey("ctrl", "l")
    _wait_or_cancel(cancel_event, 0.4)
    _enter_search_query(query, cancel_event)
    _wait_or_cancel(cancel_event, 0.2)
    _raise_if_cancelled(cancel_event)
    pyautogui.press("enter")
    _wait_or_cancel(cancel_event, 1.2)


def _search_target(hwnd, query, cancel_event=None):
    loaded = 0

    for attempt in range(10):
        _raise_if_cancelled(cancel_event)

        if attempt:
            _wait_or_cancel(cancel_event, min(1.0 + attempt * 0.25, 2.5))

        if loaded == 0 and attempt in (2, 5, 8):
            try:
                if attempt == 5:
                    _raise_if_cancelled(cancel_event)
                    _open_search(query)
                    _wait_or_cancel(cancel_event, 1.5)
                else:
                    _type_search(hwnd, query, cancel_event)
            except _SpotifyCancelled:
                raise
            except Exception:
                pass

        lines, bounds = _read_spotify_window(hwnd, cancel_event)

        if _no_results(lines):
            return "none", None, f"Spotify found no results for '{query}'."

        song = _find_song_row(lines, query, bounds)

        if song is not None:
            return "song", song, ""

        if _search_loaded(lines):
            loaded += 1

            if loaded >= 2:
                item = _find_top_result(lines, query, bounds)

                if item is not None:
                    return "item", item, ""

    return (
        "none",
        None,
        f"Spotify did not show a matching result for '{query}'. "
        "Nothing was clicked.",
    )


def _play_row(hwnd, row, texts, locate, cancel_event=None):
    title_before = _window_title(hwnd)

    for attempt in range(3):
        _raise_if_cancelled(cancel_event)

        if attempt:
            lines, bounds = _read_spotify_window(hwnd, cancel_event)
            message = _payment_message(lines, bounds, row["text"])

            if message:
                raise _PaymentRequired(message)

            refreshed = locate(lines, bounds)

            if refreshed is not None:
                row = refreshed

        _click_line(hwnd, row, True, cancel_event)

        if _confirm_playback(
            hwnd,
            texts,
            title_before,
            cancel_event=cancel_event,
        ):
            return True, row

    return False, row


def _play_item(hwnd, item, query, cancel_event=None):
    _click_line(hwnd, item, False, cancel_event)
    row = None

    for _ in range(6):
        _wait_or_cancel(cancel_event, 1.4)
        lines, bounds = _read_spotify_window(hwnd, cancel_event)
        message = _payment_message(lines, bounds, item["text"])

        if message:
            return True, message

        row = _find_first_row(lines, bounds)

        if row is not None:
            break

    if row is None:
        return False, (
            f"Opened '{item['text']}' on Spotify, but could not find "
            "anything to play there."
        )

    played, row = _play_row(
        hwnd,
        row,
        [row["text"], item["text"], query],
        lambda current_lines, current_bounds: _find_first_row(
            current_lines,
            current_bounds,
        ),
        cancel_event,
    )

    if played:
        return True, f"Started playing '{item['text']}' on Spotify."

    lines, bounds = _read_spotify_window(hwnd, cancel_event)
    message = _payment_message(lines, bounds, item["text"])

    if message:
        return True, message

    return False, (
        f"Opened '{item['text']}' on Spotify, but could not verify that "
        "playback started. Check the Spotify player."
    )


def _play_once(query, cancel_event=None):
    _raise_if_cancelled(cancel_event)
    hwnd = _ensure_spotify_window(cancel_event)

    if hwnd is None:
        return True, (
            "Could not open Spotify. Check that it is installed and "
            "signed in."
        )

    hwnd, error = _focus_spotify(cancel_event)

    if hwnd is None:
        return False, error

    _raise_if_cancelled(cancel_event)
    pinned = hwnd
    _set_topmost(pinned, True)

    try:
        try:
            _raise_if_cancelled(cancel_event)
            _open_search(query)
            _wait_or_cancel(cancel_event, 1.5)
        except _SpotifyCancelled:
            raise
        except Exception:
            _type_search(hwnd, query, cancel_event)

        hwnd, error = _focus_spotify(cancel_event)

        if hwnd is None:
            return False, error

        kind, target, message = _search_target(hwnd, query, cancel_event)

        if kind == "none":
            return True, message

        if kind == "item":
            return _play_item(hwnd, target, query, cancel_event)

        played, row = _play_row(
            hwnd,
            target,
            [target["text"], query],
            lambda current_lines, current_bounds: _find_song_row(
                current_lines,
                query,
                current_bounds,
            ),
            cancel_event,
        )

        if played:
            _raise_if_payment_required(hwnd, row["text"], cancel_event)
            return True, f"Started playing '{row['text']}' on Spotify."

        return False, (
            f"Selected '{row['text']}' on Spotify, but could not verify "
            "that playback started. Check the Spotify player."
        )
    finally:
        _set_topmost(pinned, False)


def play_spotify_song(query, cancel_event=None):
    query = " ".join(str(query or "").split())

    if not query:
        return "No Spotify song supplied."

    last = "Spotify search and playback failed."

    for attempt in range(3):
        try:
            _raise_if_cancelled(cancel_event)
            final, message = _play_once(query, cancel_event)
        except _SpotifyCancelled:
            return "Action canceled."
        except _PaymentRequired as exc:
            return str(exc)
        except Exception as exc:
            final, message = False, f"Spotify search and playback failed: {exc}"

        if final:
            return message

        last = message
        if attempt < 2:
            try:
                _wait_or_cancel(cancel_event, 1.5)
            except _SpotifyCancelled:
                return "Action canceled."

    return last