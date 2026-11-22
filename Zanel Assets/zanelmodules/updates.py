import os
import threading
import time
import ctypes.wintypes
import ctypes
import requests
from zanelmodules.config import GITHUB_LATEST_RELEASE_API, GITHUB_RELEASES_URL, ZANEL_VERSION


class UpdateMixin:

    def parse_version(self, version):
        version = str(version or "").strip().lower()

        if version.startswith("v"):
            version = version[1:]

        parts = version.split(".")

        numbers = []

        for part in parts[:3]:
            digits = ""

            for char in part:
                if char.isdigit():
                    digits += char
                else:
                    break

            numbers.append(int(digits) if digits else 0)

        while len(numbers) < 3:
            numbers.append(0)

        return tuple(numbers)

    def begin_update_check(self):
        with self.update_lock:
            if self.update_info.get("checking"):
                return False

            self.update_info["checking"] = True
            return True

    def run_update_check(self):
        status = "error"
        latest_version = ""
        release_url = GITHUB_RELEASES_URL
        succeeded = False

        try:
            response = requests.get(
                GITHUB_LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Zanel-AI-Assistant"
                },
                timeout=10
            )

            if not response.ok:
                print(
                    f"Version check failed: "
                    f"GitHub HTTP {response.status_code}",
                    flush=True
                )
            else:
                data = response.json()

                if isinstance(data, dict):
                    latest_version = str(
                        data.get("tag_name") or ""
                    ).strip()

                    release_url = str(
                        data.get("html_url")
                        or GITHUB_RELEASES_URL
                    ).strip()

                if not latest_version:
                    print(
                        "Version check failed: no release version found",
                        flush=True
                    )
                else:
                    current = self.parse_version(
                        ZANEL_VERSION
                    )

                    latest = self.parse_version(
                        latest_version
                    )

                    print(
                        f"Zanel version: {ZANEL_VERSION} | "
                        f"Latest version: {latest_version}",
                        flush=True
                    )

                    if latest > current:
                        status = "outdated"
                    else:
                        status = "current"

                    succeeded = True

        except requests.RequestException as e:
            print(
                f"Version check network error: {e}",
                flush=True
            )

        except Exception as e:
            print(
                f"Version check error: {e}",
                flush=True
            )

        with self.update_lock:
            previous = dict(self.update_info)

            if succeeded:
                self.update_info = {
                    "status": status,
                    "checking": False,
                    "failed": False,
                    "latest": latest_version,
                    "url": release_url or GITHUB_RELEASES_URL,
                    "checked_at": time.time(),
                }
            else:
                self.update_info = {
                    **previous,
                    "checking": False,
                    "failed": True,
                    "checked_at": time.time(),
                }

            return dict(self.update_info)

    def fetch_update_info(self):
        if self.begin_update_check():
            return self.run_update_check()

        deadline = time.time() + 15

        while time.time() < deadline:
            with self.update_lock:
                info = dict(self.update_info)

            if not info.get("checking"):
                return info

            time.sleep(0.25)

        with self.update_lock:
            return dict(self.update_info)

    def start_update_check_async(self):
        if not self.begin_update_check():
            return False

        threading.Thread(
            target=self.run_update_check,
            daemon=True,
        ).start()

        return True

    def check_for_updates(self):
        try:
            info = self.fetch_update_info()

            if info.get("status") != "outdated":
                return

            latest_version = info.get("latest") or "Unknown"
            release_url = (
                info.get("url")
                or GITHUB_RELEASES_URL
            )

            message = (
                "Your version of Zanel is outdated.\n\n"
                f"Installed version: {ZANEL_VERSION}\n"
                f"Latest version: {latest_version}\n\n"
                "Please update Zanel from GitHub."
            )

            result = ctypes.windll.user32.MessageBoxW(
                0,
                message,
                "Zanel Update Available",
                0x00000040
            )

            if result == 1:
                try:
                    os.startfile(
                        release_url
                    )

                except Exception as e:
                    print(
                        f"Could not open update page: {e}",
                        flush=True
                    )

        except Exception as e:
            print(
                f"Version check error: {e}",
                flush=True
            )
