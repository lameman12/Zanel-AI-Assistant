import ctypes
import ctypes.wintypes
import contextvars
import difflib
import os
import re
import tempfile
import time
import unicodedata
import urllib.parse
import webbrowser

import pyautogui

from zanelmodules.spotify import (
    _belongs_to_window,
    _enter_search_query,
    _force_foreground,
    _foreground_window,
    _normalize_text,
    _recognize_text,
    _set_topmost,
    _window_rectangle,
    _window_title,
)


YOUTUBE_URL = "https://www.youtube.com"
WIN32_WHEEL_DELTA = 120
RESULT_SCROLL_DELTA = -3 * WIN32_WHEEL_DELTA
TOP_SCROLL_DELTA = 10 * WIN32_WHEEL_DELTA
YOUTUBE_SEARCH_TIMEOUT = 25
MAX_STALLED_RESULT_SCROLLS = 3
YOUTUBE_LOCATE_TIMEOUT = 20
MAX_RESULT_SCROLLS = 60
EXACT_LOOKAHEAD_SCROLLS = 4
RESULT_SETTLE_DELAY = 3
RESULTS_PAGE_TIMEOUT = 10
CONSENT_MESSAGE = (
    "YouTube is showing a cookie consent prompt. Choose an option in the "
    "browser once, then ask again."
)
BROWSER_EXES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "chromium.exe",
    "arc.exe",
}
YOUTUBE_TITLE = re.compile(
    r"(?:^|\s[-\u2013\u2014]\s)(?:\(\d+\)\s*)?youtube(?:\s|$)"
)
HOME_TITLE = re.compile(
    r"^(?:\(\d+\)\s*)?youtube(?:\s+and\s+\d+\s+more\s+pages?)?"
    r"(?:\s[-\u2013\u2014]\s|$)"
)
CONSENT_TITLE = re.compile(r"before you continue")
BROWSER_URL_PATTERN = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}"
    r"(?:/[^\s]*)?"
)
DOMAIN_PATTERN = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}"
)
NOISE_PATTERNS = (
    re.compile(r"\bviews?\b"),
    re.compile(
        r"\b\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago\b"
    ),
    re.compile(r"\bsubscribers?\b"),
    re.compile(r"\bwatching\b"),
    re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$"),
    re.compile(r"^(?:sponsored|ad|new|live|cc|4k|hd)$"),
)
FILTER_LABELS = {
    "all",
    "shorts",
    "videos",
    "unwatched",
    "watched",
    "recentlyuploaded",
    "live",
    "music",
    "playlists",
    "channels",
    "filters",
    "today",
    "thisweek",
    "thismonth",
    "thisyear",
    "gaming",
    "news",
    "sport",
    "sports",
    "podcasts",
    "fromyoursearch",
    "peoplealsosearchfor",
    "peoplealsowatched",
    "previouslywatched",
}
AD_MARKER_LABELS = {
    "ad",
    "advertisement",
    "booknow",
    "learnmore",
    "paidpromotion",
    "promoted",
    "shopnow",
    "signup",
    "sponsored",
    "visitsite",
    "visitwebsite",
}
VIDEO_QUERY_STOP_WORDS = {
    "a",
    "an",
    "again",
    "for",
    "me",
    "on",
    "please",
    "play",
    "the",
    "video",
    "videos",
    "watch",
    "youtube",
}
SPONSORED_PREFIX = re.compile(
    r"^\s*(?:sponsored|promoted|advertisement|paid\s+promotion)"
    r"(?:\s+(?:by|result|listing|ad)\b|\s*[·•|:–—-])",
    re.IGNORECASE,
)
AD_PREFIX = re.compile(
    r"^\s*ad(?:\s+|$|[·•|:–—-])",
    re.IGNORECASE,
)


class _TabClosed(Exception):
    pass


class _Blocked(Exception):
    pass


class _NoResults(Exception):
    pass


class _NoOrganicResults(Exception):
    pass


class _Redirected(Exception):
    pass


class _YouTubeCancelled(Exception):
    pass


_CANCEL_EVENT = contextvars.ContextVar(
    "youtube_cancel_event",
    default=None,
)


def _raise_if_cancelled():
    cancel_event = _CANCEL_EVENT.get()

    if cancel_event is not None and cancel_event.is_set():
        raise _YouTubeCancelled("Action canceled.")


def _wait_or_cancel(seconds):
    _raise_if_cancelled()
    cancel_event = _CANCEL_EVENT.get()

    if cancel_event is None:
        time.sleep(seconds)
        return

    if cancel_event.wait(seconds):
        raise _YouTubeCancelled("Action canceled.")

    _raise_if_cancelled()


def _is_window(hwnd):
    try:
        user32 = ctypes.WinDLL("user32")
        user32.IsWindow.argtypes = [ctypes.wintypes.HWND]
        user32.IsWindow.restype = ctypes.wintypes.BOOL
        return bool(user32.IsWindow(hwnd))
    except Exception:
        return False


def _window_exe(hwnd):
    try:
        wintypes = ctypes.wintypes
        user32 = ctypes.WinDLL("user32")
        kernel32 = ctypes.WinDLL("kernel32")
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
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
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        handle = kernel32.OpenProcess(0x1000, False, process_id.value)

        if not handle:
            return ""

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
            return ""

        return os.path.basename(buffer.value).lower()
    except Exception:
        return ""


def _list_youtube_windows():
    wintypes = ctypes.wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    found = []

    def callback(hwnd, lparam):
        try:
            if user32.IsWindowVisible(hwnd):
                title = _window_title(hwnd)
                lowered = title.lower()

                if title and (
                    YOUTUBE_TITLE.search(lowered)
                    or CONSENT_TITLE.search(lowered)
                ):
                    if _window_exe(hwnd) in BROWSER_EXES:
                        found.append((int(hwnd), title))
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
    return found


def _has_youtube(hwnd):
    if not _is_window(hwnd):
        return False

    lowered = _window_title(hwnd).lower()
    return bool(
        YOUTUBE_TITLE.search(lowered) or CONSENT_TITLE.search(lowered)
    )


def _ensure_tab(hwnd, grace=6):
    deadline = time.time() + grace

    while True:
        _raise_if_cancelled()

        if not _is_window(hwnd):
            raise _TabClosed()

        if _has_youtube(hwnd):
            return

        if time.time() >= deadline:
            raise _TabClosed()

        _wait_or_cancel(0.4)

def _focus_window(hwnd):
    for attempt in range(6):
        _raise_if_cancelled()

        if not _is_window(hwnd):
            raise _TabClosed()

        if _foreground_window() == int(hwnd):
            return

        _force_foreground(hwnd)
        _wait_or_cancel(0.4 + attempt * 0.1)

    raise RuntimeError("Windows would not bring the browser to the front.")


def _capture(hwnd):
    _raise_if_cancelled()
    screen_width, screen_height = pyautogui.size()
    window_left, window_top, window_right, window_bottom = _window_rectangle(
        hwnd
    )
    left = max(0, window_left)
    top = max(0, window_top)
    right = min(screen_width, window_right)
    bottom = min(screen_height, window_bottom)

    if right - left < 300 or bottom - top < 300:
        raise RuntimeError(
            "The browser window is not visible on the primary display."
        )

    image = pyautogui.screenshot(
        region=(left, top, right - left, bottom - top)
    )
    file_descriptor, image_path = tempfile.mkstemp(suffix=".png")
    os.close(file_descriptor)

    try:
        image.save(image_path, format="PNG")
        lines = _recognize_text(image_path, _CANCEL_EVENT.get())
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    for line in lines:
        line["x"] += left
        line["y"] += top

    visible = [line for line in lines if _belongs_to_window(line, hwnd)]

    if lines and not visible:
        raise RuntimeError("Another window is covering the browser.")

    return visible, (left, top, right - left, bottom - top)


def _read(hwnd):
    last = None

    for attempt in range(6):
        _raise_if_cancelled()

        try:
            _ensure_tab(hwnd)
            _focus_window(hwnd)
            _wait_or_cancel(0.25)
            lines, bounds = _capture(hwnd)

            if _foreground_window() == int(hwnd):
                return lines, bounds

            last = RuntimeError(
                "The browser did not stay in front long enough to read "
                "the page."
            )
        except (_TabClosed, _YouTubeCancelled):
            raise
        except Exception as exc:
            last = exc

        _wait_or_cancel(0.6 + attempt * 0.3)

    raise RuntimeError(str(last))


def _click_line(hwnd, line):
    for _ in range(4):
        _raise_if_cancelled()
        _focus_window(hwnd)

        if _belongs_to_window(line, hwnd):
            break

        _wait_or_cancel(0.6)
    else:
        raise RuntimeError(
            "Another window is covering the browser, so nothing was clicked."
        )

    x = line["x"] + max(1, line["width"] // 2)
    y = line["y"] + max(1, line["height"] // 2)
    _raise_if_cancelled()
    pyautogui.moveTo(
        x,
        y,
        duration=0.5,
        tween=pyautogui.easeInOutQuad,
    )
    _raise_if_cancelled()
    pyautogui.click(x=x, y=y)

def _open_youtube():
    _raise_if_cancelled()

    try:
        opened = webbrowser.open(YOUTUBE_URL, new=2)
    except Exception:
        opened = False

    _raise_if_cancelled()

    if not opened:
        os.startfile(YOUTUBE_URL)

    deadline = time.time() + 30
    fallback = None

    while time.time() < deadline:
        _raise_if_cancelled()
        windows = _list_youtube_windows()

        for hwnd, title in windows:
            lowered = title.lower()

            if HOME_TITLE.search(lowered) or CONSENT_TITLE.search(lowered):
                _wait_or_cancel(2)

                if _has_youtube(hwnd):
                    return hwnd

        if windows:
            fallback = windows[0][0]

        _wait_or_cancel(0.5)

    if fallback is not None and _has_youtube(fallback):
        _wait_or_cancel(2)
        return fallback

    raise RuntimeError("YouTube did not open in a browser within 30 seconds.")


def _consent_visible(lines):
    for line in lines:
        normalized = _normalize_text(line["text"])

        if "beforeyoucontinue" in normalized:
            return True

        if normalized in ("acceptall", "rejectall"):
            return True

    return False


def _no_results(lines):
    return any(
        _normalize_text(line["text"]).startswith("noresultsfound")
        for line in lines
    )


def _find_search_box(lines, window_bounds):
    left, top, width, height = window_bounds
    candidates = []

    for line in lines:
        normalized = _normalize_text(line["text"])

        if normalized not in {"search", "searchyoutube"}:
            continue

        center_x = (line["x"] + line["width"] / 2 - left) / width
        center_y = (line["y"] + line["height"] / 2 - top) / height

        if not 0.2 <= center_x <= 0.88 or not 0.1 <= center_y <= 0.3:
            continue

        candidates.append((abs(center_x - 0.5) + abs(center_y - 0.12), line))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def _extract_browser_url(lines, window_bounds):
    _, top, _, height = window_bounds
    candidates = []

    for line in lines:
        center_y = line["y"] + line["height"] / 2

        if not top <= center_y <= top + height * 0.2:
            continue

        text = line["text"].replace(" ", "")
        match = BROWSER_URL_PATTERN.search(text)

        if match is None:
            continue

        address = match.group(0).rstrip(".,)")

        if not address.lower().startswith(("http://", "https://")):
            address = "https://" + address

        parsed = urllib.parse.urlparse(address)

        if parsed.hostname:
            candidates.append((center_y, address))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def _read_browser_url(hwnd):
    _raise_if_cancelled()
    _focus_window(hwnd)

    if _foreground_window() != int(hwnd):
        raise RuntimeError("The browser lost focus before its URL was read.")

    pyautogui.hotkey("ctrl", "l")
    _wait_or_cancel(0.25)

    try:
        lines, bounds = _capture(hwnd)
    finally:
        if _foreground_window() == int(hwnd):
            pyautogui.press("esc")

    address = _extract_browser_url(lines, bounds)

    if address is None:
        raise RuntimeError("Could not read the active browser tab's URL.")

    return address


def _is_youtube_url(address):
    host = (urllib.parse.urlparse(address).hostname or "").lower().rstrip(".")
    return (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtu.be"
    )


def _assert_active_youtube_tab(hwnd, lines=None, bounds=None):
    _raise_if_cancelled()

    if not _is_window(hwnd):
        raise _TabClosed()

    if lines is not None and bounds is not None:
        address = _extract_browser_url(lines, bounds)

        if address and not _is_youtube_url(address):
            raise _Redirected(
                urllib.parse.urlparse(address).hostname or address
            )

    if not _has_youtube(hwnd):
        raise _Redirected("a non-YouTube page")


def _guard_site(hwnd):
    _raise_if_cancelled()
    _focus_window(hwnd)
    lines, bounds = _capture(hwnd)
    _assert_active_youtube_tab(hwnd, lines, bounds)


def _submit_search(hwnd, query):
    box = None

    for _ in range(4):
        _raise_if_cancelled()
        lines, bounds = _read(hwnd)

        if _consent_visible(lines):
            raise _Blocked(CONSENT_MESSAGE)

        box = _find_search_box(lines, bounds)

        if box is not None:
            break

        _wait_or_cancel(1.2)

    if box is None:
        address = _read_browser_url(hwnd)

        if not _is_youtube_url(address):
            raise RuntimeError(
                "YouTube's search field was not identified and the active "
                "page is not verified as YouTube; nothing was typed."
            )

        _focus_window(hwnd)
        pyautogui.press("/")
        _wait_or_cancel(0.2)
    else:
        _click_line(hwnd, box)

    _wait_or_cancel(0.4)
    _guard_site(hwnd)
    _enter_search_query(query, _CANCEL_EVENT.get())
    _wait_or_cancel(0.2)
    _raise_if_cancelled()
    pyautogui.press("enter")
    _wait_or_cancel(0.5)


def _is_metadata_line(line, lines):
    for other in lines:
        if other is line:
            continue

        if abs(other["x"] - line["x"]) > 16:
            continue

        gap = line["y"] - (other["y"] + other["height"])

        if -4 <= gap <= max(10, line["height"]):
            if other["height"] > line["height"] * 1.12:
                return True

    return False


def _is_ad_marker(line):
    text = line["text"].strip()
    normalized = _normalize_text(text)

    return (
        normalized in AD_MARKER_LABELS
        or bool(SPONSORED_PREFIX.search(text))
        or bool(AD_PREFIX.search(text))
        or bool(DOMAIN_PATTERN.fullmatch(text.replace(" ", "")))
    )


def _is_sponsored_result(line, lines):
    center_y = line["y"] + line["height"] / 2

    for marker in lines:
        if marker is line or not _is_ad_marker(marker):
            continue

        marker_center_y = marker["y"] + marker["height"] / 2
        vertical_distance = abs(center_y - marker_center_y)
        same_row = vertical_distance <= max(
            48,
            line["height"] * 2,
            marker["height"] * 2,
        )
        same_column = abs(marker["x"] - line["x"]) <= max(
            120,
            line["width"] * 0.3,
        )

        if vertical_distance <= 110 and (same_row or same_column):
            return True

    return False


def _fold_text(text):
    decomposed = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return "".join(char for char in decomposed if char.isalnum())


def _exact_key(text):
    return " ".join(
        unicodedata.normalize("NFKC", str(text or "")).casefold().split()
    )


def _trim_query(query):
    words = query.split()

    while words and _fold_text(words[0]) in VIDEO_QUERY_STOP_WORDS:
        words.pop(0)

    while words and _fold_text(words[-1]) in VIDEO_QUERY_STOP_WORDS:
        words.pop()

    return " ".join(words) or query


def _match_tier(text, query):
    exact_text = _exact_key(text)
    folded_text = _fold_text(text)
    best = 1

    for option in (query, _trim_query(query)):
        if exact_text == _exact_key(option):
            return 3

        if folded_text and folded_text == _fold_text(option):
            best = 2

    return best


def _raw_similarity(text, query):
    exact_text = _exact_key(text)

    return max(
        difflib.SequenceMatcher(None, exact_text, _exact_key(option)).ratio()
        for option in (query, _trim_query(query))
    )


def _video_query_words(query):
    all_words = [
        _fold_text(word)
        for word in query.split()
        if _fold_text(word)
    ]
    words = [
        word for word in all_words if word not in VIDEO_QUERY_STOP_WORDS
    ]

    return words or all_words


def _one_character_apart(first, second):
    if abs(len(first) - len(second)) > 1:
        return False

    if len(first) == len(second):
        return sum(a != b for a, b in zip(first, second)) == 1

    shorter, longer = sorted((first, second), key=len)
    short_index = 0
    long_index = 0
    differences = 0

    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue

        differences += 1
        long_index += 1

        if differences > 1:
            return False

    return True


def _video_match_score(text, query):
    query_words = _video_query_words(query)
    all_text_words = [
        _fold_text(word)
        for word in text.split()
        if _fold_text(word)
    ]
    text_words = [
        word
        for word in all_text_words
        if word not in VIDEO_QUERY_STOP_WORDS
    ] or all_text_words

    if not query_words or not text_words:
        return 0.0

    scores = [
        [0.0] * (len(text_words) + 1)
        for _ in range(len(query_words) + 1)
    ]

    for query_index, query_word in enumerate(query_words, start=1):
        for text_index, text_word in enumerate(text_words, start=1):
            similarity = 0.0

            if query_word == text_word:
                similarity = 1.0
            elif (
                min(len(query_word), len(text_word)) >= 3
                and not query_word.isdigit()
                and not text_word.isdigit()
                and _one_character_apart(query_word, text_word)
            ):
                if len(query_word) == len(text_word):
                    similarity = (len(query_word) - 1) / len(query_word)
                else:
                    similarity = (
                        min(len(query_word), len(text_word))
                        / max(len(query_word), len(text_word))
                    )
            elif min(len(query_word), len(text_word)) >= 4:
                similarity = difflib.SequenceMatcher(
                    None,
                    query_word,
                    text_word,
                ).ratio()

                if similarity < 0.72:
                    similarity = 0.0

            scores[query_index][text_index] = max(
                scores[query_index - 1][text_index],
                scores[query_index][text_index - 1],
                scores[query_index - 1][text_index - 1] + similarity,
            )

    matched = scores[-1][-1]

    if matched == 0:
        return 0.0

    recall = matched / len(query_words)
    precision = matched / len(text_words)
    return 2 * precision * recall / (precision + recall)


def _results_top(lines, window_bounds):
    left, top, width, height = window_bounds
    bottoms = []

    for line in lines:
        if _normalize_text(line["text"]) not in FILTER_LABELS:
            continue

        center_x = (line["x"] + line["width"] / 2 - left) / width
        center_y = (line["y"] + line["height"] / 2 - top) / height

        if 0.12 <= center_x <= 0.95 and 0.12 <= center_y <= 0.3:
            bottoms.append(line["y"] + line["height"])

    if not bottoms:
        return top + height * 0.2

    return min(
        max(max(bottoms) + 2, top + height * 0.15),
        top + height * 0.3,
    )


def _find_videos(lines, query, window_bounds):
    left, top, width, height = window_bounds
    cutoff = _results_top(lines, window_bounds)
    region = [
        line
        for line in lines
        if line["y"] >= cutoff
    ]
    candidates = []

    for line in region:
        text = line["text"].strip()
        normalized = _normalize_text(text)
        center_x = (line["x"] + line["width"] / 2 - left) / width

        if (
            len(normalized) < 3
            or not 0.12 <= center_x <= 0.92
            or normalized in FILTER_LABELS
            or normalized.startswith(("searchresultsfor", "resultsfor"))
            or _is_ad_marker(line)
            or DOMAIN_PATTERN.search(text)
            or _is_sponsored_result(line, lines)
        ):
            continue

        lowered = text.lower()

        if any(pattern.search(lowered) for pattern in NOISE_PATTERNS):
            continue

        if _is_metadata_line(line, region):
            continue

        score = _video_match_score(text, query)

        candidates.append((score, line))

    return sorted(
        candidates,
        key=lambda item: (-item[0], item[1]["y"], item[1]["x"]),
    )[:50]


def _find_video(lines, query, window_bounds):
    candidates = _find_videos(lines, query, window_bounds)
    return candidates[0][1] if candidates else None


def _result_signature(lines, bounds):
    _, top, _, height = bounds
    return tuple(
        (
            _normalize_text(line["text"]),
            round((line["y"] + line["height"] / 2 - top) / height, 3),
        )
        for _, line in _find_videos(lines, "", bounds)
    )


def _scroll_results(hwnd, bounds, amount=RESULT_SCROLL_DELTA, delay=0.25):
    _raise_if_cancelled()
    _focus_window(hwnd)
    left, top, width, height = bounds
    _raise_if_cancelled()
    pyautogui.moveTo(
        left + width // 2,
        top + int(height * 0.6),
        duration=0.3,
    )
    pyautogui.scroll(
        amount,
        x=left + width // 2,
        y=top + int(height * 0.6),
    )
    _wait_or_cancel(delay)


def _scroll_results_to_top(hwnd, bounds, deadline):
    _raise_if_cancelled()
    _focus_window(hwnd)
    left, top, width, height = bounds
    pyautogui.moveTo(
        left + width // 2,
        top + int(height * 0.6),
        duration=0.2,
    )

    lines, bounds = _read(hwnd)
    _assert_active_youtube_tab(hwnd, lines, bounds)
    previous_signature = _result_signature(lines, bounds)

    while time.monotonic() < deadline:
        _raise_if_cancelled()
        _assert_active_youtube_tab(hwnd)
        pyautogui.scroll(
            TOP_SCROLL_DELTA,
            x=left + width // 2,
            y=top + int(height * 0.6),
        )
        _wait_or_cancel(0.15)
        lines, bounds = _read(hwnd)
        _assert_active_youtube_tab(hwnd, lines, bounds)
        signature = _result_signature(lines, bounds)

        if signature == previous_signature:
            return lines, bounds

        previous_signature = signature

    return None


def _locate_video(hwnd, query, target, bounds, deadline):
    _raise_if_cancelled()
    located = _scroll_results_to_top(hwnd, bounds, deadline)

    if located is None:
        return None

    lines, bounds = located
    previous_signature = None
    stalled_scrolls = 0

    while True:
        _raise_if_cancelled()
        _assert_active_youtube_tab(hwnd, lines, bounds)

        if _consent_visible(lines):
            raise _Blocked(CONSENT_MESSAGE)

        if _no_results(lines):
            raise _NoResults()

        for _, line in _find_videos(lines, query, bounds):
            if _exact_key(line["text"]) == target:
                return line

        if time.monotonic() >= deadline:
            return None

        signature = _result_signature(lines, bounds)

        if signature == previous_signature:
            stalled_scrolls += 1

            if stalled_scrolls >= MAX_STALLED_RESULT_SCROLLS:
                break
        else:
            stalled_scrolls = 0

        previous_signature = signature

        if time.monotonic() >= deadline:
            return None

        _scroll_results(hwnd, bounds)
        lines, bounds = _read(hwnd)
        _assert_active_youtube_tab(hwnd, lines, bounds)

    return None


def _wait_for_results_page(hwnd):
    deadline = time.monotonic() + RESULTS_PAGE_TIMEOUT

    while time.monotonic() < deadline:
        _raise_if_cancelled()
        _ensure_tab(hwnd)

        if not HOME_TITLE.search(_window_title(hwnd).lower()):
            return

        _wait_or_cancel(0.4)


def _initial_read(hwnd):
    _raise_if_cancelled()
    _wait_for_results_page(hwnd)
    _wait_or_cancel(RESULT_SETTLE_DELAY)
    _assert_active_youtube_tab(hwnd)
    return _read(hwnd)


def _choose_video(hwnd, query):
    _raise_if_cancelled()
    records = {}
    viewport_number = 0
    stalled_scrolls = 0
    lookahead_left = None
    lines, bounds = _initial_read(hwnd)
    deadline = time.monotonic() + YOUTUBE_SEARCH_TIMEOUT
    previous_signature = None

    while True:
        _raise_if_cancelled()
        viewport_number += 1

        _assert_active_youtube_tab(hwnd, lines, bounds)

        if _consent_visible(lines):
            raise _Blocked(CONSENT_MESSAGE)

        if _no_results(lines):
            raise _NoResults()

        for score, line in _find_videos(lines, query, bounds):
            key = _exact_key(line["text"])
            tier = _match_tier(line["text"], query)
            similarity = _raw_similarity(line["text"], query)

            if tier >= 2:
                score = max(score, 1.0)

            record = records.get(key)

            if record is None:
                records[key] = {
                    "tier": tier,
                    "score": score,
                    "similarity": similarity,
                    "text": line["text"],
                    "seen": 1,
                    "first_view": viewport_number,
                    "first_y": line["y"],
                }
            else:
                record["tier"] = max(record["tier"], tier)
                record["score"] = max(record["score"], score)
                record["similarity"] = max(record["similarity"], similarity)
                record["seen"] += 1

                if len(line["text"]) < len(record["text"]):
                    record["text"] = line["text"]

            if tier == 3:
                return line

            if (tier == 2 or score >= 1.0) and lookahead_left is None:
                lookahead_left = EXACT_LOOKAHEAD_SCROLLS

        if lookahead_left is not None:
            if lookahead_left <= 0:
                break

            lookahead_left -= 1

        if time.monotonic() >= deadline:
            break

        if viewport_number > MAX_RESULT_SCROLLS:
            break

        signature = _result_signature(lines, bounds)

        if signature == previous_signature:
            stalled_scrolls += 1

            if stalled_scrolls >= MAX_STALLED_RESULT_SCROLLS:
                break
        else:
            stalled_scrolls = 0

        previous_signature = signature
        _scroll_results(hwnd, bounds)
        lines, bounds = _read(hwnd)
        _assert_active_youtube_tab(hwnd, lines, bounds)

    if not records:
        return None

    ranked = sorted(
        records.items(),
        key=lambda item: (
            -item[1]["tier"],
            -item[1]["score"],
            -item[1]["similarity"],
            -item[1]["seen"],
            item[1]["first_view"],
            item[1]["first_y"],
            len(item[1]["text"]),
            item[0],
        ),
    )
    target = ranked[0][0]

    for _, line in _find_videos(lines, query, bounds):
        if _exact_key(line["text"]) == target:
            return line

    return _locate_video(
        hwnd,
        query,
        target,
        bounds,
        time.monotonic() + YOUTUBE_LOCATE_TIMEOUT,
    )


def _is_youtube_video_url(address):
    parsed = urllib.parse.urlparse(address)

    if not _is_youtube_url(address):
        return False

    if parsed.hostname and parsed.hostname.lower().endswith("youtu.be"):
        return bool(parsed.path.strip("/"))

    path = parsed.path.rstrip("/")
    return (
        path == "/watch"
        and bool(urllib.parse.parse_qs(parsed.query).get("v"))
    ) or path.startswith("/shorts/")


def _video_page_title(lines, bounds, query):
    left, top, width, height = bounds
    candidates = []

    for line in lines:
        center_x = (line["x"] + line["width"] / 2 - left) / width
        center_y = (line["y"] + line["height"] / 2 - top) / height

        if not 0.02 <= center_x <= 0.76 or not 0.5 <= center_y <= 0.82:
            continue

        score = _video_match_score(line["text"], query)

        if score >= 2 / 3:
            candidates.append((score, line["text"]))

    if not candidates:
        return None

    return max(candidates, key=lambda item: item[0])[1]


def _wait_for_video(hwnd, query, timeout=12):
    attempts = max(1, min(4, int(timeout / 3)))
    address = ""
    opened_video_address = None

    for attempt in range(attempts):
        _raise_if_cancelled()

        if not _is_window(hwnd):
            raise _TabClosed()

        address = _read_browser_url(hwnd)

        if not _is_youtube_url(address):
            return "external", address

        if _is_youtube_video_url(address):
            lines, bounds = _capture(hwnd)
            title = _video_page_title(lines, bounds, query)

            if title:
                return "playing", title

            opened_video_address = address

        elif urllib.parse.urlparse(address).path.rstrip("/") != "/results":
            return "other", address

        if attempt + 1 < attempts:
            _wait_or_cancel(min(1.0, timeout / attempts))

    if opened_video_address:
        return "other", opened_video_address

    return "unchanged", address


def _play_once(query):
    _raise_if_cancelled()
    hwnd = _open_youtube()
    _focus_window(hwnd)
    _set_topmost(hwnd, True)
    clicked = False
    terminal_message = None

    try:
        if CONSENT_TITLE.search(_window_title(hwnd).lower()):
            raise _Blocked(CONSENT_MESSAGE)

        _raise_if_cancelled()
        _submit_search(hwnd, query)
        video = _choose_video(hwnd, query)

        if video is None:
            raise _NoOrganicResults(
                f"No clear match for '{query}' was found on YouTube, so "
                "nothing was clicked."
            )

        _guard_site(hwnd)
        clicked = True

        try:
            _click_line(hwnd, video)
            _raise_if_cancelled()
            outcome, page_info = _wait_for_video(
                hwnd,
                query,
            )
        except _YouTubeCancelled:
            raise
        except _TabClosed:
            terminal_message = (
                "The YouTube tab was closed before the video could be "
                "confirmed."
            )
        except Exception as exc:
            terminal_message = (
                "A video was clicked, but it could not be confirmed that it "
                f"opened ({exc})."
            )
        else:
            if outcome == "playing":
                terminal_message = (
                    f"Started playing '{page_info}' on YouTube."
                )
            elif outcome == "external":
                host = urllib.parse.urlparse(page_info).hostname or page_info
                terminal_message = (
                    f"The clicked result opened {host} instead of a "
                    "YouTube video. It may have been an ad."
                )
            elif outcome == "unchanged":
                terminal_message = (
                    "A result was clicked, but the page did not change to "
                    "a video."
                )
            else:
                if _is_youtube_video_url(page_info):
                    terminal_message = (
                        f"Opened '{video['text'].strip()}' on YouTube, but "
                        "it may not be the video requested."
                    )
                else:
                    terminal_message = (
                        "Opened a YouTube page, but could not verify it "
                        "matched your request."
                    )
    finally:
        try:
            _set_topmost(hwnd, False)
        except Exception as exc:
            if not clicked:
                raise

            terminal_message = (
                f"{terminal_message} The browser window also could not be "
                f"put back to normal: {exc}"
            )

    return True, terminal_message


def play_youtube_video(query, cancel_event=None):
    query = " ".join(str(query or "").split())

    if not query:
        return "No YouTube video supplied."

    token = _CANCEL_EVENT.set(cancel_event)

    try:
        _raise_if_cancelled()
        _, message = _play_once(query)
        return message
    except _YouTubeCancelled:
        return "Action canceled."
    except _Blocked as exc:
        return str(exc)
    except _NoResults:
        return f"YouTube found no results for '{query}'."
    except _NoOrganicResults as exc:
        return str(exc)
    except _Redirected as exc:
        return (
            f"The browser left YouTube (now on {exc}), so the action was "
            "stopped."
        )
    except _TabClosed:
        return "The YouTube tab was closed or changed before the video started."
    except Exception as exc:
        return f"YouTube playback failed: {exc}"
    finally:
        _CANCEL_EVENT.reset(token)