import re
import colorsys
from zanelmodules.config import (
    DEFAULT_THEME,
    DEFAULT_THEME_ACCENT,
    DEFAULT_THEME_NAME,
    THEME_PRESETS,
)


def normalize_hex(value):
    value = str(value or "").strip().lower()

    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value

    return None


def hsl_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(
        h,
        max(0.0, min(1.0, l)),
        max(0.0, min(1.0, s)),
    )

    return "#%02x%02x%02x" % (
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)),
    )


def hex_to_hsv(value):
    value = normalize_hex(value) or DEFAULT_THEME_ACCENT.lower()

    r, g, b = (
        int(value[index:index + 2], 16) / 255.0
        for index in (1, 3, 5)
    )

    return colorsys.rgb_to_hsv(r, g, b)


def hsv_to_hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)

    return "#%02x%02x%02x" % (
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)),
    )


def build_theme(accent):
    accent = normalize_hex(accent) or DEFAULT_THEME_ACCENT.lower()

    r, g, b = (
        int(accent[index:index + 2], 16) / 255.0
        for index in (1, 3, 5)
    )

    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.55, min(0.75, l))
    base_s = min(0.3, s)

    steps = {
        "bg": 0.050,
        "panel": 0.068,
        "title": 0.075,
        "skip": 0.082,
        "field": 0.088,
        "upload": 0.095,
        "mic": 0.102,
        "button": 0.112,
        "mic_press": 0.125,
        "button_hover": 0.150,
        "track": 0.175,
        "border": 0.200,
    }

    theme = {
        key: hsl_hex(h, base_s, value)
        for key, value in steps.items()
    }

    theme["glow"] = hsl_hex(h, min(s, 0.55), 0.38)
    theme["accent"] = hsl_hex(h, s, l)
    theme["accent_hover"] = hsl_hex(h, s, l + 0.08)
    theme["accent_press"] = hsl_hex(h, s, l - 0.08)

    seen = set()

    for key in list(theme):
        value = theme[key]

        while value in seen:
            value = "#%s%s%02x" % (
                value[1:3],
                value[3:5],
                (int(value[5:7], 16) + 1) % 256,
            )

        seen.add(value)
        theme[key] = value

    return theme


def get_theme(name, accent):
    if name == DEFAULT_THEME_NAME:
        return dict(DEFAULT_THEME)

    if name in THEME_PRESETS:
        return build_theme(THEME_PRESETS[name])

    return build_theme(accent)


def theme_color_map(source, target):
    mapping = {}

    for key, old in source.items():
        new = target.get(key)

        if new and old.lower() != new.lower():
            mapping[old.lower()] = new

    return mapping


def blend_color(start, end, amount):
    amount = max(0.0, min(1.0, amount))

    start_rgb = (
        int(start[1:3], 16),
        int(start[3:5], 16),
        int(start[5:7], 16),
    )

    end_rgb = (
        int(end[1:3], 16),
        int(end[3:5], 16),
        int(end[5:7], 16),
    )

    return "#%02x%02x%02x" % tuple(
        int(start_rgb[index] + (end_rgb[index] - start_rgb[index]) * amount)
        for index in range(3)
    )
