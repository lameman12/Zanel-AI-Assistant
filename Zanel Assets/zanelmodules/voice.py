import json
import os
import queue
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from collections import deque
import winsound
import urllib.request
import uuid
import ctypes.wintypes
import ctypes
import numpy as np
import requests
import sounddevice as sd
from zanelmodules.config import (
    BLOCK_SECONDS,
    CHANNELS,
    ENERGY_THRESHOLD,
    MAX_GAIN,
    MAX_IDLE_SECONDS,
    MAX_RECORD_SECONDS,
    MIC_SENSITIVITY_LEVELS,
    MUSIC_TEMP_DIR,
    MUSIC_URLS,
    PRE_ROLL_BLOCKS,
    SAMPLE_RATE,
    SILENCE_BLOCKS_TO_STOP,
    START_SPEECH_BLOCKS,
    TARGET_PEAK,
    TTS_FORMAT,
    TTS_URL,
)
from zanelmodules.dialogs import ask_local_confirmation


class VoiceMixin:

    def stop_rickroll(self):
        with self.rickroll_lock:
            process_id = self.rickroll_process
            self.rickroll_process = None

        if process_id:
            kernel32 = ctypes.windll.kernel32

            process_handle = kernel32.OpenProcess(
                0x0001,
                False,
                process_id,
            )

            if process_handle:
                kernel32.TerminateProcess(
                    process_handle,
                    0,
                )

                kernel32.CloseHandle(
                    process_handle
                )

    def cleanup_music_file(self):
        with self.music_lock:
            media_pid = self.music_process
            temp_file = self.music_temp_file

            self.music_process = None
            self.music_temp_file = None

        if media_pid:
            try:
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(media_pid),
                        "/F",
                    ],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

        if temp_file:
            for _ in range(60):
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    break
                except PermissionError:
                    time.sleep(0.25)
                except Exception:
                    break

    def stop_music(self):
        with self.music_lock:
            media_pid = self.music_process
            temp_file = self.music_temp_file

            self.music_process = None
            self.music_temp_file = None

        if media_pid or temp_file:
            self.music_stopped_by_zanel = True

        if media_pid:
            try:
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(media_pid),
                        "/F",
                    ],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

        if temp_file:
            for _ in range(60):
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    break
                except PermissionError:
                    time.sleep(0.25)
                except Exception:
                    break

        return "Music stopped."

    def find_media_player_process(self):
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "Get-Process | "
                        "Where-Object {"
                        "$_.ProcessName -eq 'Microsoft.Media.Player' "
                        "-or $_.ProcessName -eq 'Microsoft.ZuneMusic' "
                        "-or $_.ProcessName -eq 'MediaPlayer'"
                        "} | "
                        "Select-Object Id,ProcessName,MainWindowTitle | "
                        "ConvertTo-Json -Compress"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                return None

            output = result.stdout.strip()

            if not output:
                return None

            data = json.loads(output)

            if isinstance(data, dict):
                data = [data]

            preferred = []

            for item in data:
                pid = item.get("Id")
                name = str(
                    item.get(
                        "ProcessName",
                        "",
                    )
                ).lower()

                title = str(
                    item.get(
                        "MainWindowTitle",
                        "",
                    )
                ).lower()

                if not pid:
                    continue

                if (
                    "media" in name
                    or "zune" in name
                    or "media" in title
                ):
                    preferred.append(
                        int(pid)
                    )

            if preferred:
                return preferred[0]

        except Exception:
            pass

        return None

    def play_music(self, song_name, root):
        song_key = str(song_name).lower().strip()
        song_key = song_key.replace("_", "-").replace(" ", "-")

        url = MUSIC_URLS.get(song_key)

        if not url:
            return (
                "Unknown music. Available music: "
                "chill-bossa-nova, lo-fi, soft-techno, dance."
            )

        if not ask_local_confirmation(
            root,
            "Zanel wants to play music",
            f"Allow Zanel to play:\n\n{song_name}?",
        ):
            return "User declined playing music."

        self.stop_music()

        temp_file = None

        try:
            MUSIC_TEMP_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            temp_file = (
                MUSIC_TEMP_DIR
                / f"{song_key}_{uuid.uuid4().hex}.mp3"
            )

            urllib.request.urlretrieve(
                url,
                str(temp_file),
            )

            if not temp_file.exists():
                return "Zanel could not create the temporary music file."

            self.music_stopped_by_zanel = False

            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-WindowStyle",
                    "Hidden",
                    "-Command",
                    f"Start-Process '{str(temp_file)}'",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            media_pid = None

            for _ in range(30):
                time.sleep(1)

                media_pid = self.find_media_player_process()

                if media_pid:
                    break

            if not media_pid:
                return "Media Player opened but Zanel could not detect it."

            with self.music_lock:
                self.music_temp_file = str(temp_file)
                self.music_process = media_pid

            def monitor_player():

                while self.running:

                    try:
                        result = subprocess.run(
                            [
                                "tasklist",
                                "/FI",
                                f"PID eq {media_pid}",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )

                        if str(media_pid) not in result.stdout:
                            break

                    except Exception:
                        break

                    time.sleep(2)

                if (
                    not self.music_stopped_by_zanel
                    and time.time() - self.last_feedback_time > 5
                ):
                    self.last_action_feedback = (
                        "Action: play_music\n"
                        "Result: Music stopped playing."
                    )

                    self.last_feedback_time = time.time()

                with self.music_lock:
                    self.music_process = None
                    self.music_temp_file = None

                for _ in range(60):
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        break

                    except PermissionError:
                        time.sleep(0.25)

                    except Exception:
                        break

            self.music_cleanup_thread = threading.Thread(
                target=monitor_player,
                daemon=True,
            )

            self.music_cleanup_thread.start()

            return f"Playing {song_name}."

        except Exception as exc:
            if temp_file:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass

            return f"Could not play music: {exc}"

    def ai_set_mic(self, muted):
        muted = bool(muted)
        self.saved_mic_muted = muted
        self.persist_settings()

        if self.settings_frame is not None:
            self.settings_mic_was_muted = muted
            return

        self.set_mic(muted)

    def set_silent_mode(self, enabled):
        self.silent_mode = bool(enabled)

        self.persist_settings()

        if self.silent_mode:
            return "Zanel silent mode enabled."

        return "Zanel silent mode disabled."

    def load_audio_systems(self):
        if not self.running:
            return

        self.messages.put(
            (
                "state",
                "Mic Muted"
                if self.mic_muted
                else "Listening",
            )
        )

        if self.running:
            threading.Thread(
                target=self._listen_loop,
                daemon=True,
            ).start()

    def toggle_mic(self):
        if self.tts_busy:
            return

        self.saved_mic_muted = not self.mic_muted
        self.persist_settings()
        self.set_mic(not self.mic_muted)

    def set_mic(self, muted):
        self.mic_muted = bool(muted)

        def update():
            try:
                if not self.mic_button.winfo_exists():
                    return

                if self.tts_busy:
                    self.mic_button.configure(
                        text="●  Mic MUTED",
                        bg="#3a2028",
                        state="disabled",
                    )

                    self.state.configure(
                        text="Zanel is speaking…"
                    )

                else:
                    self.mic_button.configure(
                        text=(
                            "●  Mic MUTED"
                            if self.mic_muted
                            else "●  Mic ON"
                        ),
                        bg=(
                            "#3a2028"
                            if self.mic_muted
                            else self.theme["mic"]
                        ),
                        state="normal",
                    )

                    self.state.configure(
                        text=(
                            "Mic muted"
                            if self.mic_muted
                            else "Listening"
                        )
                    )

            except tk.TclError:
                pass

        if self.running:
            try:
                self.root.after(0, update)
            except tk.TclError:
                pass

    def _listen_loop(self):
        while self.running:
            if (
                self.mic_muted
                or self.ai_busy
                or self.tts_busy
            ):
                time.sleep(0.1)
                continue

            try:
                audio = self._record_utterance()

                if (
                    self.mic_muted
                    or self.ai_busy
                    or self.tts_busy
                ):
                    continue

                if (
                    audio is None
                    or len(audio) < int(SAMPLE_RATE * 0.25)
                ):
                    continue

                self.messages.put(
                    ("state", "Transcribing…")
                )

                text = self._transcribe(audio)

                if (
                    text
                    and not self.mic_muted
                    and not self.tts_busy
                ):
                    self.send_to_ai(text)

                if self.running and not self.busy_chats and not self.tts_busy:
                    self.messages.put(
                        (
                            "state",
                            "Mic Muted"
                            if self.mic_muted
                            else "Listening",
                        )
                    )

            except Exception as exc:
                if not self.running:
                    break

                self.messages.put(
                    (
                        "text",
                        "System",
                        f"Microphone error: {exc}",
                    )
                )

                if self.running:
                    self.messages.put(
                        (
                            "state",
                            "Mic Muted"
                            if self.mic_muted
                            else "Listening",
                        )
                    )

                time.sleep(1)

    def _get_microphone_settings(self):
        try:
            default_device = sd.default.device
        except Exception:
            default_device = None

        candidates = []

        if isinstance(
            default_device,
            (tuple, list)
        ):
            if len(default_device) > 0:
                candidates.append(
                    default_device[0]
                )
        elif isinstance(
            default_device,
            int
        ):
            candidates.append(
                default_device
            )

        try:
            devices = sd.query_devices()
        except Exception as exc:
            raise RuntimeError(
                f"Could not query audio devices: {exc}"
            ) from exc

        preferred = str(getattr(self, "mic_device", "") or "").strip()

        if preferred:
            try:
                default_api = sd.query_devices(kind="input").get("hostapi")
            except Exception:
                default_api = None

            matches = []

            for index, device in enumerate(devices):
                try:
                    if (
                        int(device.get("max_input_channels", 0)) > 0
                        and str(device.get("name", "")).strip() == preferred
                    ):
                        matches.append((index, device.get("hostapi")))
                except Exception:
                    continue

            matches.sort(key=lambda item: item[1] != default_api)

            for index, _api in reversed(matches):
                if index in candidates:
                    candidates.remove(index)

                candidates.insert(0, index)

        for index, device in enumerate(devices):
            try:
                if (
                    int(
                        device.get(
                            "max_input_channels",
                            0
                        )
                    ) > 0
                ):
                    if index not in candidates:
                        candidates.append(index)
            except Exception:
                continue

        for device_index in candidates:
            try:
                device_info = sd.query_devices(
                    device_index,
                    "input"
                )

                max_input_channels = int(
                    device_info.get(
                        "max_input_channels",
                        0
                    )
                )

                if max_input_channels < 1:
                    continue

                channels = min(
                    max(
                        1,
                        int(CHANNELS)
                    ),
                    max_input_channels
                )

                rates = []

                try:
                    default_rate = float(
                        device_info.get(
                            "default_samplerate",
                            0
                        )
                    )

                    if default_rate > 0:
                        rates.append(
                            default_rate
                        )
                except Exception:
                    pass

                for rate in (
                    SAMPLE_RATE,
                    48000,
                    44100,
                    32000,
                    24000,
                    22050,
                    16000
                ):
                    try:
                        rate = float(rate)

                        if (
                            rate > 0
                            and rate not in rates
                        ):
                            rates.append(rate)
                    except Exception:
                        continue

                for samplerate in rates:
                    try:
                        sd.check_input_settings(
                            device=device_index,
                            channels=channels,
                            dtype="float32",
                            samplerate=samplerate
                        )

                        return (
                            device_index,
                            channels,
                            samplerate
                        )
                    except Exception:
                        continue

            except Exception:
                continue

        raise RuntimeError(
            "No compatible microphone input device was found."
        )

    def _record_utterance(self):
        (
            device_index,
            stream_channels,
            samplerate
        ) = self._get_microphone_settings()

        blocksize = max(
            1,
            int(
                samplerate * BLOCK_SECONDS
            )
        )

        chunks = queue.Queue()
        pre_roll = deque(maxlen=PRE_ROLL_BLOCKS)
        recorded = []
        started = False
        speech_blocks = 0
        silence_blocks = 0
        listen_start = time.time()
        speech_start = 0.0

        def callback(
            indata,
            _frames,
            _time,
            status
        ):
            if (
                not self.running
                or self.mic_muted
            ):
                return

            if len(indata) == 0:
                return

            if indata.ndim == 1:
                chunks.put(
                    indata.copy()
                )
            else:
                chunks.put(
                    indata[:, 0].copy()
                )

        try:
            with sd.InputStream(
                device=device_index,
                samplerate=samplerate,
                channels=stream_channels,
                dtype="float32",
                blocksize=blocksize,
                callback=callback,
            ):
                while (
                    self.running
                    and not self.mic_muted
                ):
                    now = time.time()

                    if (
                        not started
                        and now - listen_start > MAX_IDLE_SECONDS
                    ):
                        return None

                    if (
                        started
                        and now - speech_start > MAX_RECORD_SECONDS
                    ):
                        break

                    try:
                        chunk = chunks.get(
                            timeout=0.1
                        )
                    except queue.Empty:
                        continue

                    rms = float(
                        np.sqrt(
                            np.mean(
                                np.square(chunk)
                            )
                        )
                    )

                    self.audio_level = min(
                        1.0,
                        rms * 12
                    )

                    is_speech = rms >= MIC_SENSITIVITY_LEVELS.get(
                        self.mic_sensitivity,
                        ENERGY_THRESHOLD,
                    )

                    if not started:
                        pre_roll.append(chunk)

                        if is_speech:
                            speech_blocks += 1
                        else:
                            speech_blocks = 0

                        if speech_blocks >= START_SPEECH_BLOCKS:
                            started = True
                            speech_start = now
                            silence_blocks = 0
                            recorded.extend(pre_roll)
                            pre_roll.clear()

                        continue

                    recorded.append(chunk)

                    if is_speech:
                        silence_blocks = 0
                    else:
                        silence_blocks += 1

                        if silence_blocks >= SILENCE_BLOCKS_TO_STOP:
                            break

        except Exception as exc:
            raise RuntimeError(
                f"Could not open microphone input: {exc}"
            ) from exc

        if (
            self.mic_muted
            or not started
            or not recorded
        ):
            return None

        audio = np.concatenate(
            recorded
        ).astype(
            np.float32,
            copy=False
        )

        peak = float(
            np.max(
                np.abs(audio)
            )
        )

        if peak > 0:
            gain = min(
                MAX_GAIN,
                TARGET_PEAK / peak
            )

            if gain > 1.0:
                audio = np.clip(
                    audio * gain,
                    -1.0,
                    1.0
                ).astype(
                    np.float32,
                    copy=False
                )

        if samplerate != SAMPLE_RATE:
            old_length = len(audio)

            new_length = int(
                old_length
                * SAMPLE_RATE
                / samplerate
            )

            if new_length > 0:
                old_positions = np.linspace(
                    0.0,
                    1.0,
                    old_length,
                    endpoint=False
                )

                new_positions = np.linspace(
                    0.0,
                    1.0,
                    new_length,
                    endpoint=False
                )

                audio = np.interp(
                    new_positions,
                    old_positions,
                    audio
                ).astype(
                    np.float32,
                    copy=False
                )

        return audio

    def skip_tts(self):
        if not self.tts_busy:
            return

        self.tts_skip = True

        try:
            winsound.PlaySound(
                None,
                winsound.SND_PURGE,
            )
        except Exception:
            pass

        self.messages.put(
            (
                "state",
                "Skipping speech…",
            )
        )

    def update_skip_button(self):
        try:
            if not self.running:
                return

            if self.tts_busy:
                if not self.skip_visible:
                    self.reset_skip_button_style()

                    self.skip_button.pack(
                        side="right",
                        padx=(8, 5),
                        pady=0,
                    )

                    self.skip_visible = True
                    self.start_skip_pulse()
            else:
                if self.skip_visible:
                    self.skip_button.pack_forget()
                    self.skip_visible = False
                    self.stop_skip_pulse()
                    self.reset_skip_button_style()

        except (tk.TclError, AttributeError):
            pass

    def reset_skip_button_style(self):
        self.skip_hover = False
        self.skip_phase = 0

        try:
            self.skip_button.configure(
                bg=self.skip_pulse_colors[0],
            )

            self.skip_inner.configure(
                bg=self.theme["skip"],
                fg=self.theme["accent"],
            )

        except (tk.TclError, AttributeError):
            pass

    def skip_hover_enter(self, _event=None):
        self.skip_hover = True

        try:
            self.skip_button.configure(
                bg=self.theme["accent"],
            )

            self.skip_inner.configure(
                bg=self.theme["accent"],
                fg="#071019",
            )

        except (tk.TclError, AttributeError):
            pass

    def skip_hover_leave(self, _event=None):
        self.skip_hover = False

        try:
            self.skip_button.configure(
                bg=self.skip_pulse_colors[self.skip_phase],
            )

            self.skip_inner.configure(
                bg=self.theme["skip"],
                fg=self.theme["accent"],
            )

        except (tk.TclError, AttributeError):
            pass

    def start_skip_pulse(self):
        self.stop_skip_pulse()

        try:
            self.skip_pulse_job = self.root.after(
                90,
                self.skip_pulse_tick,
            )
        except (tk.TclError, AttributeError):
            self.skip_pulse_job = None

    def stop_skip_pulse(self):
        job = getattr(
            self,
            "skip_pulse_job",
            None,
        )

        self.skip_pulse_job = None

        if job is not None:
            try:
                self.root.after_cancel(job)
            except (tk.TclError, AttributeError):
                pass

    def skip_pulse_tick(self):
        self.skip_pulse_job = None

        if not self.running or not self.skip_visible:
            return

        try:
            if not self.skip_hover:
                self.skip_phase = (
                    self.skip_phase + 1
                ) % len(self.skip_pulse_colors)

                self.skip_button.configure(
                    bg=self.skip_pulse_colors[self.skip_phase],
                )

            self.skip_pulse_job = self.root.after(
                90,
                self.skip_pulse_tick,
            )

        except (tk.TclError, AttributeError):
            self.skip_pulse_job = None

    def refresh_skip_button(self):
        try:
            self.root.after(
                0,
                self.update_skip_button,
            )
        except (tk.TclError, RuntimeError):
            pass

    def _speak(self, text, voice=None):
        if not text or not self.running:
            return

        if self.tts_busy:
            return

        text = self.clean_tts_text(
            text
        )

        if not text:
            return

        if not self.api_key:
            self.messages.put(
                (
                    "text",
                    "System",
                    "No API key available for speech.",
                )
            )
            return

        text = text[:15000]
        voice = voice or self.tts_voice

        with self.tts_lock:
            if self.tts_busy:
                return

            self.tts_busy = True
            self.tts_skip = False

        self.refresh_skip_button()

        mic_was_muted = self.mic_muted

        if not mic_was_muted:
            self.set_mic(True)

        self.messages.put(
            ("state", "Zanel is speaking…")
        )

        wav_path = None

        try:
            response = requests.post(
                TTS_URL,
                json={
                    "key": self.api_key,
                    "text": text,
                    "voice": voice,
                    "format": TTS_FORMAT,
                },
                timeout=430,
            )

            if not response.ok:
                if response.status_code in (401, 403):
                    self.handle_invalid_key()
                    return

                raise RuntimeError(
                    self._get_server_error(
                        response,
                        "TTS",
                    )
                )

            audio_bytes = response.content

            if not audio_bytes:
                raise RuntimeError(
                    "TTS server returned empty audio."
                )

            if self.tts_skip or not self.running:
                return

            fd, wav_path = tempfile.mkstemp(
                suffix=".wav"
            )
            os.close(fd)

            with open(
                wav_path,
                "wb",
            ) as audio_file:
                audio_file.write(
                    audio_bytes
                )

            duration = None

            try:
                import wave

                with wave.open(
                    wav_path,
                    "rb",
                ) as wav_file:
                    frame_rate = wav_file.getframerate()

                    if frame_rate > 0:
                        duration = (
                            wav_file.getnframes()
                            / float(frame_rate)
                        )
            except Exception:
                duration = None

            if self.tts_skip or not self.running:
                return

            if duration is None:
                winsound.PlaySound(
                    wav_path,
                    winsound.SND_FILENAME,
                )
            else:
                winsound.PlaySound(
                    wav_path,
                    winsound.SND_FILENAME
                    | winsound.SND_ASYNC,
                )

                end_time = (
                    time.time()
                    + duration
                    + 0.5
                )

                while (
                    self.running
                    and not self.tts_skip
                    and time.time() < end_time
                ):
                    time.sleep(0.05)

                try:
                    winsound.PlaySound(
                        None,
                        winsound.SND_PURGE,
                    )
                except Exception:
                    pass

        except requests.Timeout:
            self.messages.put(
                (
                    "text",
                    "System",
                    "TTS server timed out.",
                )
            )

        except requests.ConnectionError:
            self.messages.put(
                (
                    "text",
                    "System",
                    "TTS server is offline or unreachable.",
                )
            )

        except RuntimeError as exc:
            self.messages.put(
                (
                    "text",
                    "System",
                    str(exc),
                )
            )

        except Exception as exc:
            self.messages.put(
                (
                    "text",
                    "System",
                    f"TTS error: {exc}",
                )
            )

        finally:
            if wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

            self.tts_busy = False
            self.tts_skip = False

            self.refresh_skip_button()

            if not self.running:
                return

            self.set_mic(
                bool(self.saved_mic_muted)
                or self.settings_frame is not None
            )

            self.messages.put(
                (
                    "state",
                    "Mic Muted"
                    if self.mic_muted
                    else "Listening",
                )
            )
