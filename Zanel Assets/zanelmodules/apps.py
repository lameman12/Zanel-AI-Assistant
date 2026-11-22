import json
import os
import difflib
import shutil
import subprocess
import time
import re


def find_winget():
    path = shutil.which("winget")

    if path:
        return path

    candidate = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft",
        "WindowsApps",
        "winget.exe",
    )

    if os.path.isfile(candidate):
        return candidate

    return None


def run_winget(executable, args, timeout=60):
    try:
        completed = subprocess.run(
            [executable] + list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return None, "Timed out."
    except Exception as exc:
        return None, str(exc)

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")

    return completed.returncode & 0xFFFFFFFF, output


def winget_tail(output):
    lines = []

    for line in str(output or "").replace("\r", "\n").split("\n"):
        stripped = line.strip()

        if not stripped:
            continue

        if set(stripped) <= set("-\\|/ "):
            continue

        lines.append(stripped)

    return " ".join(lines[-3:])[:300]


def parse_winget_table(output):
    lines = [
        line.rstrip()
        for line in str(output or "").replace("\r", "\n").split("\n")
    ]

    start = None

    for index, line in enumerate(lines):
        if (
            line.startswith("---")
            and index > 0
            and lines[index - 1].strip()
        ):
            start = index
            break

    if start is None:
        return []

    header = lines[start - 1]
    id_position = header.find("Id")
    version_position = header.find("Version")

    if id_position < 0 or version_position <= id_position:
        return []

    rows = []

    for line in lines[start + 1:]:
        if not line.strip() or len(line) <= version_position:
            continue

        name = line[:id_position].strip()
        package_id = line[id_position:version_position].strip()
        rest = line[version_position:].split()

        if not name or not package_id or " " in package_id:
            continue

        rows.append(
            {
                "name": name,
                "id": package_id,
                "version": rest[0] if rest else "",
            }
        )

    return rows


def normalize_app_text(value):
    return "".join(
        character
        for character in str(value or "").lower()
        if character.isalnum()
    )


def score_app_match(requested, row):
    name = normalize_app_text(row.get("name"))
    package_id = normalize_app_text(row.get("id"))

    if not requested or not name:
        return 0.0

    if requested == name:
        return 1.0

    score = difflib.SequenceMatcher(
        None,
        requested,
        name,
    ).ratio()

    if requested in name:
        score = max(
            score,
            0.92 - min(0.3, 0.02 * (len(name) - len(requested))),
        )

    if requested in package_id:
        score = max(score, 0.75)

    return score


def winget_candidates(executable, requested, preferred_source=""):
    sources = ("winget", "msstore")

    if preferred_source in sources:
        sources = (preferred_source,)

    wanted = normalize_app_text(requested)
    found = []
    seen = set()

    for source in sources:
        code, output = run_winget(
            executable,
            [
                "search",
                "--query",
                requested,
                "--source",
                source,
                "--accept-source-agreements",
            ],
            45,
        )

        if code != 0:
            continue

        for row in parse_winget_table(output):
            key = (source, row["id"].lower())

            if key in seen:
                continue

            seen.add(key)

            score = score_app_match(wanted, row)

            if score < 0.6:
                continue

            if source == "winget":
                score += 0.03

            found.append(
                {
                    "name": row["name"],
                    "id": row["id"],
                    "version": row["version"],
                    "source": source,
                    "score": score,
                }
            )

    found.sort(
        key=lambda item: (
            -item["score"],
            len(item["name"]),
        )
    )

    return found[:4]


def winget_publisher(executable, candidate):
    code, output = run_winget(
        executable,
        [
            "show",
            "--id",
            candidate["id"],
            "--source",
            candidate["source"],
            "--exact",
            "--accept-source-agreements",
        ],
        45,
    )

    if code != 0:
        return "Unknown"

    match = re.search(
        r"(?im)^\s*Publisher\s*:\s*(.+)$",
        output,
    )

    if match:
        return match.group(1).strip()[:80]

    return "Unknown"


def winget_is_installed(executable, candidate):
    code, output = run_winget(
        executable,
        [
            "list",
            "--id",
            candidate["id"],
            "--exact",
            "--accept-source-agreements",
        ],
        45,
    )

    return code == 0 and candidate["id"].lower() in output.lower()


def registry_uninstall_entries():
    entries = []

    try:
        import winreg
    except ImportError:
        return entries

    locations = (
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_CURRENT_USER, 0),
    )

    path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"

    fields = (
        "DisplayName",
        "DisplayVersion",
        "Publisher",
        "UninstallString",
        "QuietUninstallString",
        "InstallLocation",
        "SystemComponent",
        "ParentKeyName",
    )

    for hive, flag in locations:
        try:
            root_key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ | flag)
        except OSError:
            continue

        with root_key:
            index = 0

            while True:
                try:
                    subkey = winreg.EnumKey(root_key, index)
                except OSError:
                    break

                index += 1
                values = {}

                try:
                    with winreg.OpenKey(root_key, subkey) as item:
                        for field in fields:
                            try:
                                values[field] = str(
                                    winreg.QueryValueEx(item, field)[0] or ""
                                )
                            except OSError:
                                values[field] = ""
                except OSError:
                    continue

                if (
                    not values["DisplayName"]
                    or values["SystemComponent"] == "1"
                    or values["ParentKeyName"]
                ):
                    continue

                if (
                    not values["UninstallString"]
                    and not values["QuietUninstallString"]
                ):
                    continue

                entries.append(
                    {
                        "name": values["DisplayName"].strip(),
                        "version": values["DisplayVersion"].strip(),
                        "publisher": values["Publisher"].strip(),
                        "uninstall": values["UninstallString"].strip(),
                        "quiet": values["QuietUninstallString"].strip(),
                        "location": values["InstallLocation"].strip().strip('"'),
                        "key": subkey,
                    }
                )

    return entries


def registry_entry_exists(entry):
    for item in registry_uninstall_entries():
        if item["key"] == entry["key"] and item["name"] == entry["name"]:
            return True

    return False


def appx_packages():
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-AppxPackage | "
                "Where-Object { -not $_.IsFramework -and -not $_.NonRemovable } | "
                "Select-Object Name,PackageFullName,Publisher | "
                "ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return []

    if completed.returncode != 0 or not completed.stdout.strip():
        return []

    try:
        data = json.loads(completed.stdout)
    except ValueError:
        return []

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return []

    packages = []

    for item in data:
        if not isinstance(item, dict):
            continue

        package_name = str(item.get("Name") or "")
        full_name = str(item.get("PackageFullName") or "")

        if not package_name or not full_name:
            continue

        packages.append(
            {
                "name": package_name,
                "full": full_name,
                "publisher": str(item.get("Publisher") or "")[:60],
                "short": package_name.split(".")[-1],
            }
        )

    return packages


def closest_entry(entries, name, field):
    wanted = normalize_app_text(name)
    best = None
    best_score = 0.0

    for entry in entries:
        score = score_app_match(
            wanted,
            {"name": entry[field], "id": ""},
        )

        if score > best_score:
            best = entry
            best_score = score

    if best_score >= 0.9:
        return best

    return None


def find_installed_apps(executable, requested):
    wanted = normalize_app_text(requested)
    registry = registry_uninstall_entries()
    appx = appx_packages()
    candidates = []

    if executable:
        code, output = run_winget(
            executable,
            [
                "list",
                "--query",
                requested,
                "--accept-source-agreements",
            ],
            60,
        )

        if code == 0:
            for row in parse_winget_table(output):
                score = score_app_match(wanted, row)

                if score >= 0.7:
                    candidates.append(
                        {
                            "name": row["name"],
                            "id": row["id"],
                            "version": row["version"],
                            "source": "winget",
                            "score": score + 0.02,
                        }
                    )

    for entry in registry:
        score = score_app_match(
            wanted,
            {"name": entry["name"], "id": ""},
        )

        if score >= 0.7:
            candidates.append(
                {
                    "name": entry["name"],
                    "id": entry["key"],
                    "version": entry["version"],
                    "source": "registry",
                    "score": score,
                }
            )

    for package in appx:
        score = score_app_match(
            wanted,
            {"name": package["short"], "id": package["name"]},
        )

        if score >= 0.7:
            candidates.append(
                {
                    "name": package["short"],
                    "id": package["name"],
                    "version": "",
                    "source": "appx",
                    "score": score,
                }
            )

    candidates = [
        item
        for item in candidates
        if "zanel" not in normalize_app_text(item["name"])
    ]

    candidates.sort(key=lambda item: (-item["score"], len(item["name"])))

    unique = []
    seen = set()

    for item in candidates:
        key = normalize_app_text(item["name"])

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique[:5], registry, appx


def uninstall_via_winget(executable, candidate):
    variants = [
        ["--id", candidate["id"], "--exact"],
        ["--id", candidate["id"], "--exact", "--force"],
        ["--name", candidate["name"], "--exact"],
    ]

    last_error = ""

    for variant in variants:
        code, output = run_winget(
            executable,
            ["uninstall"]
            + variant
            + [
                "--silent",
                "--accept-source-agreements",
                "--disable-interactivity",
            ],
            900,
        )

        if code == 0:
            return True, ""

        last_error = winget_tail(output)

    return False, last_error


def uninstall_via_appx(package):
    full_name = package["full"]

    if not re.fullmatch(r"[\w.~\-]+", full_name):
        return False, "Invalid package name."

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Remove-AppxPackage -Package '{full_name}' -ErrorAction Stop",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as exc:
        return False, str(exc)

    still_installed = any(
        item["full"] == full_name for item in appx_packages()
    )

    if completed.returncode == 0 and not still_installed:
        return True, ""

    return (
        False,
        winget_tail(completed.stderr or completed.stdout)
        or "Remove-AppxPackage failed.",
    )


def uninstall_via_registry(entry):
    quiet = entry["quiet"].strip()
    plain = entry["uninstall"].strip()
    guid = re.search(r"\{[0-9A-Fa-f\-]{36}\}", plain)
    is_msi = bool(guid) and "msiexec" in plain.lower()
    commands = []

    if is_msi:
        commands.append(
            (f"msiexec.exe /x {guid.group(0)} /qn /norestart", True, 900)
        )

    if quiet:
        commands.append((quiet, True, 900))

    if plain and not is_msi:
        for suffix in (
            " /S",
            " /VERYSILENT /SUPPRESSMSGBOXES /NORESTART",
            " /quiet /norestart",
            "",
        ):
            commands.append(
                (plain + suffix, bool(suffix), 180 if suffix else 600)
            )

    last_error = "No uninstall command was available."

    for command, hidden, limit in commands:
        returned_ok = False

        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=limit,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if hidden else 0
                ),
            )
            last_error = f"Uninstaller exit code {completed.returncode}."
            returned_ok = completed.returncode in (0, 3010)
        except subprocess.TimeoutExpired:
            last_error = "The uninstaller timed out."
        except Exception as exc:
            last_error = str(exc)

        deadline = time.time() + (60 if returned_ok else 8)

        while time.time() < deadline:
            if not registry_entry_exists(entry):
                return True, ""

            time.sleep(2)

        if returned_ok:
            return (
                False,
                "The uninstaller finished but the app is still listed.",
            )

    return False, last_error
