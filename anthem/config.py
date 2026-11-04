"""Settings and genre presets for Anthem.

Keys live in settings.json next to this project. That file holds secrets,
so it never goes into a zip you share or a public repo.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
STYLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.json")
OUTPUT_DIR = os.path.join(ROOT, "output")
ASSETS_DIR = os.path.join(ROOT, "assets")

# Local and free by design: no accounts, no keys, no metered APIs.
# "acestep" generates on this PC and needs a GPU; "file" takes an mp3 you
# already have and works anywhere. The default is "file" so the app is
# useful the moment it opens, even before the ACE-Step server is running.
DEFAULTS = {
    "provider": "file",
    "acestep_url": "http://localhost:8001",
    "acestep_token": "",        # only if you started the server with auth
    "song_length": 0,           # 0 means "use the style's own default"
    "video_resolution": "1920x1080",
    "video_fps": 30,
    "video_motion": "kenburns",
    "visualizer": "bars",
    "visualizer_color": "#4FC3F7",
    "audio_bitrate": "320k",
    "channel_name": "",
    "poll_timeout_seconds": 1800,
}

# Offered in the Length dropdown. Seconds, and the label people think in.
LENGTH_CHOICES = [
    (0, "Auto (style default)"),
    (60, "1:00  - short / loop"),
    (90, "1:30  - teaser"),
    (120, "2:00  - radio edit"),
    (150, "2:30"),
    (180, "3:00  - single"),
    (210, "3:30"),
    (240, "4:00  - club mix"),
    (300, "5:00  - extended"),
    (360, "6:00  - full club"),
]


def load():
    """Return settings, filling anything missing with the defaults."""
    data = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data.update(json.load(fh))
        except (OSError, ValueError) as exc:
            print("Could not read settings.json (%s) - using defaults." % exc)
    # Environment wins, so a server token need not be written to disk.
    if os.environ.get("ACESTEP_TOKEN"):
        data["acestep_token"] = os.environ["ACESTEP_TOKEN"]
    if os.environ.get("ACESTEP_URL"):
        data["acestep_url"] = os.environ["ACESTEP_URL"]
    return data


def save(data):
    keep = {k: v for k, v in data.items() if k in DEFAULTS}
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, indent=2)
    return SETTINGS_PATH


def styles():
    with open(STYLES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_dirs():
    for path in (OUTPUT_DIR, ASSETS_DIR):
        os.makedirs(path, exist_ok=True)
