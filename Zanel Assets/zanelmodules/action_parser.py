import json
import re
import unicodedata
from zanelmodules.config import DEFAULT_CHAT_NAME, PREVIEW_CHARS


class ParserMixin:

    def format_message(
        self,
        text,
    ):
        if not text:
            return ""

        text = str(text)

        lines = text.splitlines()
        formatted_lines = []

        for line in lines:
            stripped = line.lstrip()

            if stripped.startswith("* "):
                stripped = "• " + stripped[2:]

            formatted_lines.append(
                stripped
            )

        return "\n".join(
            formatted_lines
        )

    def clean_tts_text(
        self,
        text,
    ):
        if text is None:
            return ""

        try:
            text = str(text)
        except Exception:
            return ""

        if not text:
            return ""

        try:
            text = unicodedata.normalize(
                "NFKD",
                text
            )
        except Exception:
            pass

        text = re.sub(
            r"```[\s\S]*?```",
            " ",
            text
        )

        text = re.sub(
            r"`([^`]*)`",
            r"\1",
            text
        )

        text = re.sub(
            r"\*\*([\s\S]*?)\*\*",
            r"\1",
            text
        )

        text = re.sub(
            r"__([\s\S]*?)__",
            r"\1",
            text
        )

        text = re.sub(
            r"(?<!\w)\*([\s\S]*?)\*(?!\w)",
            r"\1",
            text
        )

        text = re.sub(
            r"(?<!\w)_([\s\S]*?)_(?!\w)",
            r"\1",
            text
        )

        text = re.sub(
            r"(?m)^[ \t]*(?:[-*+•‣▪◦∙●○◾◽◆◇])"
            r"[ \t]+",
            "",
            text
        )

        text = re.sub(
            r"(?m)^[ \t]*\d+[.)][ \t]+",
            "",
            text
        )

        text = re.sub(
            r"(?m)^[ \t]*#{1,6}[ \t]*",
            "",
            text
        )

        text = re.sub(
            r"(?m)^[ \t]*>[ \t]*",
            "",
            text
        )

        text = re.sub(
            r"https?://\S+",
            " ",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"www\.\S+",
            " ",
            text,
            flags=re.IGNORECASE
        )

        text = text.replace(
            "\u2018",
            "'"
        )

        text = text.replace(
            "\u2019",
            "'"
        )

        text = text.replace(
            "\u201A",
            "'"
        )

        text = text.replace(
            "\u201B",
            "'"
        )

        text = text.replace(
            "\u2032",
            "'"
        )

        text = text.replace(
            "\u2035",
            "'"
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        ascii_text = []

        for char in text:
            try:
                if char.isascii():
                    ascii_text.append(
                        char
                    )
                    continue

                decomposed = unicodedata.normalize(
                    "NFKD",
                    char
                )

                for decomposed_char in decomposed:
                    if decomposed_char.isascii():
                        ascii_text.append(
                            decomposed_char
                        )

            except Exception:
                continue

        text = "".join(
            ascii_text
        )

        text = re.sub(
            r"[^A-Za-z0-9'\s]",
            " ",
            text
        )

        text = re.sub(
            r"(?<![A-Za-z0-9])'+",
            " ",
            text
        )

        text = re.sub(
            r"'+(?![A-Za-z0-9])",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        text = text.strip(
            " '"
        )

        return text

    @staticmethod
    def make_preview(text, limit=PREVIEW_CHARS):
        text = " ".join(str(text or "").split())

        if len(text) <= limit:
            return text

        cut = text.rfind(" ", 0, limit)

        if cut < limit // 2:
            cut = limit

        return text[:cut].rstrip() + "…"

    @staticmethod
    def clean_chat_name(raw):
        raw = re.sub(r"<think>[\s\S]*?</think>", "", str(raw or ""))
        lines = [line.strip() for line in raw.splitlines() if line.strip()]

        if not lines:
            return ""

        text = re.sub(r"(?i)^title\s*:\s*", "", lines[0])
        text = text.strip(" \t\"'`*#_")
        text = re.sub(r"[.!?:;,\-]+$", "", text).strip()
        text = " ".join(text.split())

        if not text or len(text.split()) > 8:
            return ""

        return text[:32].rstrip()

    @staticmethod
    def fallback_chat_name(source_text):
        words = re.findall(r"\S+", str(source_text or ""))[:5]
        name = " ".join(words)[:32].strip()

        return name or DEFAULT_CHAT_NAME

    @staticmethod
    def _repair_json_strings(text):
        if not text or not isinstance(text, str):
            return text

        result = []
        in_string = False
        escaped = False

        for char in text:
            if escaped:
                result.append(char)
                escaped = False
                continue

            if char == "\\":
                result.append(char)
                escaped = True
                continue

            if char == '"':
                result.append(char)
                in_string = not in_string
                continue

            if in_string:
                if char == "\n":
                    result.append("\\n")
                    continue

                if char == "\r":
                    result.append("\\r")
                    continue

                if char == "\t":
                    result.append("\\t")
                    continue

                if ord(char) < 32:
                    result.append(
                        "\\u{:04x}".format(ord(char))
                    )
                    continue

            result.append(char)

        return "".join(result)

    @staticmethod
    def shorten(text, limit):
        text = str(text)

        if len(text) <= limit:
            return text

        return text[: limit - 1] + "…"

    @staticmethod
    def _remove_trailing_json_commas(text):
        if not text or not isinstance(text, str):
            return text

        result = []
        in_string = False
        escaped = False
        index = 0

        while index < len(text):
            char = text[index]

            if escaped:
                result.append(char)
                escaped = False
                index += 1
                continue

            if char == "\\":
                result.append(char)
                escaped = True
                index += 1
                continue

            if char == '"':
                result.append(char)
                in_string = not in_string
                index += 1
                continue

            if not in_string and char == ",":
                lookahead = index + 1

                while (
                    lookahead < len(text)
                    and text[lookahead].isspace()
                ):
                    lookahead += 1

                if (
                    lookahead < len(text)
                    and text[lookahead] in "}]"
                ):
                    index += 1
                    continue

            result.append(char)
            index += 1

        return "".join(result)

    @staticmethod
    def _extract_json_objects(text):
        if not text or not isinstance(text, str):
            return []

        objects = []
        start = None
        depth = 0
        in_string = False
        escaped = False

        for index, char in enumerate(text):
            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                if depth == 0:
                    start = index

                depth += 1
                continue

            if char == "}":
                if depth <= 0:
                    continue

                depth -= 1

                if depth == 0 and start is not None:
                    candidate = text[start:index + 1].strip()

                    if candidate:
                        objects.append(candidate)

                    start = None

        return objects

    @staticmethod
    def _strip_code_fence(text):
        if not text or not isinstance(text, str):
            return text

        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            while lines and not lines[-1].strip():
                lines.pop()

            if lines and lines[-1].strip() == "```":
                lines.pop()

            cleaned = "\n".join(lines).strip()

        return cleaned

    @staticmethod
    def _strip_json_prefix(text):
        if not text or not isinstance(text, str):
            return text

        cleaned = text.strip()

        prefixes = (
            "json\n",
            "json\r\n",
            "json ",
            "JSON\n",
            "JSON\r\n",
            "JSON ",
        )

        for prefix in prefixes:
            if cleaned.startswith(prefix):
                return cleaned[len(prefix):].strip()

        return cleaned

    @staticmethod
    def _normalize_action_candidate(text):
        if not text or not isinstance(text, str):
            return ""

        cleaned = (
            text.replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
            .strip()
        )

        cleaned = ParserMixin._strip_code_fence(cleaned)
        cleaned = ParserMixin._strip_json_prefix(cleaned)

        return cleaned.strip()

    @staticmethod
    def _parse_action_json(text):
        if not text or not isinstance(text, str):
            return None

        candidates = []
        normalized = (
            text.replace("\ufeff", "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )

        if normalized:
            candidates.append(normalized)

        stripped = ParserMixin._normalize_action_candidate(
            normalized
        )

        if stripped and stripped not in candidates:
            candidates.append(stripped)

        extracted = ParserMixin._extract_json_objects(
            normalized
        )

        for candidate in extracted:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        for candidate in list(candidates):
            repaired = ParserMixin._repair_json_strings(
                candidate
            )

            if repaired and repaired not in candidates:
                candidates.append(repaired)

            repaired_commas = (
                ParserMixin._remove_trailing_json_commas(
                    repaired
                )
            )

            if (
                repaired_commas
                and repaired_commas not in candidates
            ):
                candidates.append(repaired_commas)

        for candidate in candidates:
            candidate = candidate.strip()

            if not candidate:
                continue

            try:
                action = json.loads(candidate)

                if isinstance(action, dict):
                    return action

            except (
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ):
                pass

        for candidate in candidates:
            repaired = ParserMixin._repair_json_strings(
                candidate
            )

            repaired = (
                ParserMixin._remove_trailing_json_commas(
                    repaired
                )
            )

            try:
                decoder = json.JSONDecoder()
                action, _ = decoder.raw_decode(
                    repaired.lstrip()
                )

                if isinstance(action, dict):
                    return action

            except (
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ):
                pass

        for candidate in candidates:
            candidate = candidate.strip()

            if not (
                candidate.startswith("{")
                and candidate.endswith("}")
            ):
                continue

            python_candidate = (
                ParserMixin._repair_json_strings(candidate)
            )

            python_candidate = (
                ParserMixin._remove_trailing_json_commas(
                    python_candidate
                )
            )

            try:
                import ast

                action = ast.literal_eval(
                    python_candidate
                )

                if isinstance(action, dict):
                    return action

            except (
                SyntaxError,
                ValueError,
                TypeError,
                MemoryError,
                RecursionError,
            ):
                pass

        return None

    @staticmethod
    def _extract_action(reply):
        if not reply or not isinstance(reply, str):
            return None

        normalized = (
            reply.replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
            .strip()
        )

        tag_pairs = [
            ("<ACTION>", "</ACTION>"),
            ("<action>", "</action>"),
            ("<Action>", "</Action>"),
            ("<ACTION>", "[/ACTION]"),
            ("[ACTION]", "</ACTION>"),
            ("[ACTION]", "[/ACTION]"),
            ("[action]", "[/action]"),
            ("[Action]", "[/Action]"),
            ("[ACTION>", "</ACTION>"),
            ("[action>", "</action>"),
            ("<ACTION>", ""),
            ("<action>", ""),
            ("[ACTION]", ""),
            ("[action]", ""),
            ("[ACTION>", ""),
            ("[action>", ""),
        ]

        candidates = []

        for start_tag, end_tag in tag_pairs:
            search_from = 0

            while search_from < len(normalized):
                start = normalized.find(
                    start_tag,
                    search_from,
                )

                if start == -1:
                    break

                content_start = (
                    start + len(start_tag)
                )

                if end_tag:
                    end = normalized.find(
                        end_tag,
                        content_start,
                    )

                    if end == -1:
                        search_from = content_start
                        continue

                    raw = normalized[
                        content_start:end
                    ].strip()

                    search_from = (
                        end + len(end_tag)
                    )
                else:
                    raw = normalized[
                        content_start:
                    ].strip()

                    search_from = len(normalized)

                if raw:
                    candidates.append(raw)

        if not candidates:
            extracted = ParserMixin._extract_json_objects(
                normalized
            )

            if extracted:
                candidates.extend(extracted)

        if not candidates:
            return None

        for raw in reversed(candidates):
            cleaned = ParserMixin._normalize_action_candidate(
                raw
            )

            if not cleaned:
                continue

            action = ParserMixin._parse_action_json(
                cleaned
            )

            if isinstance(action, dict):
                return action

        return None

    @staticmethod
    def _extract_actions(reply, limit=6):
        if not reply or not isinstance(reply, str):
            return []

        normalized = (
            reply.replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
        )

        pattern = re.compile(
            r"(?:<|\[)\s*ACTION\s*(?:>|\])"
            r"([\s\S]*?)"
            r"(?:<|\[)\s*/\s*ACTION\s*(?:>|\])",
            re.IGNORECASE,
        )

        actions = []

        for match in pattern.finditer(normalized):
            cleaned = ParserMixin._normalize_action_candidate(
                match.group(1)
            )

            if not cleaned:
                continue

            action = ParserMixin._parse_action_json(cleaned)

            if isinstance(action, dict) and action:
                actions.append(action)

                if len(actions) >= limit:
                    break

        if not actions:
            single = ParserMixin._extract_action(reply)

            if isinstance(single, dict) and single:
                actions.append(single)

        return actions

    @staticmethod
    def _remove_action_block(reply):
        if not reply or not isinstance(reply, str):
            return ""

        patterns = [
            ("<ACTION>", "</ACTION>"),
            ("<action>", "</action>"),
            ("[ACTION]", "[/ACTION]"),
            ("[action]", "[/action]"),
            ("[ACTION>", "</ACTION>"),
            ("[action>", "</action>"),
            ("<ACTION>", "[/ACTION]"),
            ("<action>", "[/action]"),
            ("<ACTION>", ""),
            ("<action>", ""),
            ("[ACTION]", ""),
            ("[action]", ""),
            ("[ACTION>", ""),
            ("[action>", ""),
        ]

        cleaned = reply.replace("\ufeff", "")

        while True:
            original = cleaned

            for start_tag, end_tag in patterns:
                start = cleaned.find(start_tag)

                if start == -1:
                    continue

                if end_tag:
                    end = cleaned.find(
                        end_tag,
                        start + len(start_tag),
                    )

                    if end != -1:
                        cleaned = (
                            cleaned[:start]
                            + cleaned[
                                end + len(end_tag):
                            ]
                        )
                        continue

                remainder = cleaned[
                    start + len(start_tag):
                ]

                next_markers = [
                    "<ACTION>",
                    "</ACTION>",
                    "<action>",
                    "</action>",
                    "[ACTION]",
                    "[/ACTION]",
                    "[action]",
                    "[/action]",
                    "[ACTION>",
                    "</ACTION>",
                    "[action>",
                    "</action>",
                ]

                next_position = len(remainder)

                for marker in next_markers:
                    position = remainder.find(marker)

                    if (
                        position != -1
                        and position < next_position
                    ):
                        next_position = position

                cleaned = (
                    cleaned[:start]
                    + remainder[next_position:]
                )

            if cleaned == original:
                break

        lines = cleaned.splitlines()
        result = []
        inside_action = False

        action_markers = {
            "<ACTION>",
            "</ACTION>",
            "<action>",
            "</action>",
            "[ACTION]",
            "[/ACTION]",
            "[action]",
            "[/action]",
            "[ACTION>",
            "[action>",
        }

        for line in lines:
            stripped = line.strip()

            if stripped in action_markers:
                if (
                    stripped in {
                        "<ACTION>",
                        "<action>",
                        "[ACTION]",
                        "[action]",
                        "[ACTION>",
                        "[action>",
                    }
                ):
                    inside_action = True
                else:
                    inside_action = False

                continue

            if inside_action:
                continue

            result.append(line)

        cleaned = "\n".join(result)

        while "\n\n\n" in cleaned:
            cleaned = cleaned.replace(
                "\n\n\n",
                "\n\n",
            )

        return cleaned.strip()

    def _clean_leaked_feedback(self, text):
        if not text or not isinstance(text, str):
            return ""

        cleaned = text

        start_pattern = (
            r"\[\s*ACTION\s+RESULT\s+FROM\s+PREVIOUS\s+REQUEST\s*\]"
        )

        end_pattern = (
            r"\[\s*END\s+ACTION\s+RESULT\s*\]"
        )

        cleaned = re.sub(
            start_pattern + r"[\s\S]*?" + end_pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            start_pattern + r"[\s\S]*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            end_pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"(?im)^[ \t]*Feedback-?[ \t]*ID[ \t]*:.*"
            r"(?:\n[ \t]*Action[ \t]*:.*)?"
            r"(?:\n[ \t]*Result[ \t]*:.*)?$",
            "",
            cleaned,
        )

        feedback_id = getattr(
            self,
            "feedback_id",
            "",
        )

        if feedback_id:
            cleaned = cleaned.replace(
                feedback_id,
                "",
            )

        cleaned = re.sub(
            r"\n{3,}",
            "\n\n",
            cleaned,
        )

        return cleaned.strip()

    def _fix_literal_newlines(self, text):
        if not text or not isinstance(text, str):
            return ""

        if "```" in text:
            return text.strip()

        text = text.replace("\\r\\n", "\n")
        text = text.replace("\\n", "\n")
        text = text.replace("\\r", "\n")
        text = text.replace("\\t", " ")
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()
