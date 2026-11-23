import json
import os
import threading
import time
import tkinter as tk
import math
import uuid
import numpy as np
import requests
from zanelmodules.actions import execute_action
from zanelmodules.config import (
    AI_URL,
    BOT_NAME,
    CHANNELS,
    INPUT_PLACEHOLDER,
    LONG_REPLY_CHARS,
    LONG_REPLY_LINES,
    LONG_REPLY_MAX_CHARS,
    MAX_ACTIONS_PER_MESSAGE,
    MAX_PASTES,
    MAX_SERVER_MESSAGE_CHARS,
    MESSAGES_CLEAR_URL,
    PASTE_MAX_CHARS,
    PREVIEW_CHARS,
    SAMPLE_RATE,
    TRANSCRIBE_URL,
)
from zanelmodules.prompts import MULTI_ACTION_RULE, SINGLE_ACTION_RULE, SYSTEM_PROMPT
from zanelmodules.storage import make_entry

PRE_SEND_DELAY = 3.0


class NetworkMixin:

    def _transcribe(self, audio):
        if self.mic_muted:
            return ""

        try:
            import io
            import wave

            audio_array = np.asarray(audio)

            if audio_array.size == 0:
                return ""

            audio_array = np.clip(
                audio_array,
                -1.0,
                1.0
            )

            audio_int16 = (
                audio_array * 32767
            ).astype(np.int16)

            wav_buffer = io.BytesIO()

            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(
                    audio_int16.tobytes()
                )

            wav_buffer.seek(0)

            response = requests.post(
                TRANSCRIBE_URL,
                files={
                    "audio": (
                        "zanel_audio.wav",
                        wav_buffer,
                        "audio/wav"
                    )
                },
                data={
                    "key": self.api_key
                },
                timeout=120
            )

            if not response.ok:
                if response.status_code in (401, 403):
                    self.handle_invalid_key()
                    return ""

                error_message = self._get_server_error(
                    response,
                    "Transcription",
                )

                raise RuntimeError(
                    error_message
                )

            data = response.json()

            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(
                    str(data["error"])
                )

            text = str(
                data.get("text") or ""
            ).strip()

            if self.mic_muted:
                return ""

            return text

        except requests.Timeout:
            self.messages.put(
                (
                    "text",
                    "System",
                    "Transcription server timed out.",
                )
            )
            return ""

        except requests.ConnectionError:
            self.messages.put(
                (
                    "text",
                    "System",
                    "Transcription server is offline or unreachable.",
                )
            )
            return ""

        except requests.RequestException:
            self.messages.put(
                (
                    "text",
                    "System",
                    "Transcription connection failed.",
                )
            )
            return ""

        except RuntimeError as exc:
            self.messages.put(
                (
                    "text",
                    "System",
                    str(exc),
                )
            )
            return ""

        except Exception as exc:
            self.messages.put(
                (
                    "text",
                    "System",
                    f"Transcription failed: {exc}",
                )
            )
            return ""

    def _get_server_error(self, response, label):
        if response is None:
            return f"{label} server did not respond."

        status = response.status_code
        detail = ""

        try:
            data = response.json()

            if isinstance(data, dict):
                detail = str(
                    data.get("error")
                    or data.get("message")
                    or data.get("detail")
                    or ""
                ).strip()
        except ValueError:
            detail = ""

        if status in (401, 403):
            base = f"{label} request was rejected. Check your API key."
        elif status == 429:
            base = f"{label} server is rate limiting you. Wait a moment."
        elif status >= 500:
            base = f"{label} server error (HTTP {status})."
        else:
            base = f"{label} request failed (HTTP {status})."

        if detail:
            return f"{base} {detail[:200]}"

        return base

    def _server_clear(self, item):
        key = self.api_key

        if not key:
            return False

        try:
            response = requests.post(
                MESSAGES_CLEAR_URL,
                json={
                    "key": key,
                    "platform": item["platform"],
                    "user_id": item["user_id"],
                },
                timeout=8,
            )
        except requests.RequestException:
            return False

        return response.status_code == 200

    def start_server_cleanup(self):
        with self.cleanup_lock:
            if self.cleanup_running:
                return

            self.cleanup_running = True

        threading.Thread(
            target=self._server_cleanup_worker,
            daemon=True,
        ).start()

    def _server_cleanup_worker(self):
        try:
            for _attempt in range(3):
                items = self.chat_store.pending_items()

                if not items:
                    break

                for item in items:
                    if self._server_clear(item):
                        self.chat_store.remove_pending(item)

                    time.sleep(0.3)

                if not self.chat_store.pending_items():
                    break

                time.sleep(12)
        finally:
            with self.cleanup_lock:
                self.cleanup_running = False

    def test_api_key(self, key):
        key = key.strip()

        if not key:
            return False, "Please enter an API key."

        try:
            response = requests.post(
                AI_URL,
                json={
                    "key": key,
                    "model": "normal",
                    "user_id": "Un--set404",
                    "platform": "Un--set404",
                    "message": "API key connection test.",
                    "bot_name": BOT_NAME,
                    "system_prompt": "Respond only with: OK",
                },
                timeout=15,
            )

            if response.ok:
                return True, "API key is working."

            return (
                False,
                f"API key rejected "
                f"(HTTP {response.status_code}).",
            )

        except requests.RequestException as exc:
            return (
                False,
                f"Could not connect to the AI server: {exc}",
            )

    def can_send_message(self):
        now = time.time()

        if self.ai_busy:
            self.flash_state("Wait for this chat's reply")
            return False

        if self.busy_chats:
            self.flash_state("Wait for the other chat's reply")
            return False

        remaining = self.message_cooldown - (now - self.last_message_time)

        if remaining > 0:
            self.flash_state(f"Wait {math.ceil(remaining)}s before sending")
            return False

        return True

    def set_response_button_state(self, state):
        button = getattr(self, "send_button", None)

        if button is None:
            return

        try:
            if state == "busy":
                button.configure(
                    text="Cancel",
                    command=self.cancel_response,
                    fg="#FFFFFF",
                    bg="#C43F52",
                    activeforeground="#FFFFFF",
                    activebackground="#E05265",
                    state="normal",
                )
            elif state == "cancelling":
                button.configure(
                    text="Stopping…",
                    fg="#FFFFFF",
                    bg="#68434A",
                    activeforeground="#FFFFFF",
                    activebackground="#68434A",
                    state="disabled",
                )
            else:
                button.configure(
                    text="Send",
                    command=self.send_manual,
                    fg="#071019",
                    bg="#5CFF9D",
                    activeforeground="#071019",
                    activebackground="#72FFAB",
                    state="normal",
                )
        except tk.TclError:
            pass

    def cancel_response(self):
        with self.response_lock:
            cancel_event = self.current_cancel_event

            if cancel_event is None or cancel_event.is_set():
                return

            cancel_event.set()
            chat_id = self.current_request_chat_id
            turn_id = self.current_turn_id
            preserve_turn = bool(
                getattr(self, "current_request_dispatched", False)
            )

            if turn_id:
                self.cancelled_turn_ids.add(turn_id)

                if preserve_turn:
                    preserved_turn_ids = getattr(
                        self,
                        "preserved_turn_ids",
                        None,
                    )

                    if preserved_turn_ids is not None:
                        preserved_turn_ids.add(turn_id)

        if self.tts_busy:
            self.skip_tts()

        if chat_id and turn_id:
            self.messages.put(
                ("cancel_turn", chat_id, turn_id, preserve_turn)
            )
        self.messages.put(("response_state", "cancelling"))
        self.messages.put(("state", "Cancelling…"))

    def _finish_ai_request(self, chat_id, cancel_event):
        with self.response_lock:
            if self.current_cancel_event is not cancel_event:
                return

            self.current_cancel_event = None
            self.busy_chats.discard(chat_id)
            self.current_request_chat_id = None
            self.current_turn_id = None
            self.current_request_dispatched = False

        self.refresh_sidebar_threadsafe()
        self.messages.put(("response_state", "idle"))

        if self.running and not self.tts_busy:
            self.messages.put(
                ("state", "Mic Muted" if self.mic_muted else "Listening")
            )

    def send_manual(self):
        try:
            text = self.manual.get().strip()
        except tk.TclError:
            return

        if text == INPUT_PLACEHOLDER:
            text = ""

        image_path = getattr(self, "attached_image_path", None)
        pastes = list(self.pending_pastes)

        if not text and not image_path and not pastes:
            return

        if self.chat_loading:
            self.flash_state("Chat is loading…")
            return

        if pastes:
            used = len(text) + sum(len(item) for item in pastes) + 2 * len(pastes)

            if len(pastes) > 1:
                used += sum(
                    len(f"[Pasted message {number}]\n")
                    for number in range(1, len(pastes) + 1)
                )

            if used > MAX_SERVER_MESSAGE_CHARS:
                self.flash_state(
                    f"Too much text to send (max {MAX_SERVER_MESSAGE_CHARS:,} characters)"
                )
                return

        if not self.can_send_message():
            return

        if not self.send_to_ai(text, image_path, pastes):
            return

        self.manual.delete(0, "end")
        self.clear_pending_paste()

    def send_to_ai(self, text, image_path=None, pastes=None):
        if (
            (not text and not image_path and not pastes)
            or self.chat_loading
        ):
            return False

        chat_id = self.active_chat_id
        meta = self.chat_store.get_chat(chat_id) if chat_id else None

        if meta is None:
            self.messages.put(("text", "System", "No active chat."))
            return False

        rate_limited = 0
        with self.response_lock:
            if self.busy_chats or self.current_cancel_event is not None:
                return False

            now = time.time()
            remaining = self.message_cooldown - (now - self.last_message_time)

            if remaining > 0:
                rate_limited = remaining
            else:
                self.last_message_time = now
                cancel_event = threading.Event()
                self.current_cancel_event = cancel_event
                turn_id = uuid.uuid4().hex
                self.current_request_chat_id = chat_id
                self.current_turn_id = turn_id
                self.current_request_dispatched = False
                self.busy_chats.add(chat_id)

        if rate_limited:
            self.flash_state(f"Wait {math.ceil(rate_limited)}s before sending")
            return False

        text = (text or "")[:MAX_SERVER_MESSAGE_CHARS]
        candidates = [
            item
            for item in (pastes or [])
            if isinstance(item, str) and item.strip()
        ][:MAX_PASTES]

        multiple = len(candidates) > 1
        sent_pastes = []
        parts = [text] if text else []
        room = MAX_SERVER_MESSAGE_CHARS - len(text)

        for number, item in enumerate(candidates, start=1):
            header = f"[Pasted message {number}]\n" if multiple else ""
            available = min(room - len(header) - 2, PASTE_MAX_CHARS)

            if available < 20:
                break

            chunk = item[:available]
            sent_pastes.append(chunk)
            parts.append(header + chunk)
            room -= len(header) + len(chunk) + 2

        server_text = "\n\n".join(parts)

        naming_text = None

        if not meta.get("named"):
            naming_text = (
                text
                or (sent_pastes[0][:300] if sent_pastes else "")
                or "Screenshot"
            )

        self.refresh_sidebar_threadsafe()
        if image_path:
            self.messages.put(("state", "Preparing image…"))

        self.messages.put(("response_state", "busy"))
        send_after = time.monotonic() + PRE_SEND_DELAY

        threading.Thread(
            target=self._prepare_and_send,
            args=(
                chat_id,
                text,
                image_path,
                sent_pastes,
                server_text,
                naming_text,
                cancel_event,
                turn_id,
                send_after,
            ),
            daemon=True,
        ).start()

        return True

    def _prepare_and_send(
        self,
        chat_id,
        text,
        image_path,
        sent_pastes,
        server_text,
        naming_text,
        cancel_event,
        turn_id,
        send_after=None,
    ):
        thumbnail = (
            self.chat_store.save_thumbnail(chat_id, image_path)
            if image_path and not cancel_event.is_set()
            else None
        )
        if not cancel_event.is_set():
            self.post_chat(
                chat_id,
                "You",
                text,
                None,
                thumbnail,
                sent_pastes,
                turn_id=turn_id,
            )
        if send_after is not None:
            last_countdown = None

            while not cancel_event.is_set():
                now = time.monotonic()
                remaining = send_after - now
                countdown = max(0, math.ceil(remaining))

                if countdown != last_countdown:
                    unit = "second" if countdown == 1 else "seconds"
                    self.messages.put(
                        (
                            "state",
                            f"Sending in {countdown} {unit}…",
                        )
                    )
                    last_countdown = countdown

                if remaining <= 0:
                    break

                next_boundary = send_after - max(0, countdown - 1)
                wait_time = min(
                    remaining,
                    max(0.001, next_boundary - now),
                )

                if cancel_event.wait(wait_time):
                    break

        if not cancel_event.is_set():
            self.messages.put(("state", "Zanel is thinking…"))

        self.ai_thread(
            chat_id,
            server_text,
            image_path,
            naming_text,
            cancel_event,
            turn_id,
        )

    def post_chat(
        self,
        chat_id,
        who,
        text,
        paste=None,
        image=None,
        pastes=None,
        turn_id=None,
    ):
        if turn_id in self.cancelled_turn_ids:
            return

        self.messages.put(
            (
                "chat_msg",
                chat_id,
                make_entry(who, text, paste, image, pastes, turn_id),
            )
        )

    def build_system_prompt(self):
        prompt = SYSTEM_PROMPT.replace(
            "This session's Feedback ID is:",
            f"This session's Feedback ID is: {self.feedback_id}",
        )

        if self.multi_actions:
            rule = MULTI_ACTION_RULE
        else:
            rule = SINGLE_ACTION_RULE

        return prompt + "\n\n" + rule

    def _mark_server_request_dispatched(self, cancel_event):
        with self.response_lock:
            if (
                self.current_cancel_event is not cancel_event
                or cancel_event.is_set()
                or self.current_request_dispatched
            ):
                return False

            self.current_request_dispatched = True
            return True

    def ai_thread(
        self,
        chat_id,
        text,
        image_path=None,
        naming_text=None,
        cancel_event=None,
        turn_id=None,
    ):
        cancel_event = cancel_event or threading.Event()

        if cancel_event.is_set():
            if image_path:
                try:
                    self.root.after(0, self.reset_screenshot_button)
                except tk.TclError:
                    pass

            self._finish_ai_request(chat_id, cancel_event)
            return

        self.messages.put(("state", "Zanel is thinking…"))

        meta = self.chat_store.get_chat(chat_id)
        key = self.api_key

        if not key or meta is None:
            self.messages.put(
                (
                    "text",
                    "System",
                    "API key missing." if not key else "This chat no longer exists.",
                )
            )
            self._finish_ai_request(chat_id, cancel_event)
            return

        feedback = self.last_action_feedback[:2000]
        self.last_action_feedback = ""

        message_text = text or "Please analyze this screenshot."

        payload = {
            "key": key,
            "model": "vision" if image_path else "normal",
            "user_id": meta["user_id"],
            "platform": meta["platform"],
            "message": message_text,
            "bot_name": BOT_NAME,
            "system_prompt": self.build_system_prompt(),
            "web_search": (
                False
                if image_path
                else bool(getattr(self, "web_search", True))
            ),
        }

        if feedback:
            payload["message"] = (
                f"{message_text}\n\n"
                f"[ACTION RESULT FROM PREVIOUS REQUEST]\n"
                f"Feedback-ID: {self.feedback_id}\n"
                f"{feedback}\n"
                f"[END ACTION RESULT]"
            )

        response = None

        try:
            if cancel_event.is_set():
                return

            if image_path:
                if not os.path.isfile(image_path):
                    raise FileNotFoundError(
                        "The attached screenshot could not be found."
                    )

                extension = os.path.splitext(image_path)[1].lower()

                mimetype = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                }.get(extension)

                if not mimetype:
                    raise ValueError("Unsupported screenshot format.")

                with open(image_path, "rb") as image_file:
                    image_bytes = image_file.read()

                if not image_bytes:
                    raise ValueError("The attached screenshot is empty.")

                if len(image_bytes) > 5 * 1024 * 1024:
                    raise ValueError(
                        "The attached screenshot is larger than 5 MB."
                    )

                if cancel_event.is_set():
                    return

                if not self._mark_server_request_dispatched(cancel_event):
                    return

                response = requests.post(
                    AI_URL,
                    data={**payload, "model": "vision"},
                    files={
                        "image": (
                            os.path.basename(image_path),
                            image_bytes,
                            mimetype,
                        )
                    },
                    timeout=140,
                )

            else:
                if cancel_event.is_set():
                    return

                if not self._mark_server_request_dispatched(cancel_event):
                    return

                response = requests.post(
                    AI_URL,
                    json={**payload, "model": "normal"},
                    timeout=140,
                )

            if cancel_event.is_set():
                return

            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError:
                raise ValueError("AI server returned invalid JSON.")

            if not isinstance(data, dict):
                raise ValueError("AI server returned an invalid response.")

            if data.get("error"):
                raise ValueError(str(data["error"]))

            reply = str(data.get("response", "No response generated"))
            reply = self._clean_leaked_feedback(reply)
            if cancel_event.is_set():
                return

            if self.multi_actions:
                actions = self._extract_actions(
                    reply,
                    MAX_ACTIONS_PER_MESSAGE,
                )
            else:
                single_action = self._extract_action(reply)
                actions = (
                    [single_action]
                    if isinstance(single_action, dict) and single_action
                    else []
                )
            spoken = self._remove_action_block(reply).strip()
            spoken = self._fix_literal_newlines(spoken)

            tts_text = spoken

            if spoken:
                if cancel_event.is_set():
                    return

                code_start = spoken.find("```")

                if code_start != -1:
                    visible = spoken[:code_start].strip()

                    if len(visible) > PREVIEW_CHARS:
                        visible = self.make_preview(visible)

                    tts_text = visible or "I put the code in a long response."

                    self.post_chat(
                        chat_id,
                        BOT_NAME,
                        visible,
                        spoken[code_start:LONG_REPLY_MAX_CHARS + code_start],
                        turn_id=turn_id,
                    )
                elif (
                    len(spoken) > LONG_REPLY_CHARS
                    or spoken.count("\n") >= LONG_REPLY_LINES
                ):
                    tts_text = self.make_preview(spoken)

                    self.post_chat(
                        chat_id,
                        BOT_NAME,
                        tts_text,
                        spoken[:LONG_REPLY_MAX_CHARS],
                        turn_id=turn_id,
                    )
                else:
                    self.post_chat(
                        chat_id,
                        BOT_NAME,
                        spoken,
                        turn_id=turn_id,
                    )

            if naming_text and not cancel_event.is_set():
                self.name_chat_async(chat_id, naming_text, cancel_event)

            feedback_parts = []

            for number, action in enumerate(actions, start=1):
                if not self.running or cancel_event.is_set():
                    break

                result = execute_action(
                    action,
                    self.root,
                    self.ai_set_mic,
                    app=self,
                    cancel_event=cancel_event,
                )

                if cancel_event.is_set():
                    break

                action_name = action.get("action", "unknown")

                if len(actions) == 1:
                    feedback_parts.append(
                        f"Action: {action_name}\n"
                        f"Result: {result}"
                    )
                else:
                    feedback_parts.append(
                        f"Action {number}: {action_name}\n"
                        f"Result: {result}"
                    )

                if result and result != "No local action requested.":
                    self.post_chat(
                        chat_id,
                        "Zanel action",
                        result,
                        turn_id=turn_id,
                    )

                if str(result).startswith("CLOSE_ZANEL_SUCCESS"):
                    break

                if cancel_event.is_set():
                    break

            if feedback_parts and not cancel_event.is_set():
                self.last_action_feedback = "\n\n".join(feedback_parts)
                self.last_feedback_time = time.time()

            if (
                tts_text
                and self.running
                and not cancel_event.is_set()
                and not self.silent_mode
                and chat_id == self.active_chat_id
            ):
                self._speak(tts_text)

        except requests.HTTPError:
            if cancel_event.is_set():
                return

            if response is not None and response.status_code in (401, 403):
                self.handle_invalid_key()
            else:
                self.messages.put(
                    ("text", "System", self._get_server_error(response, "AI"))
                )

        except requests.Timeout:
            if cancel_event.is_set():
                return

            self.messages.put(("text", "System", "AI server timed out."))

        except requests.ConnectionError:
            if cancel_event.is_set():
                return

            self.messages.put(
                ("text", "System", "AI server is offline or unreachable.")
            )

        except requests.RequestException as exc:
            if cancel_event.is_set():
                return

            self.messages.put(
                (
                    "text",
                    "System",
                    str(exc).strip() or "AI connection failed.",
                )
            )

        except (FileNotFoundError, ValueError) as exc:
            if cancel_event.is_set():
                return

            if isinstance(exc, ValueError) and self._is_invalid_key_message(exc):
                self.handle_invalid_key()
            else:
                self.messages.put(("text", "System", str(exc)))

        except Exception as exc:
            if cancel_event.is_set():
                return

            self.messages.put(
                (
                    "text",
                    "System",
                    str(exc).strip() or "An unexpected AI error occurred.",
                )
            )

        finally:
            with self.response_lock:
                request_dispatched = (
                    self.current_cancel_event is cancel_event
                    and self.current_request_dispatched
                )

            if request_dispatched:
                self.chat_store.mark_server_used(chat_id)

            if (
                image_path
                and self.current_cancel_event is cancel_event
            ):
                try:
                    self.root.after(0, self.reset_screenshot_button)
                except tk.TclError:
                    pass

            self._finish_ai_request(chat_id, cancel_event)

    def name_chat_async(self, chat_id, source_text, cancel_event=None):
        threading.Thread(
            target=self._name_chat_worker,
            args=(chat_id, source_text, cancel_event),
            daemon=True,
        ).start()

    def _name_chat_worker(self, chat_id, source_text, cancel_event=None):
        with self.name_lock:
            if cancel_event is not None and cancel_event.is_set():
                return

            meta = self.chat_store.get_chat(chat_id)

            if meta is None or meta.get("named") or meta.get("anonymous"):
                return

            name = self.request_chat_name(source_text) or self.fallback_chat_name(
                source_text
            )

            if cancel_event is not None and cancel_event.is_set():
                return

            meta = self.chat_store.get_chat(chat_id)

            if meta is None or meta.get("named"):
                return

            if self.chat_store.rename(chat_id, name, True):
                self.refresh_sidebar_threadsafe()

    def request_chat_name(self, source_text):
        snippet = " ".join(str(source_text).split())[:400]

        if not snippet or not self.api_key:
            return ""

        payload = {
            "key": self.api_key,
            "model": "small",
            "user_id": "Un--set404",
            "platform": "Un--set404",
            "message": (
                "Write a title of at most 5 words for a chat that starts with "
                "this message. Reply with only the title.\n\n"
                f"Message: {snippet}"
            ),
            "bot_name": BOT_NAME,
            "system_prompt": (
                "You write very short chat titles. Reply with only the title, "
                "2 to 5 words, no quotes, no punctuation at the end."
            ),
        }

        for attempt in range(2):
            try:
                response = requests.post(AI_URL, json=payload, timeout=60)
            except requests.RequestException:
                return ""

            if response.status_code == 429 and attempt == 0:
                time.sleep(3.3)
                continue

            if not response.ok:
                return ""

            try:
                data = response.json()
            except ValueError:
                return ""

            if not isinstance(data, dict) or data.get("error"):
                return ""

            return self.clean_chat_name(str(data.get("response") or ""))

        return ""
