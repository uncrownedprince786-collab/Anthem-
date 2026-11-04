"""Lyrics in, finished YouTube folder out.

One call does the whole job: shape the lyrics, generate the audio, render a
video per take, and drop the title/description/tags beside them. Each run
gets its own folder under output/ so nothing overwrites anything.
"""

import os
import time
from dataclasses import dataclass, field

from . import config, lyrics as lyrics_mod, metadata, providers, video


@dataclass
class Job:
    lyrics: str = ""
    genre: str = "trance"
    title: str = ""
    background: str = ""
    instrumental: bool = False
    length_seconds: int = 0
    extra_style: str = ""
    source_audio: str = ""       # only used by the "file" provider
    make_video: bool = True


@dataclass
class Result:
    run_dir: str = ""
    title: str = ""
    tracks: list = field(default_factory=list)
    videos: list = field(default_factory=list)
    notes_files: list = field(default_factory=list)
    seconds: float = 0.0


def style_prompt_for(genre, styles, extra=""):
    base = (styles.get(genre) or {}).get("prompt", genre)
    extra = (extra or "").strip()
    return "%s, %s" % (base, extra) if extra else base


def run(job, settings=None, progress=None):
    started = time.time()
    settings = dict(settings or config.load())
    config.ensure_dirs()
    styles = config.styles()

    if job.genre not in styles:
        raise providers.ProviderError(
            "Unknown style '%s'. Pick one of: %s"
            % (job.genre, ", ".join(sorted(styles))))
    style = styles[job.genre]

    def say(message):
        if progress:
            progress(message)

    # --- lyrics ------------------------------------------------------
    shaped = ""
    if not job.instrumental:
        shaped = lyrics_mod.structure(job.lyrics, style["structure"])
        if not shaped.strip():
            raise providers.ProviderError(
                "No lyrics given. Write some, or tick Instrumental.")

    title = (job.title or "").strip()
    if not title:
        title = lyrics_mod.suggest_title(job.lyrics or "", style["label"])
    say("Title: %s" % title)

    # Fail before anything is written to disk, so a missing API key does
    # not litter output/ with empty run folders.
    backend = providers.get(settings.get("provider", "file"), settings)
    if not backend.configured():
        raise providers.ProviderError(backend.missing_message())

    # --- run folder --------------------------------------------------
    run_dir = metadata.unique_dir(config.OUTPUT_DIR, metadata.slug(title))
    settings["_run_dir"] = run_dir
    settings["_source_audio"] = job.source_audio
    say("Working in %s" % run_dir)

    if shaped:
        with open(os.path.join(run_dir, "lyrics.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(shaped)

    # --- generate ----------------------------------------------------
    style_prompt = style_prompt_for(job.genre, styles, job.extra_style)
    request = providers.Request(
        lyrics=shaped,
        style_prompt=style_prompt,
        negative_prompt=style.get("negative", ""),
        title=title,
        instrumental=job.instrumental,
        length_seconds=job.length_seconds or style.get("default_length", 200),
    )

    tracks = backend.generate(request, progress=say)
    if not tracks:
        raise providers.ProviderError(
            "%s returned no audio." % backend.label)
    say("Got %d take%s." % (len(tracks), "" if len(tracks) == 1 else "s"))

    result = Result(run_dir=run_dir, title=title, tracks=tracks)

    # --- video + paperwork -------------------------------------------
    for index, track in enumerate(tracks, 1):
        suffix = "" if len(tracks) == 1 else "_take%d" % index
        stem = metadata.slug(track.title or title) + suffix

        made_video = ""
        if job.make_video:
            out_path = os.path.join(run_dir, stem + ".mp4")
            say("Rendering video for take %d..." % index)
            try:
                video.render(track.audio_path, job.background, out_path,
                             settings, title_text=track.title or title,
                             progress=say)
                result.videos.append(out_path)
                made_video = out_path
            except video.VideoError as exc:
                # A failed render must not cost the audio, which was paid for.
                say("Video failed for take %d: %s" % (index, exc))

        notes = os.path.join(run_dir, stem + "_youtube.txt")
        metadata.write(
            notes, track.title or title, job.genre, styles,
            lyrics=track.lyrics or shaped,
            channel_name=settings.get("channel_name", ""),
            style_prompt=style_prompt,
            video_path=made_video,
            audio_path=track.audio_path,
        )
        result.notes_files.append(notes)

    result.seconds = time.time() - started
    say("Done in %d seconds." % result.seconds)
    return result
