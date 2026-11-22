import json
import os
import difflib
import shutil
import subprocess
import time
import webbrowser
import urllib.request
import ctypes.wintypes
import pyautogui
import pyperclip
import re
from datetime import datetime
import ctypes
import sys
import numpy as np
from zanelmodules.animations import confetti_animation, flip_coin_animation, roll_dice_animation
from zanelmodules.apps import (
    closest_entry,
    find_installed_apps,
    find_winget,
    normalize_app_text,
    run_winget,
    uninstall_via_appx,
    uninstall_via_registry,
    uninstall_via_winget,
    winget_candidates,
    winget_is_installed,
    winget_publisher,
    winget_tail,
)
from zanelmodules.config import ALLOW_SHELL_COMMANDS, WINGET_ALREADY_INSTALLED
from zanelmodules.dialogs import ask_local_confirmation
from zanelmodules.files import (
    cleanup_leftovers,
    clear_read_only,
    describe_item,
    permanent_delete,
    protected_reason,
    search_local_items,
    send_to_recycle_bin,
)
from zanelmodules.resources import resource_path
from zanelmodules.spotify import play_spotify_song
from zanelmodules.youtube import play_youtube_video
from zanelmodules.windows_ctl import (
    application_is_running,
    connect_bluetooth_device,
    control_window,
    find_window_match,
    find_rickroll_process,
    get_process_snapshot,
    run_on_main,
    set_bluetooth_state,
)


def _wait_for_action(cancel_event, seconds):
    if cancel_event is None:
        time.sleep(seconds)
        return False

    return cancel_event.wait(seconds)


def execute_action(action, root, mic_callback, app=None, cancel_event=None):
    cancel_event = cancel_event or getattr(app, "current_cancel_event", None)

    if cancel_event is not None and cancel_event.is_set():
        return "Action canceled."

    if not isinstance(action, dict):
        return "Invalid action."

    name = str(
        action.get("action", "none")
    ).lower().strip()

    if name == "none":
        return "No local action requested."

    if name == "open_url":
        url = str(
            action.get("url", "")
        ).strip()

        if not (
            url.startswith("https://")
            or url.startswith("http://")
        ):
            return (
                "Blocked: only HTTP and HTTPS URLs "
                "are allowed."
            )

        if not ask_local_confirmation(
            root,
            "Zanel wants to open a website",
            f"Allow Zanel to open:\n\n{url}",
        ):
            return "User declined opening the URL."

        try:
            webbrowser.open(url)
            return f"Opened {url}"
        except Exception as exc:
            return f"Could not open URL: {exc}"

    if name in (
        "flip_coin",
        "coin_flip",
        "flip_a_coin",
        "flip_the_coin",
    ):
        try:
            return run_on_main(
                root,
                lambda: flip_coin_animation(root),
            ) or "The coin flip finished."

        except Exception as exc:
            return (
                f"Could not flip the coin: "
                f"{exc}"
            )

    if name in (
        "roll_dice",
        "roll_a_dice",
        "roll_the_dice",
        "dice_roll",
        "throw_dice",
        "throw_a_dice",
    ):
        try:
            return run_on_main(
                root,
                lambda: roll_dice_animation(root),
            ) or "The dice roll finished."

        except Exception as exc:
            return (
                f"Could not roll the dice: "
                f"{exc}"
            )

    if name in (
        "confetti",
        "confetti_spray",
        "celebrate",
        "celebration",
        "party",
        "party_mode",
    ):
        try:
            if not ask_local_confirmation(
                root,
                "Zanel wants to launch confetti",
                "Allow Zanel to launch the confetti celebration?",
            ):
                return "User declined the confetti celebration."

            return confetti_animation(root)

        except Exception as exc:
            return (
                f"Could not launch the confetti: "
                f"{exc}"
            )

    if name in (
        "rickroll",
        "rick_roll",
        "rick_roll_video",
    ):
        if app is None:
            return "Could not play the Rickroll."

        try:
            with app.rickroll_lock:
                if app.rickroll_process is not None:
                    kernel32 = ctypes.windll.kernel32

                    process_handle = kernel32.OpenProcess(
                        0x1000,
                        False,
                        app.rickroll_process,
                    )

                    if process_handle:
                        exit_code = ctypes.c_ulong()

                        queried = kernel32.GetExitCodeProcess(
                            process_handle,
                            ctypes.byref(exit_code),
                        )

                        kernel32.CloseHandle(
                            process_handle
                        )

                        if queried and exit_code.value == 259:
                            return (
                                "A Rickroll is already playing."
                            )

                    app.rickroll_process = None

                video_path = resource_path("rickroll.mp4")

                if not os.path.isfile(video_path):
                    return (
                        "Could not play the Rickroll because "
                        "the bundled rickroll.mp4 file was not found."
                    )

                if not ask_local_confirmation(
                    root,
                    "Zanel wants to play a Rickroll",
                    "Allow Zanel to play the Rickroll video?",
                ):
                    return "User declined the Rickroll."

                before = get_process_snapshot()

                os.startfile(
                    video_path
                )

                pid = find_rickroll_process(
                    before
                )

                if pid is None:
                    return (
                        "Rickroll video opened, but Zanel could not "
                        "track the media player process."
                    )

                app.rickroll_process = pid

                return "Rickroll video opened."

        except Exception as exc:
            app.rickroll_process = None

            return (
                f"Could not play the Rickroll: {exc}"
            )

    if name == "open_app":
        program = str(
            action.get("program")
            or action.get("app_name")
            or action.get("app")
            or action.get("name")
            or ""
        ).strip()

        if not program:
            return "No application supplied."

        try:
            if os.path.isfile(program):
                if not ask_local_confirmation(
                    root,
                    "Zanel wants to open an application",
                    f"Allow Zanel to launch:\n\n{program}",
                ):
                    return (
                        "User declined the "
                        "application launch."
                    )

                subprocess.Popen(
                    [program],
                    shell=False,
                )

                program_name = os.path.splitext(
                    os.path.basename(program)
                )[0]

                for _ in range(20):
                    if _wait_for_action(cancel_event, 0.5):
                        return "Action canceled."

                    if application_is_running(
                        program_name
                    ):
                        return f"Launched {program}."

                return (
                    f"Launch command was sent for "
                    f"{program}, but Zanel could not "
                    f"confirm that it opened."
                )

            start_apps_result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-StartApps | "
                    "ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            apps = []

            if start_apps_result.returncode == 0:
                try:
                    data = json.loads(
                        start_apps_result.stdout
                    )

                    if isinstance(data, dict):
                        data = [data]

                    if isinstance(data, list):
                        apps = [
                            app
                            for app in data
                            if (
                                isinstance(app, dict)
                                and app.get("Name")
                                and app.get("AppID")
                            )
                        ]

                except (
                    json.JSONDecodeError,
                    TypeError,
                    ValueError,
                ):
                    apps = []

            requested = program.lower().strip()

            requested_clean = "".join(
                character
                for character in requested
                if character.isalnum()
                or character == " "
            )

            requested_words = set(
                requested_clean.split()
            )

            scored = []

            for app in apps:
                app_name = str(
                    app.get("Name", "")
                ).strip()

                app_clean = "".join(
                    character
                    for character in app_name.lower()
                    if character.isalnum()
                    or character == " "
                )

                app_words = set(
                    app_clean.split()
                )

                ratio = difflib.SequenceMatcher(
                    None,
                    requested_clean,
                    app_clean,
                ).ratio()

                word_score = 0.0

                if requested_words and app_words:
                    overlap = requested_words.intersection(
                        app_words
                    )

                    word_score = (
                        len(overlap)
                        / len(requested_words)
                    )

                if (
                    requested_clean
                    and requested_clean in app_clean
                ):
                    ratio = max(
                        ratio,
                        0.95,
                    )

                score = max(
                    ratio,
                    word_score,
                )

                scored.append(
                    (
                        score,
                        app_name,
                        str(
                            app.get("AppID", "")
                        ),
                    )
                )

            scored.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            if scored:
                (
                    best_score,
                    best_name,
                    best_app_id,
                ) = scored[0]

                if best_score >= 0.55:
                    if not ask_local_confirmation(
                        root,
                        "Zanel found a matching application",
                        f"Requested:\n\n"
                        f"{program}\n\n"
                        f"Matched application:\n\n"
                        f"{best_name}\n\n"
                        f"Open this application?",
                    ):
                        return (
                            "User declined opening "
                            "the matched application."
                        )

                    subprocess.Popen(
                        [
                            "explorer.exe",
                            f"shell:AppsFolder\\{best_app_id}",
                        ],
                        shell=False,
                    )

                    for _ in range(20):
                        if _wait_for_action(cancel_event, 0.5):
                            return "Action canceled."

                        if application_is_running(
                            best_name
                        ):
                            return (
                                f"Launched {best_name}."
                            )

                    return (
                        f"Launch command was sent for "
                        f"{best_name}, but Zanel could not "
                        f"confirm that it opened."
                    )

            start_menu_paths = [
                os.path.join(
                    os.environ.get(
                        "APPDATA",
                        "",
                    ),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                ),
                os.path.join(
                    os.environ.get(
                        "PROGRAMDATA",
                        "",
                    ),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                ),
            ]

            shortcuts = []

            for base_path in start_menu_paths:
                if not os.path.isdir(base_path):
                    continue

                try:
                    for root_dir, dirs, files in os.walk(
                        base_path
                    ):
                        for filename in files:
                            if not filename.lower().endswith(
                                ".lnk"
                            ):
                                continue

                            shortcut_name = os.path.splitext(
                                filename
                            )[0]

                            shortcut_clean = "".join(
                                character
                                for character
                                in shortcut_name.lower()
                                if (
                                    character.isalnum()
                                    or character == " "
                                )
                            )

                            ratio = (
                                difflib.SequenceMatcher(
                                    None,
                                    requested_clean,
                                    shortcut_clean,
                                ).ratio()
                            )

                            if (
                                requested_clean
                                and requested_clean
                                in shortcut_clean
                            ):
                                ratio = max(
                                    ratio,
                                    0.95,
                                )

                            shortcuts.append(
                                (
                                    ratio,
                                    shortcut_name,
                                    os.path.join(
                                        root_dir,
                                        filename,
                                    ),
                                )
                            )

                except OSError:
                    continue

            shortcuts.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            if (
                shortcuts
                and shortcuts[0][0] >= 0.55
            ):
                (
                    score,
                    shortcut_name,
                    shortcut_path,
                ) = shortcuts[0]

                if not ask_local_confirmation(
                    root,
                    "Zanel found a matching application",
                    f"Requested:\n\n"
                    f"{program}\n\n"
                    f"Matched application:\n\n"
                    f"{shortcut_name}\n\n"
                    f"Open this application?",
                ):
                    return (
                        "User declined opening "
                        "the matched application."
                    )

                subprocess.Popen(
                    [
                        "cmd",
                        "/c",
                        "start",
                        "",
                        shortcut_path,
                    ],
                    shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                for _ in range(20):
                    if _wait_for_action(cancel_event, 0.5):
                        return "Action canceled."

                    if application_is_running(
                        shortcut_name
                    ):
                        return (
                            f"Launched {shortcut_name}."
                        )

                return (
                    f"Launch command was sent for "
                    f"{shortcut_name}, but Zanel could "
                    f"not confirm that it opened."
                )

            return (
                "Could not find an installed application "
                f"similar to '{program}'."
            )

        except Exception as exc:
            return (
                f"Could not launch application: {exc}"
            )

    if name == "open_file":
        requested = str(
            action.get("path")
            or action.get("file")
            or action.get("filename")
            or action.get("name")
            or ""
        ).strip()

        runner = str(
            action.get("with")
            or action.get("runner")
            or action.get("program")
            or action.get("application")
            or ""
        ).strip()

        if not requested:
            return "No file supplied."

        try:
            def normalize_name(value):
                value = os.path.basename(
                    os.path.normpath(
                        str(value)
                    )
                )

                value = value.lower().strip()

                if "." in value:
                    value = os.path.splitext(
                        value
                    )[0]

                return "".join(
                    character
                    for character in value
                    if character.isalnum()
                    or character in (
                        " ",
                        "_",
                        "-",
                    )
                ).strip()

            def normalize_full_name(value):
                value = str(value).lower().strip()

                return "".join(
                    character
                    for character in value
                    if character.isalnum()
                    or character in (
                        " ",
                        "_",
                        "-",
                        ".",
                    )
                ).strip()

            def score_candidate(
                requested_name,
                candidate_path,
            ):
                candidate_name = os.path.basename(
                    candidate_path
                )

                requested_full = (
                    normalize_full_name(
                        requested_name
                    )
                )

                candidate_full = (
                    normalize_full_name(
                        candidate_name
                    )
                )

                requested_base = normalize_name(
                    requested_name
                )

                candidate_base = normalize_name(
                    candidate_name
                )

                if not requested_full:
                    return 0.0

                if requested_full == candidate_full:
                    return 1.0

                if requested_base and (
                    requested_base
                    == candidate_base
                ):
                    return 0.98

                ratio_full = (
                    difflib.SequenceMatcher(
                        None,
                        requested_full,
                        candidate_full,
                    ).ratio()
                )

                ratio_base = (
                    difflib.SequenceMatcher(
                        None,
                        requested_base,
                        candidate_base,
                    ).ratio()
                    if requested_base
                    and candidate_base
                    else 0.0
                )

                requested_words = set(
                    requested_base.split()
                )

                candidate_words = set(
                    candidate_base.split()
                )

                word_score = 0.0

                if requested_words:
                    overlap = (
                        requested_words.intersection(
                            candidate_words
                        )
                    )

                    word_score = (
                        len(overlap)
                        / len(requested_words)
                    )

                substring_score = 0.0

                if (
                    requested_full
                    and requested_full
                    in candidate_full
                ):
                    substring_score = 0.94

                if (
                    requested_base
                    and requested_base
                    in candidate_base
                ):
                    substring_score = max(
                        substring_score,
                        0.96,
                    )

                return max(
                    ratio_full,
                    ratio_base,
                    word_score,
                    substring_score,
                )

            def is_probably_file(path):
                try:
                    return (
                        os.path.isfile(path)
                        and not os.path.islink(path)
                    )
                except OSError:
                    return False

            def collect_drives():
                drives = []

                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    drive = f"{letter}:\\"

                    if os.path.isdir(drive):
                        drives.append(drive)

                return drives

            def search_paths(requested_name):
                matches = []
                seen = set()

                requested_base = os.path.basename(
                    requested_name
                )

                requested_lower = (
                    requested_base.lower()
                )

                preferred_locations = [
                    os.path.join(
                        os.path.expanduser("~"),
                        "Downloads",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Desktop",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Documents",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Pictures",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Videos",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Music",
                    ),
                    os.path.expanduser("~"),
                    os.environ.get(
                        "TEMP",
                        "",
                    ),
                ]

                for base_path in preferred_locations:
                    if not base_path:
                        continue

                    if not os.path.isdir(base_path):
                        continue

                    try:
                        for root_dir, dirs, files in os.walk(
                            base_path,
                            topdown=True,
                        ):
                            dirs[:] = [
                                directory
                                for directory in dirs
                                if directory.lower()
                                not in {
                                    "node_modules",
                                    ".git",
                                    "__pycache__",
                                    ".cache",
                                    "cache",
                                }
                            ]

                            for filename in files:
                                if (
                                    requested_lower
                                    == filename.lower()
                                ):
                                    path = os.path.abspath(
                                        os.path.join(
                                            root_dir,
                                            filename,
                                        )
                                    )

                                    key = os.path.normcase(
                                        path
                                    )

                                    if key not in seen:
                                        seen.add(key)
                                        matches.append(path)

                    except (
                        OSError,
                        PermissionError,
                    ):
                        continue

                if matches:
                    return matches

                drives = collect_drives()

                excluded_roots = {
                    os.path.normcase(
                        os.path.join(
                            os.environ.get(
                                "SystemRoot",
                                r"C:\Windows",
                            ),
                        )
                    ),
                    os.path.normcase(
                        os.path.join(
                            os.environ.get(
                                "ProgramFiles",
                                r"C:\Program Files",
                            ),
                        )
                    ),
                    os.path.normcase(
                        os.path.join(
                            os.environ.get(
                                "ProgramFiles(x86)",
                                r"C:\Program Files (x86)",
                            ),
                        )
                    ),
                }

                for drive in drives:
                    try:
                        for root_dir, dirs, files in os.walk(
                            drive,
                            topdown=True,
                        ):
                            normalized_root = (
                                os.path.normcase(
                                    os.path.abspath(
                                        root_dir
                                    )
                                )
                            )

                            dirs[:] = [
                                directory
                                for directory in dirs
                                if os.path.normcase(
                                    os.path.join(
                                        normalized_root,
                                        directory,
                                    )
                                )
                                not in excluded_roots
                                and directory.lower()
                                not in {
                                    "$recycle.bin",
                                    "system volume information",
                                    "windows.old",
                                    "node_modules",
                                    ".git",
                                    "__pycache__",
                                }
                            ]

                            for filename in files:
                                if (
                                    requested_lower
                                    == filename.lower()
                                ):
                                    path = os.path.abspath(
                                        os.path.join(
                                            root_dir,
                                            filename,
                                        )
                                    )

                                    key = os.path.normcase(
                                        path
                                    )

                                    if key not in seen:
                                        seen.add(key)
                                        matches.append(path)

                    except (
                        OSError,
                        PermissionError,
                    ):
                        continue

                return matches

            def fuzzy_search(requested_name):
                candidates = []
                seen = set()

                preferred_locations = [
                    os.path.join(
                        os.path.expanduser("~"),
                        "Downloads",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Desktop",
                    ),
                    os.path.join(
                        os.path.expanduser("~"),
                        "Documents",
                    ),
                    os.path.expanduser("~"),
                ]

                for base_path in preferred_locations:
                    if not os.path.isdir(base_path):
                        continue

                    try:
                        for root_dir, dirs, files in os.walk(
                            base_path,
                            topdown=True,
                        ):
                            dirs[:] = [
                                directory
                                for directory in dirs
                                if directory.lower()
                                not in {
                                    "node_modules",
                                    ".git",
                                    "__pycache__",
                                    ".cache",
                                    "cache",
                                }
                            ]

                            for filename in files:
                                path = os.path.abspath(
                                    os.path.join(
                                        root_dir,
                                        filename,
                                    )
                                )

                                key = os.path.normcase(
                                    path
                                )

                                if key in seen:
                                    continue

                                seen.add(key)

                                score = score_candidate(
                                    requested_name,
                                    path,
                                )

                                if score >= 0.55:
                                    candidates.append(
                                        (
                                            score,
                                            path,
                                        )
                                    )

                    except (
                        OSError,
                        PermissionError,
                    ):
                        continue

                if not candidates:
                    for drive in collect_drives():
                        try:
                            for root_dir, dirs, files in os.walk(
                                drive,
                                topdown=True,
                            ):
                                dirs[:] = [
                                    directory
                                    for directory in dirs
                                    if directory.lower()
                                    not in {
                                        "$recycle.bin",
                                        "system volume information",
                                        "windows.old",
                                        "node_modules",
                                        ".git",
                                        "__pycache__",
                                    }
                                ]

                                for filename in files:
                                    path = os.path.abspath(
                                        os.path.join(
                                            root_dir,
                                            filename,
                                        )
                                    )

                                    key = os.path.normcase(
                                        path
                                    )

                                    if key in seen:
                                        continue

                                    seen.add(key)

                                    score = score_candidate(
                                        requested_name,
                                        path,
                                    )

                                    if score >= 0.55:
                                        candidates.append(
                                            (
                                                score,
                                                path,
                                            )
                                        )

                        except (
                            OSError,
                            PermissionError,
                        ):
                            continue

                candidates.sort(
                    key=lambda item: item[0],
                    reverse=True,
                )

                return candidates[:10]

            def resolve_runner(
                runner_name,
                target_path,
            ):
                if not runner_name:
                    return None

                requested_runner = (
                    runner_name.lower().strip()
                )

                extension = (
                    os.path.splitext(
                        target_path
                    )[1]
                    .lower()
                )

                aliases = {
                    "python": [
                        "python",
                        "python.exe",
                        "python3",
                        "python3.exe",
                        "py",
                        "py.exe",
                    ],
                    "pythonw": [
                        "pythonw",
                        "pythonw.exe",
                        "pyw",
                        "pyw.exe",
                    ],
                    "powershell": [
                        "powershell",
                        "powershell.exe",
                        "pwsh",
                        "pwsh.exe",
                    ],
                    "cmd": [
                        "cmd",
                        "cmd.exe",
                        "command prompt",
                    ],
                    "node": [
                        "node",
                        "node.exe",
                    ],
                    "java": [
                        "java",
                        "java.exe",
                    ],
                }

                runner_command = None

                for key, values in aliases.items():
                    if requested_runner in values:
                        runner_command = key
                        break

                if runner_command:
                    if (
                        runner_command
                        in {
                            "python",
                            "pythonw",
                        }
                    ):
                        if extension == ".py":
                            candidates = (
                                ["python"]
                                if runner_command
                                == "python"
                                else ["pythonw"]
                            )

                            if (
                                shutil.which(
                                    candidates[0]
                                )
                                is None
                            ):
                                candidates = [
                                    "py"
                                ]

                            executable = shutil.which(
                                candidates[0]
                            )

                            if executable:
                                return [
                                    executable,
                                    target_path,
                                ]

                        if extension == ".pyw":
                            candidates = [
                                "pythonw",
                                "pyw",
                                "python",
                            ]

                            for candidate in candidates:
                                executable = (
                                    shutil.which(
                                        candidate
                                    )
                                )

                                if executable:
                                    return [
                                        executable,
                                        target_path,
                                    ]

                    if runner_command == "powershell":
                        executable = (
                            shutil.which(
                                "pwsh"
                            )
                            or shutil.which(
                                "powershell"
                            )
                        )

                        if executable:
                            return [
                                executable,
                                "-File",
                                target_path,
                            ]

                    if runner_command == "cmd":
                        executable = shutil.which(
                            "cmd"
                        )

                        if executable:
                            return [
                                executable,
                                "/c",
                                target_path,
                            ]

                    if runner_command == "node":
                        executable = shutil.which(
                            "node"
                        )

                        if executable:
                            return [
                                executable,
                                target_path,
                            ]

                    if runner_command == "java":
                        executable = shutil.which(
                            "java"
                        )

                        if executable:
                            return [
                                executable,
                                target_path,
                            ]

                explicit_runner = runner_name.strip()

                if os.path.isfile(
                    explicit_runner
                ):
                    return [
                        explicit_runner,
                        target_path,
                    ]

                executable = shutil.which(
                    explicit_runner
                )

                if executable:
                    return [
                        executable,
                        target_path,
                    ]

                return None

            target_path = None

            expanded_requested = os.path.expandvars(
                os.path.expanduser(
                    requested
                )
            )

            if (
                os.path.isabs(
                    expanded_requested
                )
                and is_probably_file(
                    expanded_requested
                )
            ):
                target_path = os.path.abspath(
                    expanded_requested
                )

            elif is_probably_file(
                expanded_requested
            ):
                target_path = os.path.abspath(
                    expanded_requested
                )

            else:
                if os.path.dirname(
                    expanded_requested
                ):
                    possible_path = os.path.abspath(
                        expanded_requested
                    )

                    if is_probably_file(
                        possible_path
                    ):
                        target_path = possible_path

                if target_path is None:
                    exact_matches = search_paths(
                        requested
                    )

                    if exact_matches:
                        if len(
                            exact_matches
                        ) == 1:
                            target_path = (
                                exact_matches[0]
                            )
                        else:
                            scored = [
                                (
                                    score_candidate(
                                        requested,
                                        path,
                                    ),
                                    path,
                                )
                                for path in exact_matches
                            ]

                            scored.sort(
                                key=lambda item: item[0],
                                reverse=True,
                            )

                            if (
                                scored
                                and scored[0][0]
                                >= 0.80
                            ):
                                target_path = (
                                    scored[0][1]
                                )

                if target_path is None:
                    fuzzy_matches = (
                        fuzzy_search(
                            requested
                        )
                    )

                    if not fuzzy_matches:
                        return (
                            f"Could not find a file "
                            f"similar to '{requested}'."
                        )

                    best_score, best_path = (
                        fuzzy_matches[0]
                    )

                    if best_score < 0.55:
                        return (
                            f"Could not find a file "
                            f"similar to '{requested}'."
                        )

                    if best_score < 0.85:
                        if not ask_local_confirmation(
                            root,
                            "Zanel found a similar file",
                            f"Requested:\n\n"
                            f"{requested}\n\n"
                            f"Closest match:\n\n"
                            f"{best_path}\n\n"
                            f"Open this file?",
                        ):
                            return (
                                "User declined opening "
                                "the similar file."
                            )

                    target_path = best_path

            if not target_path:
                return (
                    f"Could not find '{requested}'."
                )

            target_path = os.path.abspath(
                os.path.normpath(
                    target_path
                )
            )

            if not is_probably_file(
                target_path
            ):
                return (
                    "The selected path is not "
                    "a valid file."
                )

            extension = (
                os.path.splitext(
                    target_path
                )[1]
                .lower()
            )

            dangerous_script_extensions = {
                ".bat",
                ".cmd",
                ".ps1",
                ".psm1",
                ".vbs",
                ".vbe",
                ".js",
                ".jse",
                ".wsf",
                ".wsh",
                ".hta",
                ".py",
                ".pyw",
                ".pyc",
                ".pyo",
                ".jar",
                ".exe",
                ".com",
                ".scr",
                ".msi",
            }

            if runner:
                command = resolve_runner(
                    runner,
                    target_path,
                )

                if not command:
                    return (
                        f"Could not find a program "
                        f"to run '{runner}'."
                    )

                command_display = " ".join(
                    f'"{part}"'
                    if " " in str(part)
                    else str(part)
                    for part in command
                )

                if not ask_local_confirmation(
                    root,
                    "Zanel wants to open a file",
                    f"Allow Zanel to run:\n\n"
                    f"{command_display}",
                ):
                    return (
                        "User declined opening "
                        "the file."
                    )

                subprocess.Popen(
                    command,
                    shell=False,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if extension
                        in {
                            ".py",
                            ".pyw",
                            ".ps1",
                            ".bat",
                            ".cmd",
                            ".vbs",
                            ".js",
                        }
                        else 0
                    ),
                )

                return (
                    f"Opened {os.path.basename(target_path)} "
                    f"with {runner}."
                )

            if extension in dangerous_script_extensions:
                if extension in {
                    ".py",
                    ".pyw",
                }:
                    python_executable = (
                        shutil.which(
                            "python"
                        )
                        or shutil.which(
                            "py"
                        )
                    )

                    pythonw_executable = (
                        shutil.which(
                            "pythonw"
                        )
                        or shutil.which(
                            "pyw"
                        )
                    )

                    if extension == ".pyw":
                        suggested_runner = (
                            pythonw_executable
                            or python_executable
                        )
                    else:
                        suggested_runner = (
                            python_executable
                        )

                    if suggested_runner:
                        if not ask_local_confirmation(
                            root,
                            "Zanel wants to run a Python file",
                            f"File:\n\n"
                            f"{target_path}\n\n"
                            f"Python:\n\n"
                            f"{suggested_runner}\n\n"
                            f"Allow Zanel to run this file?",
                        ):
                            return (
                                "User declined running "
                                "the Python file."
                            )

                        subprocess.Popen(
                            [
                                suggested_runner,
                                target_path,
                            ],
                            shell=False,
                            creationflags=(
                                subprocess.CREATE_NO_WINDOW
                            ),
                        )

                        return (
                            f"Ran "
                            f"{os.path.basename(target_path)} "
                            f"with Python."
                        )

                if not ask_local_confirmation(
                    root,
                    "Zanel wants to open a file",
                    f"File:\n\n"
                    f"{target_path}\n\n"
                    f"This file may execute code.\n\n"
                    f"Allow Zanel to open it?",
                ):
                    return (
                        "User declined opening "
                        "the file."
                    )

            else:
                if not ask_local_confirmation(
                    root,
                    "Zanel wants to open a file",
                    f"Allow Zanel to open:\n\n"
                    f"{target_path}",
                ):
                    return (
                        "User declined opening "
                        "the file."
                    )

            os.startfile(
                target_path
            )

            return (
                f"Opened "
                f"{os.path.basename(target_path)}."
            )

        except FileNotFoundError:
            return (
                f"Could not find the file "
                f"'{requested}'."
            )

        except PermissionError:
            return (
                "Zanel does not have permission "
                "to open that file."
            )

        except OSError as exc:
            return (
                f"Could not open the file: {exc}"
            )

        except Exception as exc:
            return (
                f"Could not open the file: {exc}"
            )

    if name in (
        "search_file",
        "find_file",
        "search_for_file",
    ):
        requested = str(
            action.get("filename")
            or action.get("file")
            or action.get("name")
            or action.get("query")
            or action.get("path")
            or ""
        ).strip()

        if not requested:
            return "No file name supplied."

        try:
            requested = os.path.expandvars(
                os.path.expanduser(
                    requested.strip('"').strip("'")
                )
            )

            def normalize_text(value):
                value = str(
                    value
                ).lower().strip()

                return "".join(
                    character
                    for character in value
                    if character.isalnum()
                    or character in (
                        " ",
                        "_",
                        "-",
                        ".",
                    )
                ).strip()

            def normalize_filename(value):
                value = os.path.basename(
                    os.path.normpath(
                        str(value)
                    )
                )

                return normalize_text(
                    value
                )

            def normalize_stem(value):
                value = normalize_filename(
                    value
                )

                return os.path.splitext(
                    value
                )[0].strip()

            def tokenize(value):
                value = normalize_stem(
                    value
                )

                return [
                    token
                    for token in re.split(
                        r"[\s_.-]+",
                        value,
                    )
                    if token
                ]

            def is_file(path):
                try:
                    return (
                        os.path.isfile(path)
                        and not os.path.islink(path)
                    )
                except OSError:
                    return False

            requested_filename = os.path.basename(
                os.path.normpath(
                    requested
                )
            )

            requested_full = normalize_filename(
                requested_filename
            )

            requested_stem = normalize_stem(
                requested_filename
            )

            requested_extension = (
                os.path.splitext(
                    requested_filename
                )[1].lower()
            )

            requested_tokens = tokenize(
                requested_filename
            )

            if not requested_stem:
                return "No valid file name supplied."

            direct_path = os.path.abspath(
                requested
            )

            if is_file(
                direct_path
            ):
                return (
                    "Found file\n\n"
                    f"{direct_path}"
                )

            excluded_directories = {
                "$recycle.bin",
                "system volume information",
                "windows.old",
                "windows",
                "program files",
                "program files (x86)",
                "programdata",
                "windowsapps",
                "msixvc",
                "node_modules",
                ".git",
                ".svn",
                ".hg",
                "__pycache__",
                ".cache",
                "cache",
                "temp",
                "tmp",
                "package cache",
                "packages",
            }

            ignored_extensions = {
                ".lnk",
                ".tmp",
                ".etl",
                ".db",
                ".db-wal",
                ".db-shm",
            }

            def should_skip_directory(
                directory
            ):
                return (
                    directory.lower()
                    in excluded_directories
                )

            def score_candidate(
                candidate_path
            ):
                candidate_filename = os.path.basename(
                    candidate_path
                )

                candidate_full = normalize_filename(
                    candidate_filename
                )

                candidate_stem = normalize_stem(
                    candidate_filename
                )

                if (
                    not candidate_stem
                    or not requested_stem
                ):
                    return 0.0

                if (
                    candidate_full
                    == requested_full
                ):
                    return 1.0

                if (
                    candidate_stem
                    == requested_stem
                ):
                    return 0.99

                candidate_extension = (
                    os.path.splitext(
                        candidate_filename
                    )[1].lower()
                )

                if (
                    requested_extension
                    and candidate_extension
                    != requested_extension
                ):
                    extension_penalty = 0.10
                else:
                    extension_penalty = 0.0

                stem_ratio = difflib.SequenceMatcher(
                    None,
                    requested_stem,
                    candidate_stem,
                ).ratio()

                full_ratio = difflib.SequenceMatcher(
                    None,
                    requested_full,
                    candidate_full,
                ).ratio()

                requested_compact = (
                    requested_stem
                    .replace(" ", "")
                    .replace("_", "")
                    .replace("-", "")
                )

                candidate_compact = (
                    candidate_stem
                    .replace(" ", "")
                    .replace("_", "")
                    .replace("-", "")
                )

                compact_ratio = difflib.SequenceMatcher(
                    None,
                    requested_compact,
                    candidate_compact,
                ).ratio()

                token_score = 0.0

                if requested_tokens:
                    candidate_tokens = tokenize(
                        candidate_filename
                    )

                    if candidate_tokens:
                        requested_set = set(
                            requested_tokens
                        )

                        candidate_set = set(
                            candidate_tokens
                        )

                        overlap = (
                            requested_set
                            .intersection(
                                candidate_set
                            )
                        )

                        token_score = (
                            len(overlap)
                            / max(
                                len(requested_set),
                                len(candidate_set),
                            )
                        )

                substring_score = 0.0

                if (
                    len(requested_stem) >= 4
                    and requested_stem
                    in candidate_stem
                ):
                    substring_score = 0.94

                reverse_substring_score = 0.0

                if (
                    len(candidate_stem) >= 4
                    and candidate_stem
                    in requested_stem
                ):
                    reverse_substring_score = 0.91

                score = max(
                    stem_ratio,
                    full_ratio,
                    compact_ratio,
                    token_score,
                    substring_score,
                    reverse_substring_score,
                )

                if (
                    extension_penalty
                    and score < 0.98
                ):
                    score -= extension_penalty

                if len(requested_stem) <= 3:
                    if (
                        candidate_stem
                        != requested_stem
                    ):
                        score = min(
                            score,
                            0.70,
                        )

                if (
                    len(requested_stem) >= 6
                    and stem_ratio < 0.60
                    and compact_ratio < 0.65
                    and token_score < 0.50
                    and not substring_score
                ):
                    score = min(
                        score,
                        0.55,
                    )

                return max(
                    0.0,
                    min(
                        score,
                        1.0,
                    ),
                )

            def find_everything():
                possible_commands = [
                    "es.exe",
                    os.path.join(
                        os.environ.get(
                            "ProgramFiles",
                            r"C:\Program Files",
                        ),
                        "Everything",
                        "es.exe",
                    ),
                    os.path.join(
                        os.environ.get(
                            "ProgramFiles",
                            r"C:\Program Files",
                        ),
                        "Everything",
                        "Everything.exe",
                    ),
                    os.path.join(
                        os.environ.get(
                            "ProgramFiles(x86)",
                            r"C:\Program Files (x86)",
                        ),
                        "Everything",
                        "es.exe",
                    ),
                ]

                for command in possible_commands:
                    try:
                        if (
                            os.path.basename(
                                command
                            ).lower()
                            == "es.exe"
                            and command == "es.exe"
                        ):
                            result = shutil.which(
                                "es.exe"
                            )

                            if result:
                                return result

                        if os.path.isfile(
                            command
                        ):
                            if command.lower().endswith(
                                "es.exe"
                            ):
                                return command

                            es_path = os.path.join(
                                os.path.dirname(
                                    command
                                ),
                                "es.exe",
                            )

                            if os.path.isfile(
                                es_path
                            ):
                                return es_path

                    except OSError:
                        continue

                return None

            def search_everything(
                executable
            ):
                queries = []

                queries.append(
                    requested_filename
                )

                if (
                    requested_stem
                    and requested_stem
                    != requested_filename.lower()
                ):
                    queries.append(
                        requested_stem
                    )

                results = []
                seen = set()

                for query in queries:
                    try:
                        process = subprocess.run(
                            [
                                executable,
                                "-n",
                                "80",
                                query,
                            ],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="ignore",
                            timeout=8,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )

                        if process.returncode != 0:
                            continue

                        for line in process.stdout.splitlines():
                            path = line.strip()

                            if not path:
                                continue

                            if not is_file(
                                path
                            ):
                                continue

                            key = os.path.normcase(
                                os.path.abspath(
                                    path
                                )
                            )

                            if key in seen:
                                continue

                            seen.add(
                                key
                            )

                            filename = os.path.basename(
                                path
                            )

                            extension = (
                                os.path.splitext(
                                    filename
                                )[1].lower()
                            )

                            if extension in ignored_extensions:
                                continue

                            results.append(
                                path
                            )

                    except (
                        OSError,
                        subprocess.SubprocessError,
                    ):
                        continue

                return results

            def search_fallback():
                home = os.path.expanduser(
                    "~"
                )

                preferred_locations = [
                    os.path.join(
                        home,
                        "Desktop",
                    ),
                    os.path.join(
                        home,
                        "Downloads",
                    ),
                    os.path.join(
                        home,
                        "Documents",
                    ),
                    os.path.join(
                        home,
                        "Pictures",
                    ),
                    os.path.join(
                        home,
                        "Videos",
                    ),
                    os.path.join(
                        home,
                        "Music",
                    ),
                    os.path.join(
                        home,
                        "OneDrive",
                    ),
                ]

                matches = []
                fuzzy = []
                seen = set()

                for base_path in preferred_locations:
                    if not os.path.isdir(
                        base_path
                    ):
                        continue

                    try:
                        for root_dir, dirs, files in os.walk(
                            base_path,
                            topdown=True,
                            followlinks=False,
                        ):
                            dirs[:] = [
                                directory
                                for directory in dirs
                                if not should_skip_directory(
                                    directory
                                )
                            ]

                            for filename in files:
                                extension = (
                                    os.path.splitext(
                                        filename
                                    )[1].lower()
                                )

                                if extension in ignored_extensions:
                                    continue

                                path = os.path.join(
                                    root_dir,
                                    filename,
                                )

                                key = os.path.normcase(
                                    os.path.abspath(
                                        path
                                    )
                                )

                                if key in seen:
                                    continue

                                seen.add(
                                    key
                                )

                                filename_lower = (
                                    filename.lower()
                                )

                                stem = normalize_stem(
                                    filename
                                )

                                if (
                                    filename_lower
                                    == requested_filename.lower()
                                ):
                                    matches.append(
                                        path
                                    )
                                    continue

                                if (
                                    stem
                                    == requested_stem
                                ):
                                    matches.append(
                                        path
                                    )
                                    continue

                                score = score_candidate(
                                    path
                                )

                                if score >= 0.78:
                                    fuzzy.append(
                                        (
                                            score,
                                            path,
                                        )
                                    )

                    except (
                        OSError,
                        PermissionError,
                    ):
                        continue

                if matches:
                    return matches, fuzzy

                return [], fuzzy

            everything = find_everything()

            if everything:
                candidates = search_everything(
                    everything
                )

                exact_matches = []
                stem_matches = []
                fuzzy_matches = []

                seen = set()

                for path in candidates:
                    key = os.path.normcase(
                        os.path.abspath(
                            path
                        )
                    )

                    if key in seen:
                        continue

                    seen.add(
                        key
                    )

                    filename = os.path.basename(
                        path
                    )

                    filename_lower = (
                        filename.lower()
                    )

                    candidate_stem = normalize_stem(
                        filename
                    )

                    if (
                        filename_lower
                        == requested_filename.lower()
                    ):
                        exact_matches.append(
                            path
                        )
                        continue

                    if (
                        candidate_stem
                        == requested_stem
                    ):
                        stem_matches.append(
                            path
                        )
                        continue

                    score = score_candidate(
                        path
                    )

                    if score >= 0.78:
                        fuzzy_matches.append(
                            (
                                score,
                                path,
                            )
                        )

                if exact_matches:
                    if len(exact_matches) == 1:
                        return (
                            "Found file\n\n"
                            f"{exact_matches[0]}"
                        )

                    output = [
                        f"Found {len(exact_matches)} exact matches",
                        "",
                    ]

                    for path in exact_matches[:5]:
                        output.append(
                            path
                        )

                    return "\n".join(
                        output
                    )

                if stem_matches:
                    if len(stem_matches) == 1:
                        return (
                            "Found file\n\n"
                            f"{stem_matches[0]}"
                        )

                    output = [
                        f"Found {len(stem_matches)} matching files",
                        "",
                    ]

                    for path in stem_matches[:5]:
                        output.append(
                            path
                        )

                    return "\n".join(
                        output
                    )

                fuzzy_matches.sort(
                    key=lambda item: (
                        item[0],
                        -len(item[1]),
                    ),
                    reverse=True,
                )

                if fuzzy_matches:
                    best_score = fuzzy_matches[0][0]

                    if best_score >= 0.86:
                        output = [
                            f"Found a close match for '{requested_filename}'",
                            "",
                            fuzzy_matches[0][1],
                        ]

                        if len(fuzzy_matches) > 1:
                            output.extend(
                                [
                                    "",
                                    "Other possible matches:",
                                ]
                            )

                            for _, path in fuzzy_matches[1:5]:
                                output.append(
                                    path
                                )

                        return "\n".join(
                            output
                        )

                    if best_score >= 0.78:
                        output = [
                            f"I couldn't find an exact match for '{requested_filename}'.",
                            "",
                            "Possible matches:",
                        ]

                        for _, path in fuzzy_matches[:5]:
                            output.append(
                                path
                            )

                        return "\n".join(
                            output
                        )

            exact_matches, fuzzy_matches = search_fallback()

            if exact_matches:
                if len(exact_matches) == 1:
                    return (
                        "Found file\n\n"
                        f"{exact_matches[0]}"
                    )

                output = [
                    f"Found {len(exact_matches)} matching files",
                    "",
                ]

                for path in exact_matches[:5]:
                    output.append(
                        path
                    )

                return "\n".join(
                    output
                )

            fuzzy_matches.sort(
                key=lambda item: (
                    item[0],
                    -len(item[1]),
                ),
                reverse=True,
            )

            if fuzzy_matches:
                strong_matches = [
                    path
                    for score, path in fuzzy_matches
                    if score >= 0.86
                ]

                if strong_matches:
                    output = [
                        f"Found a close match for '{requested_filename}'",
                        "",
                        strong_matches[0],
                    ]

                    if len(strong_matches) > 1:
                        output.extend(
                            [
                                "",
                                "Other possible matches:",
                            ]
                        )

                        for path in strong_matches[1:5]:
                            output.append(
                                path
                            )

                    return "\n".join(
                        output
                    )

                possible_matches = [
                    path
                    for score, path in fuzzy_matches
                    if score >= 0.78
                ]

                if possible_matches:
                    output = [
                        f"I couldn't find an exact match for '{requested_filename}'.",
                        "",
                        "Possible matches:",
                    ]

                    for path in possible_matches[:5]:
                        output.append(
                            path
                        )

                    return "\n".join(
                        output
                    )

            return (
                f"No file matching "
                f"'{requested_filename}' "
                f"was found on the PC."
            )

        except PermissionError:
            return (
                "I couldn't search some protected "
                "folders because Windows denied access."
            )

        except OSError as exc:
            return (
                f"Could not search for the file: "
                f"{exc}"
            )

        except Exception as exc:
            return (
                f"Could not search for the file: "
                f"{exc}"
            )

    if name == "close_app":
        program = str(
            action.get("program")
            or action.get("app_name")
            or action.get("app")
            or action.get("name")
            or ""
        ).strip()

        if not program:
            return "No application supplied."

        if not ask_local_confirmation(
            root,
            "Zanel wants to close an application",
            f"Allow Zanel to close:\n\n{program}",
        ):
            return "User declined closing the application."

        try:
            requested = program.lower().strip()

            requested_clean = "".join(
                character
                for character in requested
                if character.isalnum()
                or character == " "
            )

            process_result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Process | "
                    "Select-Object "
                    "ProcessName,Id,MainWindowTitle,Path | "
                    "ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if process_result.returncode != 0:
                return (
                    "Could not inspect running applications."
                )

            data = json.loads(
                process_result.stdout
            )

            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list):
                return (
                    "Could not read the running applications."
                )

            best_match = None
            best_score = 0.0

            for process in data:
                if not isinstance(process, dict):
                    continue

                process_name = str(
                    process.get("ProcessName", "")
                ).strip()

                process_id = process.get("Id")

                window_title = str(
                    process.get("MainWindowTitle", "")
                ).strip()

                if not process_name or not process_id:
                    continue

                process_clean = "".join(
                    character
                    for character in process_name.lower()
                    if character.isalnum()
                    or character == " "
                )

                title_clean = "".join(
                    character
                    for character in window_title.lower()
                    if character.isalnum()
                    or character == " "
                )

                process_score = difflib.SequenceMatcher(
                    None,
                    requested_clean,
                    process_clean,
                ).ratio()

                title_score = difflib.SequenceMatcher(
                    None,
                    requested_clean,
                    title_clean,
                ).ratio()

                score = max(
                    process_score,
                    title_score,
                )

                if (
                    requested_clean
                    and requested_clean in process_clean
                ):
                    score = max(score, 0.95)

                if (
                    requested_clean
                    and requested_clean in title_clean
                ):
                    score = max(score, 0.95)

                if score > best_score:
                    best_score = score
                    best_match = (
                        process_name,
                        window_title,
                        int(process_id),
                    )

            if not best_match or best_score < 0.45:
                return (
                    f"Could not find a running application "
                    f"similar to '{program}'."
                )

            process_name, window_title, process_id = best_match

            display_name = process_name

            if window_title:
                display_name = (
                    f"{process_name} — {window_title}"
                )

            if not ask_local_confirmation(
                root,
                "Zanel found a running application",
                f"Requested:\n\n"
                f"{program}\n\n"
                f"Matched application:\n\n"
                f"{display_name}\n\n"
                f"Close this application?",
            ):
                return (
                    "User declined closing "
                    "the matched application."
                )

            kill_result = subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process_id),
                    "/T",
                    "/F",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if kill_result.returncode != 0:
                output = (
                    (kill_result.stdout or "")
                    + (kill_result.stderr or "")
                ).strip()

                return (
                    f"Could not close {display_name}: "
                    f"{output[-1000:]}"
                )

            for _ in range(10):
                if _wait_for_action(cancel_event, 0.5):
                    return "Action canceled."

                if not application_is_running(
                    process_name
                ):
                    return f"Closed {display_name}."

            return (
                f"Close command was sent for "
                f"{display_name}, but Zanel could not "
                f"confirm that it closed."
            )

        except Exception as exc:
            return (
                f"Could not close application: {exc}"
            )

    if name == "shell":
        if not ALLOW_SHELL_COMMANDS:
            return "Shell execution is disabled."

        command = str(
            action.get("command", "")
        ).strip()

        if not command:
            return "No shell command supplied."

        if not ask_local_confirmation(
            root,
            "Zanel wants to run a command",
            "Allow this command to run on your PC?\n\n"
            + command
            + "\n\nOnly approve commands you understand.",
        ):
            return "User declined the shell command."

        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

            output = (
                (completed.stdout or "")
                + (completed.stderr or "")
            ).strip()

            output = output[-4000:]

            return (
                f"Command exited with code "
                f"{completed.returncode}.\n"
                f"{output}"
            )

        except Exception as exc:
            return f"Command failed: {exc}"

    if name in (
        "mouse_move",
        "move_mouse",
    ):
        duration = action.get("duration", 0.3)

        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not 0 <= duration <= 3
        ):
            return "Mouse movement duration must be between 0 and 3 seconds."

        try:
            screen_size = pyautogui.size()
            point = _validated_mouse_point(action, screen_size)
        except Exception as exc:
            return f"Could not read screen bounds: {exc}"

        if point is None:
            return "Mouse coordinates must be integer pixels on the primary display."

        x, y = point

        if not ask_local_confirmation(
            root,
            "Zanel wants to move the mouse",
            f"Move the mouse to ({x}, {y}) on the primary display?",
        ):
            return "User declined moving the mouse."

        try:
            if _validated_mouse_point(
                action,
                pyautogui.size(),
            ) is None:
                return "Mouse movement canceled because the screen bounds changed."

            pyautogui.moveTo(
                x,
                y,
                duration=float(duration),
            )
            return f"Moved the mouse to ({x}, {y})."
        except Exception as exc:
            return f"Mouse movement failed: {exc}"

    if name in (
        "mouse_click",
        "click_mouse",
    ):
        button = str(action.get("button", "left")).lower().strip()
        clicks = action.get("clicks", 1)

        if button not in ("left", "right", "middle"):
            return "Mouse button must be left, right, or middle."

        if type(clicks) is not int or clicks not in (1, 2):
            return "Mouse clicks must be 1 or 2."

        try:
            screen_size = pyautogui.size()
            point = _validated_mouse_point(action, screen_size)
        except Exception as exc:
            return f"Could not read screen bounds: {exc}"

        if point is None:
            return "Mouse coordinates must be integer pixels on the primary display."

        x, y = point
        click_label = "double-click" if clicks == 2 else "click"

        if not ask_local_confirmation(
            root,
            "Zanel wants to click",
            f"{click_label.capitalize()} the {button} mouse button at "
            f"({x}, {y}) on the primary display?",
        ):
            return "User declined the mouse click."

        try:
            if _validated_mouse_point(
                action,
                pyautogui.size(),
            ) is None:
                return "Mouse click canceled because the screen bounds changed."

            pyautogui.click(
                x=x,
                y=y,
                clicks=clicks,
                button=button,
            )
            return f"Clicked at ({x}, {y})."
        except Exception as exc:
            return f"Mouse click failed: {exc}"

    if name in (
        "mouse_scroll",
        "scroll_mouse",
    ):
        amount = action.get("amount")

        if type(amount) is not int or amount == 0 or not -20 <= amount <= 20:
            return "Mouse scroll amount must be an integer from -20 to 20, excluding 0."

        has_x = "x" in action
        has_y = "y" in action

        if has_x != has_y:
            return "Mouse scroll coordinates must include both x and y."

        try:
            screen_size = pyautogui.size()
            point = (
                _validated_mouse_point(action, screen_size)
                if has_x
                else None
            )
        except Exception as exc:
            return f"Could not read screen bounds: {exc}"

        if has_x and point is None:
            return "Mouse coordinates must be integer pixels on the primary display."

        target = (
            f"at ({point[0]}, {point[1]})"
            if point
            else "at the current cursor position"
        )
        direction = "up" if amount > 0 else "down"

        if not ask_local_confirmation(
            root,
            "Zanel wants to scroll",
            f"Scroll {direction} {abs(amount)} notches {target}?",
        ):
            return "User declined scrolling."

        try:
            if has_x:
                if _validated_mouse_point(
                    action,
                    pyautogui.size(),
                ) is None:
                    return "Mouse scroll canceled because the screen bounds changed."

                pyautogui.scroll(
                    amount,
                    x=point[0],
                    y=point[1],
                )
            else:
                pyautogui.scroll(amount)

            return f"Scrolled {direction} {abs(amount)} notches."
        except Exception as exc:
            return f"Mouse scroll failed: {exc}"

    if name in (
        "mouse_drag",
        "drag_mouse",
    ):
        button = str(action.get("button", "left")).lower().strip()
        duration = action.get("duration", 0.5)

        if button != "left":
            return "Mouse drag only supports the left button."

        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not 0.1 <= duration <= 3
        ):
            return "Mouse drag duration must be between 0.1 and 3 seconds."

        try:
            screen_size = pyautogui.size()
            start = _validated_mouse_point(
                action,
                screen_size,
                "start_x",
                "start_y",
            )
            end = _validated_mouse_point(
                action,
                screen_size,
                "end_x",
                "end_y",
            )
        except Exception as exc:
            return f"Could not read screen bounds: {exc}"

        if start is None or end is None:
            return "Drag coordinates must be integer pixels on the primary display."

        start_x, start_y = start
        end_x, end_y = end

        if not ask_local_confirmation(
            root,
            "Zanel wants to drag the mouse",
            f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y}) "
            f"on the primary display over {duration:g} seconds?",
        ):
            return "User declined the mouse drag."

        try:
            current_screen_size = pyautogui.size()
            if (
                _validated_mouse_point(
                    action,
                    current_screen_size,
                    "start_x",
                    "start_y",
                ) is None
                or _validated_mouse_point(
                    action,
                    current_screen_size,
                    "end_x",
                    "end_y",
                ) is None
            ):
                return "Mouse drag canceled because the screen bounds changed."

            pyautogui.moveTo(start_x, start_y, duration=0.1)
            pyautogui.dragTo(
                end_x,
                end_y,
                duration=float(duration),
                button=button,
            )
            return (
                f"Dragged from ({start_x}, {start_y}) "
                f"to ({end_x}, {end_y})."
            )
        except Exception as exc:
            return f"Mouse drag failed: {exc}"

    if name in ("type_text", "type", "text_type"):
        text = str(
            action.get("text", "")
        )

        if not text:
            return "No text supplied."

        if not ask_local_confirmation(
            root,
            "Zanel wants to type text",
            "Focus the target window within 3 seconds, then Zanel will type:\n\n"
            + text,
        ):
            return "User declined typing."

        try:
            pyperclip.copy(text)
            if _wait_for_action(cancel_event, 3):
                return "Action canceled."

            pyautogui.hotkey("ctrl", "v")

            return "Typed the requested text."

        except Exception as exc:
            return f"Typing failed: {exc}"

    if name in (
        "wifi_status",
        "wifi",
        "network_status",
    ):
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "$wifi = Get-NetConnectionProfile "
                    "-ErrorAction SilentlyContinue; "
                    "$adapter = Get-NetAdapter "
                    "-Name 'Wi-Fi' "
                    "-ErrorAction SilentlyContinue; "
                    "if ($adapter) { "
                    "$ssid = (netsh wlan show interfaces | "
                    "Select-String '^\s*SSID\s*:').Line; "
                    "$ssid = $ssid -replace "
                    "'^\s*SSID\s*:\s*', ''; "
                    "[PSCustomObject]@{ "
                    "Status=$adapter.Status; "
                    "SSID=$ssid; "
                    "Network=$wifi.Name; "
                    "Signal=$adapter.LinkSpeed "
                    "} | ConvertTo-Json -Compress "
                    "} else { "
                    "[PSCustomObject]@{ "
                    "Status='Wi-Fi adapter not found' "
                    "} | ConvertTo-Json -Compress "
                    "}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                return "Could not check Wi-Fi status."

            data = json.loads(
                result.stdout
            )

            status = str(
                data.get("Status", "Unknown")
            )

            if status.lower() != "up":
                return (
                    f"Wi-Fi status: {status}."
                )

            ssid = str(
                data.get("SSID", "")
            ).strip()

            network = str(
                data.get("Network", "")
            ).strip()

            speed = str(
                data.get("Signal", "")
            ).strip()

            details = []

            if ssid:
                details.append(
                    f"SSID: {ssid}"
                )

            if network:
                details.append(
                    f"Network: {network}"
                )

            if speed:
                details.append(
                    f"Link speed: {speed}"
                )

            if details:
                return (
                    "Wi-Fi is connected. "
                    + " | ".join(details)
                )

            return "Wi-Fi is connected."

        except (
            json.JSONDecodeError,
            subprocess.SubprocessError,
            Exception,
        ) as exc:
            return (
                f"Could not check Wi-Fi status: "
                f"{exc}"
            )

    if name in (
        "time",
        "currenttime",
        "current_time",
        "thetime",
        "the_time",
        "localtime",
        "local_time",
    ):
        try:
            current_time = datetime.now().strftime(
                "%I:%M %p"
            )

            return (
                f"The current local time is "
                f"{current_time}."
            )

        except Exception as exc:
            return (
                f"Could not get the current time: "
                f"{exc}"
            )

    if name in (
        "press_key",
        "press",
        "key_press",
    ):
        key = str(
            action.get("key", "")
        ).strip()

        if not key:
            return "No key supplied."

        key_aliases = {
            "return": "enter",
            "escape": "esc",
            "spacebar": "space",
            "windows": "win",
            "control": "ctrl",
            "ctl": "ctrl",
            "option": "alt",
            "del": "delete",
            "ins": "insert",
            "pgup": "pageup",
            "pgdn": "pagedown",
            "page_up": "pageup",
            "page_down": "pagedown",
            "left_arrow": "left",
            "right_arrow": "right",
            "up_arrow": "up",
            "down_arrow": "down",
        }

        key = key_aliases.get(
            key.lower(),
            key.lower(),
        )

        allowed_keys = {
            "backspace",
            "tab",
            "enter",
            "space",
            "shift",
            "ctrl",
            "alt",
            "win",
            "left",
            "right",
            "up",
            "down",
            "home",
            "end",
            "pageup",
            "pagedown",
            "delete",
            "insert",
            "capslock",
            "numlock",
            "scrolllock",
            "printscreen",
            "pause",
            "f1",
            "f2",
            "f3",
            "f4",
            "f5",
            "f6",
            "f7",
            "f8",
            "f9",
            "f10",
            "f11",
            "f12",
            "f13",
            "f14",
            "f15",
            "f16",
            "f17",
            "f18",
            "f19",
            "f20",
            "f21",
            "f22",
            "f23",
            "f24",
        }

        if len(key) == 1:
            allowed = True
        else:
            allowed = key in allowed_keys

        if not allowed:
            return f"Unsupported key: {key}"

        if not ask_local_confirmation(
            root,
            "Zanel wants to press a key",
            f"Zanel will press:\n\n{key}",
        ):
            return "User declined key press."

        try:
            pyautogui.press(key)

            return f"Pressed {key}."

        except Exception as exc:
            return f"Key press failed: {exc}"

    if name in (
        "ram_usage",
        "ram",
        "memory_usage",
        "memory",
    ):
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "$os = Get-CimInstance "
                    "Win32_OperatingSystem; "
                    "$total = [math]::Round("
                    "$os.TotalVisibleMemorySize / 1MB, 2); "
                    "$free = [math]::Round("
                    "$os.FreePhysicalMemory / 1MB, 2); "
                    "$used = [math]::Round("
                    "$total - $free, 2); "
                    "$percent = [math]::Round("
                    "($used / $total) * 100, 1); "
                    "[PSCustomObject]@{ "
                    "Total=$total; "
                    "Used=$used; "
                    "Free=$free; "
                    "Percent=$percent "
                    "} | ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                return "Could not check RAM usage."

            data = json.loads(
                result.stdout
            )

            total = data.get("Total")
            used = data.get("Used")
            free = data.get("Free")
            percent = data.get("Percent")

            return (
                f"RAM usage: {used} GB used "
                f"of {total} GB "
                f"({percent}%). "
                f"{free} GB available."
            )

        except (
            json.JSONDecodeError,
            subprocess.SubprocessError,
            Exception,
        ) as exc:
            return (
                f"Could not check RAM usage: "
                f"{exc}"
            )

    if name in (
        "write_text_file",
        "create_text_file",
        "write_txt_file",
    ):
        filename = str(
            action.get("filename", "")
        ).strip()

        text = str(
            action.get("text", "")
        )

        if not filename:
            return "No filename supplied."

        if (
            os.path.basename(filename) != filename
            or "/" in filename
            or "\\" in filename
        ):
            return (
                "Blocked: the filename must be a simple "
                "file name without a directory path."
            )

        if not filename.lower().endswith(".txt"):
            filename += ".txt"

        downloads = os.path.join(
            os.path.expanduser("~"),
            "Downloads",
        )

        try:
            os.makedirs(
                downloads,
                exist_ok=True,
            )

            file_path = os.path.abspath(
                os.path.join(
                    downloads,
                    filename,
                )
            )

            downloads_path = os.path.abspath(
                downloads
            )

            if os.path.commonpath(
                [downloads_path, file_path]
            ) != downloads_path:
                return (
                    "Blocked: file must be saved "
                    "inside the Downloads folder."
                )

            if not ask_local_confirmation(
                root,
                "Zanel wants to create a text file",
                "Allow Zanel to create this file in "
                "your Downloads folder?\n\n"
                f"File:\n{filename}\n\n"
                "The file will be opened automatically "
                "in Notepad.",
            ):
                return "User declined creating the text file."

            with open(
                file_path,
                "w",
                encoding="utf-8",
                newline="",
            ) as file:
                file.write(text)

            subprocess.Popen(
                [
                    "notepad.exe",
                    file_path,
                ],
                shell=False,
            )

            return (
                f"Created {filename} in the Downloads "
                "folder and opened it in Notepad."
            )

        except OSError as exc:
            return (
                f"Could not create the text file: {exc}"
            )

        except Exception as exc:
            return (
                f"Could not create the text file: {exc}"
            )

    if name in (
        "internet_status",
        "internet",
        "internet_connection",
        "connection_status",
        "online_status",
        "online",
    ):
        try:
            request = urllib.request.Request(
                "https://www.google.com/generate_204",
                method="GET",
            )

            with urllib.request.urlopen(
                request,
                timeout=5,
            ) as response:
                if response.status in (
                    200,
                    204,
                ):
                    return (
                        "Internet connection is active."
                    )

                return (
                    "Internet connection test returned "
                    f"HTTP {response.status}."
                )

        except Exception:
            return "No active internet connection."

    if name in (
        "volume",
        "volumeset",
        "audioset",
    ):
        try:
            raw_percent = action.get("percent")

            if raw_percent is None:
                raw_percent = action.get(
                    "percentage"
                )

            if raw_percent is None:
                raw_percent = action.get(
                    "volume"
                )

            if raw_percent is None:
                return "No volume percentage supplied."

            if isinstance(raw_percent, str):
                raw_percent = (
                    raw_percent
                    .replace("%", "")
                    .strip()
                )

            percent = float(raw_percent)

            if not np.isfinite(percent):
                return "Invalid volume percentage."

            percent = max(
                0.0,
                min(
                    100.0,
                    percent,
                ),
            )

            percent = round(
                percent,
                2,
            )

        except (
            TypeError,
            ValueError,
        ):
            return "Invalid volume percentage."

        if percent.is_integer():
            display_percent = int(percent)
        else:
            display_percent = percent

        if not ask_local_confirmation(
            root,
            "Zanel wants to change the volume",
            f"Allow Zanel to set the master volume "
            f"to {display_percent}%?",
        ):
            return "User declined changing the volume."

        try:
            from pycaw.pycaw import (
                AudioUtilities,
            )

            devices = AudioUtilities.GetSpeakers()

            endpoint = devices.EndpointVolume

            endpoint.SetMasterVolumeLevelScalar(
                percent / 100.0,
                None,
            )

            return (
                f"Master volume set to "
                f"{display_percent}%."
            )

        except Exception as exc:
            return (
                f"Could not change volume: "
                f"{exc}"
            )
        

    if name in (
        "lock_pc",
        "lock_computer",
        "lock_windows",
    ):
        if not ask_local_confirmation(
            root,
            "Zanel wants to lock your PC",
            "Allow Zanel to lock your Windows PC?",
        ):
            return "User declined locking the PC."

        try:
            result = subprocess.run(
                [
                    "rundll32.exe",
                    "user32.dll,LockWorkStation",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                return (
                    "Could not lock the PC: "
                    f"{result.stderr.strip() or 'Windows returned an error.'}"
                )

            return "PC locked."

        except Exception as exc:
            return (
                f"Could not lock the PC: "
                f"{exc}"
            )

    if name in (
        "brightness",
        "brightnessset",
        "display_brightness",
    ):
        try:
            raw_percent = action.get("percent")

            if raw_percent is None:
                raw_percent = action.get(
                    "percentage"
                )

            if raw_percent is None:
                raw_percent = action.get(
                    "brightness"
                )

            if raw_percent is None:
                return "No brightness percentage supplied."

            if isinstance(raw_percent, str):
                raw_percent = (
                    raw_percent
                    .replace("%", "")
                    .strip()
                )

            percent = float(raw_percent)

            if not np.isfinite(percent):
                return "Invalid brightness percentage."

            percent = max(
                0.0,
                min(
                    100.0,
                    percent,
                ),
            )

            percent = round(
                percent,
                2,
            )

        except (
            TypeError,
            ValueError,
        ):
            return "Invalid brightness percentage."

        if percent.is_integer():
            display_percent = int(percent)
        else:
            display_percent = percent

        if not ask_local_confirmation(
            root,
            "Zanel wants to change the brightness",
            f"Allow Zanel to set the display brightness "
            f"to {display_percent}%?",
        ):
            return "User declined changing the brightness."

        try:
            from ctypes import (
                POINTER,
                byref,
                wintypes,
            )

            user32 = ctypes.WinDLL(
                "user32",
                use_last_error=True,
            )

            dxva2 = ctypes.WinDLL(
                "Dxva2",
                use_last_error=True,
            )

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HMONITOR,
                wintypes.HDC,
                POINTER(wintypes.RECT),
                wintypes.LPARAM,
            )

            class PHYSICAL_MONITOR(
                ctypes.Structure
            ):
                _fields_ = [
                    (
                        "hPhysicalMonitor",
                        wintypes.HANDLE,
                    ),
                    (
                        "szPhysicalMonitorDescription",
                        wintypes.WCHAR * 128,
                    ),
                ]

            dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [
                wintypes.HMONITOR,
                POINTER(wintypes.DWORD),
            ]

            dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = (
                wintypes.BOOL
            )

            dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [
                wintypes.HMONITOR,
                wintypes.DWORD,
                POINTER(PHYSICAL_MONITOR),
            ]

            dxva2.GetPhysicalMonitorsFromHMONITOR.restype = (
                wintypes.BOOL
            )

            dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [
                wintypes.HANDLE,
                wintypes.BYTE,
                wintypes.BYTE,
                POINTER(wintypes.BYTE),
                POINTER(wintypes.DWORD),
                POINTER(wintypes.DWORD),
            ]

            dxva2.GetVCPFeatureAndVCPFeatureReply.restype = (
                wintypes.BOOL
            )

            dxva2.SetVCPFeature.argtypes = [
                wintypes.HANDLE,
                wintypes.BYTE,
                wintypes.DWORD,
            ]

            dxva2.SetVCPFeature.restype = (
                wintypes.BOOL
            )

            dxva2.DestroyPhysicalMonitors.argtypes = [
                wintypes.DWORD,
                POINTER(PHYSICAL_MONITOR),
            ]

            dxva2.DestroyPhysicalMonitors.restype = (
                wintypes.BOOL
            )

            physical_monitors = []

            def monitor_callback(
                hmonitor,
                hdc,
                rect,
                data,
            ):
                count = wintypes.DWORD()

                if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(
                    hmonitor,
                    byref(count),
                ):
                    return True

                if count.value <= 0:
                    return True

                monitors = (
                    PHYSICAL_MONITOR * count.value
                )()

                if dxva2.GetPhysicalMonitorsFromHMONITOR(
                    hmonitor,
                    count.value,
                    monitors,
                ):
                    for monitor in monitors:
                        physical_monitors.append(
                            monitor
                        )

                return True

            callback = MONITORENUMPROC(
                monitor_callback
            )

            if not user32.EnumDisplayMonitors(
                None,
                None,
                callback,
                0,
            ):
                physical_monitors = []

            ddc_success = False

            for monitor in physical_monitors:
                try:
                    current_value = wintypes.DWORD()
                    maximum_value = wintypes.DWORD()
                    capabilities = wintypes.BYTE()
                    vcp_type = wintypes.BYTE()

                    supported = (
                        dxva2.GetVCPFeatureAndVCPFeatureReply(
                            monitor.hPhysicalMonitor,
                            0x10,
                            0,
                            byref(vcp_type),
                            byref(current_value),
                            byref(maximum_value),
                        )
                    )

                    if not supported:
                        continue

                    maximum = maximum_value.value

                    if maximum <= 0:
                        continue

                    target_value = round(
                        maximum
                        * (
                            display_percent
                            / 100.0
                        )
                    )

                    target_value = max(
                        0,
                        min(
                            maximum,
                            target_value,
                        ),
                    )

                    if dxva2.SetVCPFeature(
                        monitor.hPhysicalMonitor,
                        0x10,
                        target_value,
                    ):
                        ddc_success = True

                except Exception:
                    continue

            if physical_monitors:
                try:
                    monitor_array = (
                        PHYSICAL_MONITOR
                        * len(physical_monitors)
                    )(*physical_monitors)

                    dxva2.DestroyPhysicalMonitors(
                        len(physical_monitors),
                        monitor_array,
                    )

                except Exception:
                    pass

            if ddc_success:
                return (
                    f"Display brightness set to "
                    f"{display_percent}%."
                )

            wmi_result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "$methods = "
                        "Get-CimInstance "
                        "-Namespace root/WMI "
                        "-ClassName "
                        "WmiMonitorBrightnessMethods; "
                        f"$methods | ForEach-Object "
                        "{ $_.WmiSetBrightness(1,"
                        f"{display_percent}"
                        ") }"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if wmi_result.returncode == 0:
                return (
                    f"Display brightness set to "
                    f"{display_percent}%."
                )

            return (
                "Could not change brightness. "
                "The display does not appear to support "
                "DDC/CI or Windows software brightness control."
            )

        except Exception as exc:
            return (
                f"Could not change brightness: "
                f"{exc}"
            )

    if name in (
        "close_zanel",
        "zanel_close",
        "shutdown_command",
    ):
        if not ask_local_confirmation(
            root,
            "Zanel wants to close",
            "Allow Zanel to shut itself down?",
        ):
            return (
                "CLOSE_ZANEL_DECLINED: "
                "The user declined the shutdown request."
            )

        try:
            root.after(
                100,
                root.destroy,
            )

            return (
                "CLOSE_ZANEL_SUCCESS: "
                "Zanel shutdown was approved and initiated."
            )

        except Exception as exc:
            return (
                f"CLOSE_ZANEL_FAILED: "
                f"Could not close Zanel: {exc}"
            )

    if name in (
        "silent_mode",
        "mute_zanel",
        "quiet_mode",
    ):
        if app is None:
            return "Silent mode control is unavailable."

        enabled = bool(
            action.get(
                "enabled",
                True,
            )
        )

        if not ask_local_confirmation(
            root,
            "Zanel wants to change silent mode",
            (
                "Allow Zanel to "
                + (
                    "disable TTS (Zanel will stop speaking)"
                    if enabled
                    else "enable TTS (Zanel will speak again)"
                )
                + "?"
            ),
        ):
            return "User declined changing silent mode."

        return app.set_silent_mode(enabled)

    if name in (
        "spotify_play",
        "play_spotify",
        "play_spotify_song",
    ):
        song = str(
            action.get("song")
            or action.get("query")
            or action.get("track")
            or ""
        )
        song = " ".join(song.split())

        if not song:
            return "No Spotify song supplied."

        if len(song) > 120:
            return "Spotify song searches must be 120 characters or fewer."

        if cancel_event is not None and cancel_event.is_set():
            return "Action canceled."

        try:
            spotify_window = find_window_match("Spotify")

            if spotify_window is None:
                launch_result = execute_action(
                    {
                        "action": "open_app",
                        "app_name": "Spotify",
                    },
                    root,
                    mic_callback,
                    app=app,
                    cancel_event=cancel_event,
                )

                if cancel_event is not None and cancel_event.is_set():
                    return "Action canceled."

                if not launch_result.startswith(
                    ("Launched ", "Launch command was sent")
                ):
                    return f"Could not open Spotify: {launch_result}"

                deadline = time.time() + 15
                while time.time() < deadline:
                    if cancel_event is not None and cancel_event.is_set():
                        return "Action canceled."

                    if find_window_match("Spotify") is not None:
                        break
                    if _wait_for_action(cancel_event, 0.5):
                        return "Action canceled."
                else:
                    return (
                        "Spotify was launched, but its window did not appear "
                        "within 15 seconds."
                    )
        except Exception as exc:
            if cancel_event is not None and cancel_event.is_set():
                return "Action canceled."
            return f"Could not locate or open Spotify: {exc}"

        if cancel_event is not None and cancel_event.is_set():
            return "Action canceled."

        if not ask_local_confirmation(
            root,
            "Zanel wants to play a Spotify song",
            f"Search Spotify for:\n\n{song}\n\n"
            "Zanel will open Spotify if needed and play the best "
            "matching song.",
        ):
            return "User declined Spotify playback."

        if cancel_event is not None and cancel_event.is_set():
            return "Action canceled."

        return play_spotify_song(song, cancel_event=cancel_event)

    if name in (
        "youtube_play",
        "play_youtube",
        "play_youtube_video",
    ):
        video = str(
            action.get("video")
            or action.get("query")
            or action.get("title")
            or action.get("song")
            or ""
        )
        video = " ".join(video.split())

        if not video:
            return "No YouTube video supplied."

        if len(video) > 120:
            return "YouTube searches must be 120 characters or fewer."

        if cancel_event is not None and cancel_event.is_set():
            return "Action canceled."

        if not ask_local_confirmation(
            root,
            "Zanel wants to play a YouTube video",
            f"Open YouTube and search for:\n\n{video}\n\n"
            "Zanel will skip results labeled as ads or sponsored and click "
            "the closest matching organic video.",
        ):
            return "User declined YouTube playback."

        if cancel_event is not None and cancel_event.is_set():
            return "Action canceled."

        return play_youtube_video(video, cancel_event=cancel_event)

    if name in (
        "play_music",
        "music",
        "play_song",
    ):
        if app is None:
            return "Music control is unavailable."

        song = str(
            action.get("song")
            or action.get("music")
            or action.get("track")
            or ""
        ).strip()

        if not song:
            return "No music selection supplied."

        return app.play_music(
            song,
            root,
        )

    if name in (
        "stop_music",
        "music_stop",
        "stop_song",
    ):
        if app is None:
            return "Music control is unavailable."

        if not ask_local_confirmation(
            root,
            "Zanel wants to stop music",
            "Allow Zanel to stop the currently playing music?",
        ):
            return "User declined stopping music."

        return app.stop_music()

    if name in (
        "install_app",
        "install",
        "install_software",
        "install_program",
    ):
        requested = str(
            action.get("app_name")
            or action.get("name")
            or action.get("app")
            or action.get("program")
            or action.get("query")
            or ""
        ).strip().lstrip("-").strip()

        requested = " ".join(requested.split())[:80]

        if not requested:
            return "No application name supplied."

        if not re.fullmatch(r"[\w .+&'()\-]+", requested):
            return "Blocked: the application name contains invalid characters."

        preferred_source = str(
            action.get("source") or ""
        ).lower().strip()

        try:
            executable = find_winget()

            if not executable:
                if not ask_local_confirmation(
                    root,
                    "Zanel wants to open the Microsoft Store",
                    "WinGet was not found on this PC.\n\n"
                    f"Open the Microsoft Store search for:\n\n{requested}",
                ):
                    return "User declined opening the Microsoft Store."

                os.startfile(
                    "ms-windows-store://search/?query="
                    + urllib.parse.quote(requested)
                )

                return (
                    "WinGet is not installed, so I opened the Microsoft "
                    f"Store search for {requested}. The user must install "
                    "it manually from there."
                )

            candidates = winget_candidates(
                executable,
                requested,
                preferred_source,
            )

            if not candidates:
                return (
                    f"Could not find a trusted match for '{requested}' "
                    "in the WinGet repository or the Microsoft Store."
                )

            last_error = ""

            for candidate in candidates[:3]:
                if winget_is_installed(executable, candidate):
                    return f"{candidate['name']} is already installed."

                publisher = winget_publisher(executable, candidate)

                if candidate["source"] == "msstore":
                    source_label = "Microsoft Store"
                else:
                    source_label = "WinGet repository (hash verified)"

                if not ask_local_confirmation(
                    root,
                    "Zanel wants to install an app",
                    f"Requested:\n\n{requested}\n\n"
                    f"Found:\n\n{candidate['name']}\n"
                    f"Publisher: {publisher}\n"
                    f"Source: {source_label}\n"
                    f"ID: {candidate['id']}\n\n"
                    "Install this app?",
                ):
                    return "User declined installing the app."

                base_args = [
                    "install",
                    "--id",
                    candidate["id"],
                    "--source",
                    candidate["source"],
                    "--exact",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]

                for extra in ([], ["--scope", "user"]):
                    code, output = run_winget(
                        executable,
                        base_args + extra,
                        900,
                    )

                    if code == 0:
                        return (
                            f"Installed {candidate['name']} from "
                            f"{source_label}."
                        )

                    if (
                        code == WINGET_ALREADY_INSTALLED
                        or "already installed" in output.lower()
                    ):
                        return f"{candidate['name']} is already installed."

                    last_error = winget_tail(output)

            return (
                f"Could not install '{requested}'. "
                f"Last error: {last_error or 'Unknown error.'}"
            )

        except Exception as exc:
            return f"Could not install the application: {exc}"

    if name in (
        "delete_file",
        "delete",
        "remove_file",
        "delete_folder",
        "remove_folder",
        "trash_file",
    ):
        requested = str(
            action.get("path")
            or action.get("file")
            or action.get("filename")
            or action.get("name")
            or ""
        ).strip().strip('"').strip("'")

        hint = str(
            action.get("location")
            or action.get("where")
            or action.get("directory")
            or action.get("in")
            or ""
        ).strip()

        kind = str(
            action.get("kind") or action.get("type") or ""
        ).lower().strip()

        want_folder = (
            name in ("delete_folder", "remove_folder")
            or kind in ("folder", "directory", "dir")
        )

        if not requested:
            return "No file name supplied."

        try:
            expanded = os.path.expandvars(os.path.expanduser(requested))
            trimmed = expanded.rstrip("\\/")
            search_name = os.path.basename(trimmed)
            target = None

            if os.path.isabs(expanded) and os.path.lexists(expanded):
                target = os.path.abspath(expanded)
            else:
                if not hint and os.path.dirname(trimmed):
                    hint = os.path.dirname(trimmed)

            if target is None:
                if not search_name:
                    return "No valid file name supplied."

                matches = search_local_items(
                    search_name,
                    want_folder,
                    hint,
                )

                if not matches:
                    return (
                        f"Could not find a "
                        f"{'folder' if want_folder else 'file'} similar to "
                        f"'{search_name}'."
                    )

                top_score = matches[0][0]

                tied = [
                    path
                    for score, path in matches
                    if score >= top_score - 0.02
                ]

                if len(tied) > 1:
                    return (
                        "Found several matches: "
                        + "; ".join(tied[:5])
                        + ". Ask the user which one to delete, then use "
                        "the full path."
                    )

                target = matches[0][1]

            if not os.path.lexists(target):
                return f"Could not find '{requested}'."

            reason = protected_reason(target)

            if reason:
                return f"Blocked: {reason}"

            is_folder = os.path.isdir(target) and not os.path.islink(target)
            details = describe_item(target)
            warning = ""

            try:
                if not is_folder and os.path.getsize(target) > (1 << 30):
                    warning = (
                        "\n\nThis file is very large and may be deleted "
                        "permanently instead of going to the Recycle Bin."
                    )
            except OSError:
                pass

            if not ask_local_confirmation(
                root,
                "Zanel wants to delete "
                + ("a folder" if is_folder else "a file"),
                f"Move this to the Recycle Bin?\n\n{target}\n\n"
                f"{details}{warning}",
            ):
                return "User declined deleting the item."

            moved = send_to_recycle_bin(target)

            if not moved and os.path.lexists(target):
                clear_read_only(target)
                if _wait_for_action(cancel_event, 0.4):
                    return "Action canceled."

                moved = send_to_recycle_bin(target)

            if moved or not os.path.lexists(target):
                return (
                    f"Moved {os.path.basename(target)} to the Recycle Bin "
                    f"(from {os.path.dirname(target)})."
                )

            if not ask_local_confirmation(
                root,
                "Zanel wants to permanently delete an item",
                "The Recycle Bin could not be used.\n\n"
                f"Permanently delete this instead?\n\n{target}\n\n"
                "This cannot be undone.",
            ):
                return (
                    "Could not move the item to the Recycle Bin and the "
                    "user declined permanent deletion."
                )

            deleted, error = permanent_delete(target)

            if deleted:
                return (
                    f"Permanently deleted {os.path.basename(target)} "
                    f"(from {os.path.dirname(target)})."
                )

            return (
                f"Could not delete {os.path.basename(target)}: "
                f"{error or 'The item may be in use by another program.'}"
            )

        except Exception as exc:
            return f"Could not delete the item: {exc}"

    if name in (
        "uninstall_app",
        "uninstall",
        "remove_app",
        "uninstall_program",
        "uninstall_software",
    ):
        requested = str(
            action.get("app_name")
            or action.get("name")
            or action.get("app")
            or action.get("program")
            or action.get("query")
            or ""
        ).strip().lstrip("-").strip()

        requested = " ".join(requested.split())[:80]

        if not requested:
            return "No application name supplied."

        if not re.fullmatch(r"[\w .+&'()\-]+", requested):
            return "Blocked: the application name contains invalid characters."

        remove_data = str(
            action.get("remove_data", "")
        ).lower().strip() in ("true", "1", "yes")

        try:
            executable = find_winget()

            candidates, registry, appx = find_installed_apps(
                executable,
                requested,
            )

            if not candidates:
                return (
                    "Could not find an installed application similar "
                    f"to '{requested}'."
                )

            best = candidates[0]
            registry_match = None
            appx_match = None

            if best["source"] == "registry":
                registry_match = next(
                    (
                        entry
                        for entry in registry
                        if entry["key"] == best["id"]
                        and entry["name"] == best["name"]
                    ),
                    None,
                )
            else:
                registry_match = closest_entry(
                    registry,
                    best["name"],
                    "name",
                )

            if best["source"] == "appx":
                appx_match = next(
                    (
                        package
                        for package in appx
                        if package["name"] == best["id"]
                    ),
                    None,
                )
            else:
                appx_match = closest_entry(
                    appx,
                    best["name"],
                    "short",
                )

            methods = []

            if best["source"] == "winget" and executable:
                methods.append("winget")

            if appx_match:
                methods.append("appx")

            if registry_match:
                methods.append("registry")

            if not methods:
                return (
                    f"Found '{best['name']}' but could not find a way "
                    "to uninstall it."
                )

            publisher = "Unknown"

            if registry_match and registry_match["publisher"]:
                publisher = registry_match["publisher"]
            elif appx_match and appx_match["publisher"]:
                publisher = appx_match["publisher"]

            others = ", ".join(item["name"] for item in candidates[1:3])

            message = (
                f"Requested:\n\n{requested}\n\n"
                f"Found:\n\n{best['name']}\n"
                f"Version: {best['version'] or 'Unknown'}\n"
                f"Publisher: {publisher}\n"
            )

            if others:
                message += f"Other matches: {others}\n"

            message += "\nUninstall this app?"

            if not ask_local_confirmation(
                root,
                "Zanel wants to uninstall an app",
                message,
            ):
                return "User declined uninstalling the app."

            location = registry_match["location"] if registry_match else ""
            last_error = ""
            removed = False

            for method in methods:
                if method == "winget":
                    ok, error = uninstall_via_winget(executable, best)
                    removed = ok or not winget_is_installed(
                        executable,
                        best,
                    )
                elif method == "appx":
                    removed, error = uninstall_via_appx(appx_match)
                else:
                    removed, error = uninstall_via_registry(registry_match)

                if removed:
                    break

                last_error = error or last_error

            if not removed:
                return (
                    f"Could not uninstall '{best['name']}'. "
                    f"Last error: {last_error or 'Unknown error.'} "
                    "If the app is running, closing it and trying again "
                    "can help."
                )

            note = ""

            if remove_data:
                note = cleanup_leftovers(root, best["name"], location)

            return f"Uninstalled {best['name']}." + note

        except Exception as exc:
            return f"Could not uninstall the application: {exc}"

    if name in (
        "minimize_window",
        "minimise_window",
        "maximize_window",
        "maximise_window",
        "focus_window",
        "switch_window",
    ):
        requested = str(
            action.get("window")
            or action.get("app_name")
            or action.get("name")
            or action.get("title")
            or action.get("app")
            or action.get("program")
            or ""
        ).strip()

        if not requested:
            return "No window name supplied."

        if name.startswith("mini"):
            mode = "minimize"
        elif name.startswith("maxi"):
            mode = "maximize"
        else:
            mode = "focus"

        if app is not None and normalize_app_text(requested) in (
            "zanel",
            "zanelassistant",
            "zanelai",
        ):
            if mode == "minimize":
                root.after(0, app.minimize_window)
                return "Minimised Zanel."

            if mode == "focus":
                root.after(0, app.bring_to_front)
                return "Focused Zanel."

            return "Zanel cannot be maximised."

        try:
            return control_window(requested, mode)
        except Exception as exc:
            return f"Could not {mode} the window: {exc}"

    if name in (
        "bluetooth",
        "set_bluetooth",
        "toggle_bluetooth",
    ):
        raw = action.get("enabled")

        if raw is None:
            raw = action.get("state")

        if raw is None:
            raw = action.get("on")

        if raw is None:
            return "No Bluetooth state supplied."

        if isinstance(raw, str):
            raw = raw.strip().lower() in (
                "true",
                "1",
                "yes",
                "on",
                "enable",
                "enabled",
            )

        enabled = bool(raw)

        if not ask_local_confirmation(
            root,
            "Zanel wants to change Bluetooth",
            "Allow Zanel to turn Bluetooth "
            + ("on" if enabled else "off")
            + "?",
        ):
            return "User declined changing Bluetooth."

        return set_bluetooth_state(enabled)

    if name in (
        "bluetooth_connect",
        "connect_bluetooth",
        "bluetooth_pair",
        "connect_bluetooth_device",
    ):
        requested = str(
            action.get("device")
            or action.get("device_name")
            or action.get("name")
            or ""
        ).strip()

        requested = " ".join(requested.split())[:80]

        if not requested:
            return "No Bluetooth device name supplied."

        def confirm_device(device_name, paired):
            if paired:
                detail = "Connect to this paired Bluetooth device?"
            else:
                detail = (
                    "This device is not paired yet. Zanel will try to pair "
                    "and connect. If it asks for a PIN or password, Zanel "
                    "will deny it.\n\nPair and connect?"
                )

            return ask_local_confirmation(
                root,
                "Zanel wants to connect to a Bluetooth device",
                f"Requested:\n\n{requested}\n\n"
                f"Found:\n\n{device_name}\n\n"
                f"{detail}",
            )

        def confirm_enable():
            return ask_local_confirmation(
                root,
                "Zanel wants to turn on Bluetooth",
                "Bluetooth appears to be off. Allow Zanel to turn it on "
                "and continue connecting to:\n\n" + requested,
            )

        try:
            return connect_bluetooth_device(
                requested,
                confirm_device,
                confirm_enable,
            )
        except Exception as exc:
            return f"Could not connect to the Bluetooth device: {exc}"

    if name == "mute_mic":
        muted = bool(
            action.get("muted", True)
        )

        mic_callback(muted)

        return (
            "Microphone muted."
            if muted
            else "Microphone unmuted."
        )

    return f"Unknown action: {name}"
