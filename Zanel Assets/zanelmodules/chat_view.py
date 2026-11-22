import os
import queue
import threading
import time
import tkinter as tk
import math
import re
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageTk
import requests
from zanelmodules.config import (
    HISTORY_BATCH,
    HISTORY_INITIAL,
    HISTORY_PAGE,
    RECENT_IMAGE_LIMIT,
)
from zanelmodules.storage import make_entry


class ChatViewMixin:

    def clear_chat(self):
        now = time.time()
        elapsed = now - self.last_clear_time

        if elapsed < self.clear_cooldown:
            self.flash_state(
                f"Wait {math.ceil(self.clear_cooldown - elapsed)}s to clear"
            )
            return

        if self.chat_loading:
            self.flash_state("Chat is loading…")
            return

        self.last_clear_time = now
        self.load_token += 1
        self.deferred_entries = []
        self.history_entries = []
        self.history_start = 0
        self.loading_older = False
        self.reset_chat_view()
        self.flash_state("Chat cleared")

    def set_chat_visible(self, visible):
        holder = getattr(self, "chat_holder", self.chat)

        try:
            if visible:
                if not holder.winfo_manager():
                    holder.pack(
                        side="top",
                        fill="both",
                        expand=True,
                        padx=12,
                        pady=(12, 10),
                    )
            else:
                if holder.winfo_manager():
                    holder.pack_forget()
        except tk.TclError:
            pass

    def show_loading_label(self, visible):
        label = getattr(self, "loading_label", None)

        if label is None:
            return

        try:
            if visible:
                label.place(relx=0.5, rely=0.42, anchor="center")
                label.lift()
            else:
                label.place_forget()
        except tk.TclError:
            pass

    def show_chat_image(
        self,
        image_path,
    ):
        self.append_image("You", image_path)

    def apply_chat_font(self, size=None):
        if size is None:
            size = self.font_size

        try:
            follow = self._chat_is_at_bottom()
            size = int(size)
            self.chat.configure(font=("Segoe UI", size))
            self.chat.tag_configure(
                "bold",
                font=("Segoe UI", size, "bold"),
            )
            self.chat.tag_configure(
                "italic",
                font=("Segoe UI", size, "italic"),
            )
            self.root.update_idletasks()
            if follow:
                self.scroll_chat_to_bottom()
        except (tk.TclError, ValueError, TypeError):
            pass

    def cancel_chat_scroll(self):
        job = getattr(self, "chat_scroll_job", None)

        if job is not None:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass

        self.chat_scroll_job = None
        self.chat_scroll_target = None

    def _chat_is_at_bottom(self):
        try:
            return float(self.chat.yview()[1]) >= 0.985
        except (tk.TclError, TypeError, ValueError):
            return True

    def scroll_chat_to_bottom(self):
        self.cancel_chat_scroll()

        try:
            self.chat.see("end")
            self.on_chat_yscroll(*self.chat.yview())
        except tk.TclError:
            pass

    def scroll_chat(self, *args):
        self.cancel_chat_scroll()
        self.chat.yview(*args)

    def on_chat_mousewheel(self, event):
        try:
            steps = float(event.delta) / 120.0
            first, last = map(float, self.chat.yview())

            if not steps or last - first >= 0.999:
                return "break"

            target = self.chat_scroll_target

            if target is None or self.chat_scroll_job is None:
                target = first

            maximum = max(0.0, 1.0 - (last - first))
            distance = max(0.01, last - first) * 0.22
            self.chat_scroll_target = min(
                maximum,
                max(0.0, target - steps * distance),
            )

            if self.chat_scroll_job is None:
                self.chat_scroll_job = self.root.after(
                    16,
                    self.step_chat_scroll,
                )
        except (tk.TclError, TypeError, ValueError):
            return "break"

        return "break"

    def step_chat_scroll(self):
        self.chat_scroll_job = None

        try:
            first, last = map(float, self.chat.yview())
            target = self.chat_scroll_target

            if target is None:
                return

            maximum = max(0.0, 1.0 - (last - first))
            target = min(maximum, max(0.0, target))
            difference = target - first

            if abs(difference) < 0.001:
                self.chat.yview_moveto(target)
                self.chat_scroll_target = None
                return

            self.chat.yview_moveto(first + difference * 0.42)
            self.chat_scroll_job = self.root.after(
                16,
                self.step_chat_scroll,
            )
        except tk.TclError:
            self.chat_scroll_target = None

    def get_emoji_font(self, size=18):
        return None

    def is_emoji_character(self, char):
        if not char:
            return False

        code = ord(char)

        return (
            0x1F000 <= code <= 0x1FAFF
            or 0x2600 <= code <= 0x27BF
            or 0x2300 <= code <= 0x23FF
            or 0x2B00 <= code <= 0x2BFF
            or code in {
                0x00A9,
                0x00AE,
                0x203C,
                0x2049,
                0x2122,
                0x2139,
                0x3030,
                0x303D,
                0x3297,
                0x3299
            }
        )

    def split_emoji_text(self, text):
        parts = []
        i = 0
        length = len(text)

        while i < length:
            char = text[i]

            if not self.is_emoji_character(char):
                start = i

                while (
                    i < length
                    and not self.is_emoji_character(text[i])
                ):
                    i += 1

                if i > start:
                    parts.append(
                        (
                            "text",
                            text[start:i]
                        )
                    )

                continue

            sequence = [char]
            i += 1

            if (
                0x1F1E6 <= ord(char) <= 0x1F1FF
                and i < length
                and 0x1F1E6 <= ord(text[i]) <= 0x1F1FF
            ):
                sequence.append(
                    text[i]
                )
                i += 1

            while i < length:
                next_char = text[i]
                next_code = ord(next_char)

                if (
                    next_char == "\uFE0F"
                    or next_char == "\uFE0E"
                    or next_char == "\u200D"
                    or 0x1F3FB <= next_code <= 0x1F3FF
                ):
                    sequence.append(
                        next_char
                    )
                    i += 1
                    continue

                if (
                    next_code == 0x20E3
                    and sequence
                    and (
                        sequence[0].isdigit()
                        or sequence[0] in "#*"
                    )
                ):
                    sequence.append(
                        next_char
                    )
                    i += 1
                    continue

                if (
                    next_char == "\u20E3"
                ):
                    sequence.append(
                        next_char
                    )
                    i += 1
                    continue

                if (
                    next_char
                    and self.is_emoji_character(
                        next_char
                    )
                    and sequence
                    and sequence[-1] == "\u200D"
                ):
                    sequence.append(
                        next_char
                    )
                    i += 1
                    continue

                break

            parts.append(
                (
                    "emoji",
                    "".join(sequence)
                )
            )

        return parts

    def get_emoji_cache_dir(self):
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home())
            )
        )

        cache_dir = (
            base
            / "Zanel"
            / "emoji_cache"
        )

        try:
            cache_dir.mkdir(
                parents=True,
                exist_ok=True
            )
        except OSError:
            return None

        return cache_dir

    def get_emoji_codepoints(self, emoji):
        values = []

        for char in emoji:
            code = ord(char)

            if code in {
                0xFE0E,
                0xFE0F
            }:
                continue

            if code == 0x200D:
                values.append(
                    "200d"
                )
                continue

            values.append(
                format(
                    code,
                    "x"
                )
            )

        return "-".join(
            values
        )

    def get_emoji_image_url(self, emoji):
        codepoints = self.get_emoji_codepoints(
            emoji
        )

        if not codepoints:
            return None

        return (
            "https://cdn.jsdelivr.net/gh/"
            "jdecked/twemoji@latest/assets/72x72/"
            f"{codepoints}.png"
        )

    def begin_render(self, index):
        self.chat.configure(state="normal")
        self.chat.mark_set("render_pos", index)
        self.chat.mark_gravity("render_pos", "right")

    def end_render(self):
        try:
            self.chat.mark_unset("render_pos")
        except tk.TclError:
            pass

        self.chat.configure(state="disabled")

    def reset_chat_view(self):
        self.cancel_chat_scroll()
        older_job = getattr(self, "older_load_job", None)

        if older_job is not None:
            try:
                self.root.after_cancel(older_job)
            except tk.TclError:
                pass

        self.older_load_job = None
        self.loading_older = False
        self._emoji_network = True

        try:
            self.chat.configure(state="normal")
            self.chat.delete("1.0", "end")
        except tk.TclError:
            pass

        try:
            self.chat.mark_unset("older_anchor")
        except tk.TclError:
            pass

        try:
            self.chat.configure(state="disabled")
        except tk.TclError:
            pass

        self._chat_images.clear()
        try:
            self.chat_latest_button.place_forget()
            self.older_loading_label.place_forget()
        except (AttributeError, tk.TclError):
            pass

    def display_entry(self, entry):
        turn_id = entry.get("turn_id")

        if (
            turn_id in self.cancelled_turn_ids
            and turn_id not in getattr(self, "preserved_turn_ids", set())
        ):
            return

        if self.chat_loading:
            self.deferred_entries.append(entry)
            return

        follow = self._chat_is_at_bottom()

        try:
            self.begin_render("end-1c")
            self.render_entry(entry, None)
        except tk.TclError:
            pass
        finally:
            try:
                self.end_render()
            except tk.TclError:
                pass

        try:
            if follow:
                self.scroll_chat_to_bottom()
        except tk.TclError:
            pass

    def show_text(self, who, text):
        self.display_entry(make_entry(who, text))

    def handle_cancelled_turn(self, chat_id, turn_id, preserve=False):
        self.cancelled_turn_ids.add(turn_id)

        if preserve:
            self.preserved_turn_ids.add(turn_id)
            return

        try:
            self.chat_store.remove_turn(chat_id, turn_id)
        except OSError as exc:
            self.messages.put(
                (
                    "text",
                    "System",
                    f"Could not remove canceled messages from chat history: {exc}",
                )
            )

        if chat_id == self.active_chat_id:
            self.activate_chat(chat_id, force=True)

    def handle_chat_message(self, chat_id, entry):
        if entry.get("turn_id") in self.cancelled_turn_ids:
            return

        if entry["who"] != "System":
            self.chat_store.append(chat_id, entry)

        if chat_id == self.active_chat_id:
            self.display_entry(entry)

    def render_entry(self, entry, index=None):
        prefix = f"{entry.get('who', '')}: "

        if self.show_timestamps:
            try:
                stamp = datetime.fromtimestamp(
                    float(entry.get("time", 0))
                ).strftime("%H:%M")
                prefix = f"[{stamp}] {prefix}"
            except (TypeError, ValueError, OSError):
                pass

        self.chat.insert("render_pos", prefix)
        self.insert_rich(self.format_message(entry.get("text", "")))

        paste = entry.get("paste")
        pastes = entry.get("pastes") or []

        if paste and not pastes:
            pastes = [paste]

        for number, item in enumerate(pastes, start=1):
            self.chat.insert("render_pos", "\n")
            self.insert_paste_box(
                item,
                entry.get("who", ""),
                number if len(pastes) > 1 else None,
            )

        image = entry.get("image")

        if image:
            self.chat.insert("render_pos", "\n")

            recent = (
                index is None
                or index >= len(self.history_entries) - RECENT_IMAGE_LIMIT
            )

            if recent:
                self.insert_chat_thumbnail(image)
            else:
                self.chat.insert("render_pos", "[Image not shown]")

        self.chat.insert("render_pos", "\n\n")

    def insert_rich(self, text):
        pattern = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")
        position = 0

        for match in pattern.finditer(text):
            if match.start() > position:
                self.insert_segment(text[position:match.start()])

            if match.group(1) is not None:
                self.insert_segment(match.group(1), "bold")
            else:
                self.insert_segment(match.group(2), "italic")

            position = match.end()

        if position < len(text):
            self.insert_segment(text[position:])

    def insert_segment(self, value, tag=None):
        if not value:
            return

        for part_type, part in self.split_emoji_text(value):
            if part_type == "emoji":
                self.insert_emoji(part)
            elif tag:
                self.chat.insert("render_pos", part, tag)
            else:
                self.chat.insert("render_pos", part)

    def insert_paste_box(self, paste, who="", number=None):
        is_reply = who not in ("", "You")
        heading = "Long response" if is_reply else "Pasted message"
        hint = "click to read" if is_reply else "click to view"
        if number:
            heading = f"{heading} {number}"

        box = tk.Frame(
            self.chat,
            bg=self.theme["button"],
            highlightthickness=1,
            highlightbackground=self.theme["border"],
            cursor="hand2",
        )

        title = tk.Label(
            box,
            text=heading,
            fg=self.theme["accent"],
            bg=self.theme["button"],
            cursor="hand2",
            font=("Segoe UI", max(8, self.font_size - 1), "bold"),
        )
        title.pack(anchor="w", padx=10, pady=(6, 0))

        info = tk.Label(
            box,
            text=f"{len(paste):,} characters  ·  {hint}",
            fg="#8290A8",
            bg=self.theme["button"],
            cursor="hand2",
            font=("Segoe UI", 8),
        )
        info.pack(anchor="w", padx=10, pady=(0, 6))

        for widget in (box, title, info):
            widget.bind(
                "<Button-1>",
                lambda _event, value=paste, name=heading: self.open_paste_viewer(
                    value,
                    title=name,
                ),
            )

        self.chat.window_create("render_pos", window=box, padx=0, pady=2)

    def insert_chat_thumbnail(self, path, index="render_pos"):
        label = tk.Label(
            self.chat,
            text="Loading image…",
            fg="#8290A8",
            bg=self.theme["panel"],
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=6,
            font=("Segoe UI", 8),
        )

        try:
            self.chat.window_create(index, window=label, padx=0, pady=2)
        except tk.TclError:
            return

        token = self.load_token

        def load_image():
            image = None

            try:
                with Image.open(path) as source:
                    if source.width * source.height > 20_000_000:
                        raise ValueError("The chat image is too large to display.")

                    source.thumbnail(
                        (280, 200),
                        Image.Resampling.LANCZOS,
                    )
                    image = source.convert("RGB").copy()
            except Exception:
                image = None

            try:
                self.root.after(
                    0,
                    self.finish_chat_thumbnail,
                    label,
                    image,
                    token,
                )
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(
            target=load_image,
            daemon=True,
        ).start()

    def finish_chat_thumbnail(self, label, image, token):
        if token != self.load_token or not self.running:
            return

        try:
            if not label.winfo_exists():
                return

            if image is None:
                label.configure(
                    text="Image unavailable",
                    fg="#FF8793",
                )
                return

            photo = ImageTk.PhotoImage(image)
            label.configure(
                image=photo,
                text="",
                padx=0,
                pady=0,
            )
            label.image = photo
            self._chat_images.append((photo, label))
        except tk.TclError:
            pass

    def place_emoji_image(self, photo):
        self.chat.image_create(
            "render_pos",
            image=photo,
            align="center",
            padx=1,
        )

    def insert_emoji(self, emoji):
        try:
            emoji_size = 16
            cache_key = (emoji, emoji_size)
            cached = self._emoji_cache.get(cache_key)

            if cached is not None:
                self.place_emoji_image(cached)
                return

            if emoji in self._emoji_failed:
                self.chat.insert("render_pos", emoji)
                return

            if not self._emoji_network:
                self.chat.insert("render_pos", emoji)
                return

            token = self.load_token
            pending_key = (cache_key, token)
            self._emoji_load_id = getattr(self, "_emoji_load_id", 0) + 1
            start_mark = f"emoji_start_{token}_{self._emoji_load_id}"
            end_mark = f"emoji_end_{token}_{self._emoji_load_id}"
            self.chat.mark_set(start_mark, "render_pos")
            self.chat.mark_gravity(start_mark, "left")
            self.chat.insert("render_pos", emoji)
            self.chat.mark_set(end_mark, "render_pos")
            self.chat.mark_gravity(end_mark, "right")
            self._emoji_pending.setdefault(pending_key, []).append(
                (start_mark, end_mark)
            )

            if pending_key in self._emoji_loading:
                return

            self._emoji_loading.add(pending_key)
            base = Path(
                os.environ.get(
                    "LOCALAPPDATA",
                    str(Path.home()),
                )
            )
            cache_path = (
                base
                / "Zanel"
                / "emoji_cache"
                / (self.get_emoji_codepoints(emoji) + ".png")
            )
            threading.Thread(
                target=self.load_emoji_image,
                args=(emoji, cache_path, pending_key),
                daemon=True,
            ).start()

        except Exception:
            self._emoji_failed.add(emoji)

            try:
                self.chat.insert("render_pos", emoji)
            except tk.TclError:
                pass

    def load_emoji_image(self, emoji, cache_path, pending_key):
        image = None

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            if not cache_path.is_file():
                url = self.get_emoji_image_url(emoji)

                if not url:
                    raise ValueError("No emoji image URL was available.")

                response = requests.get(
                    url,
                    timeout=(3, 5),
                    headers={"User-Agent": "Zanel/1.0"},
                )
                response.raise_for_status()

                if "image" not in response.headers.get(
                    "Content-Type",
                    "",
                ).lower():
                    raise ValueError("The emoji response was not an image.")

                temporary_path = cache_path.with_name(
                    f"{cache_path.stem}.{threading.get_ident()}.tmp"
                )

                try:
                    temporary_path.write_bytes(response.content)
                    os.replace(temporary_path, cache_path)
                finally:
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError:
                        pass

            with Image.open(cache_path) as source:
                if source.width * source.height > 4_000_000:
                    raise ValueError("The emoji image was too large.")

                decoded = source.convert("RGBA")

                if decoded.width < 1 or decoded.height < 1:
                    raise ValueError("The emoji image was empty.")

                image = decoded.resize(
                    (16, 16),
                    Image.Resampling.LANCZOS,
                )
                image.load()
        except Exception:
            image = None

        try:
            self.root.after(
                0,
                self.finish_emoji_image,
                emoji,
                pending_key,
                image,
            )
        except (tk.TclError, RuntimeError):
            pass

    def finish_emoji_image(self, emoji, pending_key, image):
        self._emoji_loading.discard(pending_key)
        marks = self._emoji_pending.pop(pending_key, [])
        token = pending_key[1]

        if token != self.load_token or not self.running:
            return

        if image is None:
            self._emoji_failed.add(emoji)

            try:
                mark_names = self.chat.mark_names()

                for start_mark, end_mark in marks:
                    if start_mark in mark_names:
                        self.chat.mark_unset(start_mark)
                    if end_mark in mark_names:
                        self.chat.mark_unset(end_mark)
            except tk.TclError:
                pass

            return

        try:
            photo = ImageTk.PhotoImage(image)
            self._emoji_cache[pending_key[0]] = photo
            self._emoji_images.append(photo)
            self.chat.configure(state="normal")

            for start_mark, end_mark in marks:
                mark_names = self.chat.mark_names()

                if start_mark not in mark_names or end_mark not in mark_names:
                    continue

                self.chat.delete(start_mark, end_mark)
                self.chat.image_create(
                    start_mark,
                    image=photo,
                    align="center",
                    padx=1,
                )
                self.chat.mark_unset(start_mark, end_mark)

            self.chat.configure(state="disabled")
        except tk.TclError:
            try:
                self.chat.configure(state="disabled")
            except tk.TclError:
                pass

    def message_pump(self):
        while self.running:
            try:
                item = self.messages.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                if item[0] == "text":
                    self.root.after(0, self.show_text, item[1], item[2])

                elif item[0] == "chat_msg":
                    self.root.after(0, self.handle_chat_message, item[1], item[2])

                elif item[0] == "cancel_turn":
                    self.root.after(
                        0,
                        self.handle_cancelled_turn,
                        item[1],
                        item[2],
                        item[3] if len(item) > 3 else False,
                    )

                elif item[0] == "image":
                    self.root.after(0, self.append_image, item[1], item[2])

                elif item[0] == "state":
                    if time.time() < getattr(self, "screenshot_status_until", 0.0):
                        continue

                    self.root.after(
                        0,
                        lambda text=item[1]: self.state.configure(text=text),
                    )

                elif item[0] == "response_state":
                    self.root.after(
                        0,
                        self.set_response_button_state,
                        item[1],
                    )

            except tk.TclError:
                break

    def append_image(
        self,
        sender,
        image_path,
    ):
        if not image_path:
            return

        follow = self._chat_is_at_bottom()

        try:
            self.chat.configure(state="normal")
            self.chat.insert("end", f"{sender}:\n")
            self.insert_chat_thumbnail(image_path, "end")
            self.chat.insert("end", "\n\n")
            self.chat.configure(state="disabled")

            if follow:
                self.scroll_chat_to_bottom()
        except tk.TclError:
            self.chat.configure(state="disabled")

    def _read_history(self, token, chat_id):
        try:
            entries = self.chat_store.messages(chat_id)
        except Exception as exc:
            print(
                f"Could not load chat history: {exc}",
                flush=True,
            )

            try:
                self.root.after(0, self.fail_history_load, token)
            except (tk.TclError, RuntimeError):
                pass

            return

        try:
            self.root.after(0, self.start_history_render, token, entries)
        except (tk.TclError, RuntimeError):
            pass

    def fail_history_load(self, token):
        if token != self.load_token or not self.running:
            return

        self.chat_loading = False
        self._emoji_network = True
        self.history_entries = []
        self.history_start = 0
        self.set_chat_visible(True)
        self.show_loading_label(False)
        self.display_entry(
            make_entry("System", "Could not load this chat history.")
        )

        deferred = self.deferred_entries
        self.deferred_entries = []

        for entry in deferred:
            self.display_entry(entry)

        self.refresh_sidebar()

    def start_history_render(self, token, entries):
        if token != self.load_token or not self.running:
            return

        preserved_turn_ids = getattr(self, "preserved_turn_ids", set())
        entries = [
            entry
            for entry in entries
            if (
                entry.get("turn_id") not in self.cancelled_turn_ids
                or entry.get("turn_id") in preserved_turn_ids
            )
        ]
        self.history_entries = entries
        self.history_start = len(entries)

        start = max(0, len(entries) - HISTORY_INITIAL)
        self.load_initial(token, start, len(entries))

    def load_initial(self, token, position, end):
        if token != self.load_token or not self.running:
            return

        batch_end = min(end, position + HISTORY_BATCH)
        self._emoji_network = False

        try:
            self.begin_render("end-1c")

            for index in range(position, batch_end):
                try:
                    self.render_entry(self.history_entries[index], index)
                except Exception:
                    pass
        except tk.TclError:
            pass
        finally:
            try:
                self.end_render()
            except tk.TclError:
                pass

        try:
            self.chat.see("end")

            if batch_end < end:
                self.root.after(8, self.load_initial, token, batch_end, end)
                return
        except tk.TclError:
            return

        self.finish_load(token, end)

    def finish_load(self, token, end):
        if token != self.load_token:
            return

        self.history_start = max(0, end - HISTORY_INITIAL)
        self.chat_loading = False
        self._emoji_network = True
        self.set_chat_visible(True)
        self.root.update_idletasks()
        self.show_loading_label(False)

        deferred = self.deferred_entries
        self.deferred_entries = []

        for entry in deferred:
            self.display_entry(entry)

        try:
            self.chat.see("end")
        except tk.TclError:
            pass

        self.refresh_sidebar()

    def on_chat_yscroll(self, first, last):
        try:
            first_value = float(first)
            last_value = float(last)
            scrollbar = getattr(self, "chat_scrollbar", None)

            if scrollbar is not None:
                scrollbar.set(first_value, last_value)

            button = getattr(self, "chat_latest_button", None)
            viewport = max(0.01, last_value - first_value)
            far_from_bottom = (
                1.0 - last_value
            ) > viewport * 0.75

            if button is not None:
                if self.chat_loading or not far_from_bottom:
                    button.place_forget()
                else:
                    button.place(
                        relx=0.5,
                        rely=1.0,
                        y=-16,
                        anchor="s",
                    )
                    button.lift()

            if (
                not self.chat_loading
                and not self.loading_older
                and self.history_start > 0
                and first_value <= 0.02
            ):
                self.root.after_idle(self.load_older)
        except (tk.TclError, TypeError, ValueError):
            pass

    def load_older(self):
        if self.chat_loading or self.loading_older or self.history_start <= 0:
            return

        self.cancel_chat_scroll()
        self.loading_older = True
        self._emoji_network = False
        token = self.load_token
        old_start = self.history_start
        new_start = max(0, old_start - HISTORY_PAGE)

        try:
            self.older_loading_label.place(
                relx=0.5,
                y=10,
                anchor="n",
            )
            self.older_loading_label.lift()
        except (AttributeError, tk.TclError):
            pass

        try:
            self.chat.configure(state="normal")
            self.chat.mark_set("older_anchor", "1.0")
            self.chat.mark_gravity("older_anchor", "right")
            self.begin_render("1.0")
        except tk.TclError:
            self.finish_load_older(token, new_start, False)
            return

        self.load_older_batch(token, new_start, old_start, new_start)

    def load_older_batch(self, token, position, end, new_start):
        if token != self.load_token or not self.running:
            return

        self.older_load_job = None
        batch_end = min(end, position + HISTORY_BATCH)

        try:
            for index in range(position, batch_end):
                try:
                    self.render_entry(self.history_entries[index], index)
                except Exception:
                    pass
        except tk.TclError:
            self.finish_load_older(token, position, False)
            return

        if batch_end < end:
            try:
                self.older_load_job = self.root.after(
                    8,
                    self.load_older_batch,
                    token,
                    batch_end,
                    end,
                    new_start,
                )
                return
            except (tk.TclError, RuntimeError):
                self.finish_load_older(token, position, False)
                return

        self.finish_load_older(token, new_start, True)

    def finish_load_older(self, token, new_start, restore_anchor):
        if token != self.load_token:
            return

        self.older_load_job = None

        try:
            self.end_render()

            if restore_anchor:
                self.history_start = new_start
                self.chat.yview("older_anchor")
        except tk.TclError:
            pass
        finally:
            try:
                self.chat.mark_unset("older_anchor")
            except tk.TclError:
                pass

            try:
                self.chat.configure(state="disabled")
            except tk.TclError:
                pass

            self._emoji_network = True
            self.loading_older = False

            try:
                self.older_loading_label.place_forget()
                self.on_chat_yscroll(*self.chat.yview())
            except (AttributeError, tk.TclError):
                pass
