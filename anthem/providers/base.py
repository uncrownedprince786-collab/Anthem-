"""Common shape every music backend implements.

Anthem does not care which service makes the audio. A provider takes a
Request and returns finished Track objects with a local .mp3 on disk.
"""

import os
import time
import urllib.request
from dataclasses import dataclass, field


class ProviderError(RuntimeError):
    """Raised when a backend fails in a way the user needs to read."""


@dataclass
class Request:
    lyrics: str = ""
    style_prompt: str = ""
    negative_prompt: str = ""
    title: str = "Untitled"
    instrumental: bool = False
    length_seconds: int = 200
    model: str = ""


@dataclass
class Track:
    title: str
    audio_path: str
    provider: str
    style_prompt: str = ""
    lyrics: str = ""
    duration: float = 0.0
    image_url: str = ""
    raw: dict = field(default_factory=dict)


class Provider:
    name = "base"
    label = "Base"

    def __init__(self, settings):
        self.settings = settings

    def configured(self):
        """True when this backend has what it needs to run."""
        return False

    def missing_message(self):
        return "%s is not configured." % self.label

    def generate(self, request, progress=None):
        raise NotImplementedError

    # -- helpers shared by the HTTP backends -------------------------------

    @staticmethod
    def _say(progress, message):
        if progress:
            progress(message)

    @staticmethod
    def download(url, dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Anthem/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp, \
                open(dest, "wb") as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
        return dest

    @staticmethod
    def wait(seconds):
        time.sleep(seconds)
