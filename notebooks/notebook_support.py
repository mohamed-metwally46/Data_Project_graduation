"""Read validated Globiq release artifacts and render notebook bar charts."""
import hashlib
import json
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


BLUE = "#2463a4"
TEAL = "#157d77"
GOLD = "#a96b21"


def load_release(component):
    root = next(p for p in (Path.cwd(), *Path.cwd().parents)
                if (p / "data/processed/analytics/trade_intelligence_release.json").is_file())
    manifest = json.loads(
        (root / "data/processed/analytics/trade_intelligence_release.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "validated":
        raise ValueError("The Trade Intelligence release must be validated")
    entry = manifest["artifacts"][component]
    payload = (root / manifest["artifact_directory"] / entry["path"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValueError(f"Integrity check failed for {component}")
    return manifest, json.loads(payload)


def top(rows, key, identity, limit=8):
    return sorted(rows, key=lambda row: (-row[key], identity(row)))[:limit]


def _font(size, bold=False):
    choices = ("segoeuib.ttf", "DejaVuSans-Bold.ttf") if bold else ("segoeui.ttf", "DejaVuSans.ttf")
    for filename in choices:
        try:
            return ImageFont.truetype(filename, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def bar_chart(title, axis_label, items, color=BLUE):
    """Horizontal bar chart with a zero baseline and exact value labels."""
    width, left, right = 960, 340, 864
    row_height = 44
    first = 113
    bottom = first + row_height * len(items)
    image = Image.new("RGB", (width, bottom + 53), "#ffffff")
    draw = ImageDraw.Draw(image)
    ink, muted = "#15263b", "#475a70"
    draw.text((28, 22), title, font=_font(27, True), fill=ink)
    draw.text((28, 63), axis_label, font=_font(16), fill=muted)
    maximum = max((value for _, value in items), default=0) or 1
    label_font = _font(16)
    for n in range(5):
        x = left + (right - left) * n / 4
        draw.line((x, first - 12, x, bottom), fill="#e1e8ef", width=1)
        draw.text((x, bottom + 11), f"{round(maximum * n / 4):,}",
                  font=_font(13), fill=muted, anchor="mt")
    for n, (label, value) in enumerate(items):
        y = first + n * row_height
        # Keep labels clear of the plotting area on multiple font platforms.
        label = textwrap.shorten(label, width=52, placeholder="...")
        while draw.textlength(label, font=label_font) > left - 40:
            label = label[:-4] + "..."
        draw.text((left - 14, y + 12), label, font=label_font, fill=ink, anchor="rm")
        bar_end = left + (right - left) * value / maximum
        if value:
            draw.rectangle((left, y, bar_end, y + 24), fill=color)
        draw.text((bar_end + 8, y + 12), f"{value:,}", font=_font(15, True), fill=ink, anchor="lm")
    return image
