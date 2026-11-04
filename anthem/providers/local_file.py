"""Use audio you already have.

Two cases this covers, both common:

* You pay for Suno's web app and downloaded the mp3 yourself. No reason to
  pay a second time through an API - point Anthem at the file.
* You want to test the video side without spending a credit.

Nothing is generated here; the file is copied into the run folder so the
rest of the pipeline treats it like any other take.
"""

import os
import shutil

from .base import Provider, ProviderError, Track

AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma")


class LocalFileProvider(Provider):
    name = "file"
    label = "Free - music I downloaded"

    def configured(self):
        return True

    def generate(self, request, progress=None):
        source = (self.settings.get("_source_audio") or "").strip('"').strip()
        if not source:
            raise ProviderError(
                "Pick the audio file you want to use first.")
        if not os.path.isfile(source):
            raise ProviderError("No file at: %s" % source)
        if not source.lower().endswith(AUDIO_EXT):
            raise ProviderError(
                "%s is not an audio file Anthem recognises (%s)."
                % (os.path.basename(source), ", ".join(AUDIO_EXT)))

        title = request.title or os.path.splitext(os.path.basename(source))[0]
        dest = os.path.join(
            self.settings["_run_dir"],
            _slug(title) + os.path.splitext(source)[1].lower())

        self._say(progress, "Copying %s..." % os.path.basename(source))
        # copyfile, not copy2: we do not want the source's read-only bit
        # following the file into the run folder.
        shutil.copyfile(source, dest)

        return [Track(
            title=title,
            audio_path=dest,
            provider=self.name,
            style_prompt=request.style_prompt,
            lyrics=request.lyrics,
            raw={"source": source},
        )]


def _slug(text):
    keep = [c if c.isalnum() or c in " -_" else "" for c in text]
    return ("".join(keep).strip().replace(" ", "_") or "track")[:60]
