"""Turn a finished track plus a background into a YouTube-ready MP4.

Everything here is ffmpeg. That matters on a 2-core laptop: no Python
touches the pixels, so render speed is whatever ffmpeg can manage, and the
presets below are chosen to stay close to realtime rather than to win a
compression contest.

Output targets YouTube's own recommendation: H.264 high profile, yuv420p,
closed GOP at 2 seconds, faststart, and 48 kHz AAC audio.
"""

import json
import os
import subprocess
import sys

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv")

VISUALIZERS = {
    "none": "No visualizer",
    "bars": "Frequency bars",
    "wave": "Waveform line",
    "spectrum": "Spectrum glow",
}

MOTIONS = {
    "none": "Static background",
    "kenburns": "Slow zoom in (Ken Burns)",
    "drift": "Slow pan across",
}


class VideoError(RuntimeError):
    pass


# ----------------------------------------------------------------------
# probing


def _run(cmd, timeout=None):
    """Run a child process without flashing a console window on Windows."""
    kwargs = {}
    if sys.platform == "win32":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startup
    return subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, errors="replace", timeout=timeout, **kwargs)


def have_ffmpeg():
    try:
        return _run([FFMPEG, "-version"], timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def duration_of(path):
    """Length in seconds, or 0.0 if ffprobe cannot tell."""
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "json", path]
    try:
        result = _run(cmd, timeout=60)
        if result.returncode != 0:
            return 0.0
        return float(json.loads(result.stdout)["format"]["duration"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return 0.0


def kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return "unknown"


# ----------------------------------------------------------------------
# filter graph


def _hex_to_ffmpeg(colour):
    colour = (colour or "").strip()
    if colour.startswith("#") and len(colour) == 7:
        return "0x" + colour[1:]
    return colour or "0x4FC3F7"


def _background_chain(kind, motion, width, height, fps, seconds):
    """Scale and crop the background to fill the frame, then add motion."""
    if kind == "image" and motion in ("kenburns", "drift"):
        # zoompan quantises its zoom to the input resolution, which shows up
        # as visible stepping. Working from a larger intermediate hides it;
        # 1.5x is the most this CPU can carry without dropping under
        # realtime, and it is enough.
        base_w, base_h = int(width * 1.5), int(height * 1.5)
        total = max(int(seconds * fps), 1)
        chain = ("scale=%d:%d:force_original_aspect_ratio=increase,"
                 "crop=%d:%d," % (base_w, base_h, base_w, base_h))
        if motion == "kenburns":
            chain += (
                "zoompan=z='min(1+0.00035*on,1.25)':d=1"
                ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)"
                "':s=%dx%d:fps=%d," % (width, height, fps))
        else:  # drift
            chain += (
                "zoompan=z=1.18:d=1"
                ":x='(iw-iw/zoom)*(on/%d)':y='ih/2-(ih/zoom/2)"
                "':s=%dx%d:fps=%d," % (total, width, height, fps))
        return chain + "setsar=1"

    chain = ("scale=%d:%d:force_original_aspect_ratio=increase,"
             "crop=%d:%d,setsar=1" % (width, height, width, height))
    if kind == "video":
        chain += ",fps=%d" % fps
    return chain


def _visualizer_chain(style, width, colour, fps):
    """Audio-reactive overlay, keyed over the background."""
    vis_h = 260
    colour = _hex_to_ffmpeg(colour)
    # showfreqs and showwaves take one colour per audio channel. Give a
    # stereo track a single colour and the right channel falls back to
    # white, which is where the grey wash in early builds came from.
    pair = "%s|%s" % (colour, colour)

    if style == "bars":
        src = ("showfreqs=mode=bar:ascale=log:fscale=log:win_size=1024"
               ":size=%dx%d:colors=%s" % (width, vis_h, pair))
    elif style == "wave":
        src = ("showwaves=mode=cline:rate=%d:size=%dx%d:colors=%s"
               % (fps, width, vis_h, pair))
    elif style == "spectrum":
        src = ("showspectrum=size=%dx%d:slide=scroll:mode=combined"
               ":color=intensity:scale=cbrt:saturation=2"
               % (width, vis_h))
    else:
        return None, vis_h

    # Black is the visualizer's background, so key it out rather than
    # pasting a black slab over the artwork.
    # Key out the visualizer's black bed, then pull it back from full
    # opacity so it reads as an overlay on the artwork, not a sticker.
    src += (",format=rgba,colorkey=0x000000:0.30:0.10,"
            "colorchannelmixer=aa=0.78")
    return src, vis_h


def build_command(audio_path, background, out_path, settings,
                  title_text="", seconds=None):
    width, height = _resolution(settings)
    fps = int(settings.get("video_fps", 30) or 30)
    motion = settings.get("video_motion", "kenburns")
    visualizer = settings.get("visualizer", "bars")
    colour = settings.get("visualizer_color", "#4FC3F7")
    bitrate = settings.get("audio_bitrate", "320k")

    if seconds is None:
        seconds = duration_of(audio_path) or 180.0

    kind = kind_of(background) if background else "none"

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-stats", "-i", audio_path]

    if kind == "image":
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", background]
    elif kind == "video":
        cmd += ["-stream_loop", "-1", "-i", background]
    else:
        cmd += ["-f", "lavfi", "-i",
                "color=c=0x101018:s=%dx%d:r=%d" % (width, height, fps)]

    parts = []
    bg = _background_chain(kind if kind != "none" else "video",
                           motion, width, height, fps, seconds)
    parts.append("[1:v]%s[bg]" % bg)

    vis, vis_h = _visualizer_chain(visualizer, width, colour, fps)
    last = "bg"
    if vis:
        parts.append("[0:a]%s[vis]" % vis)
        parts.append("[bg][vis]overlay=x=0:y=H-%d:shortest=0[withvis]" % vis_h)
        last = "withvis"

    font = _find_font()
    if title_text and font:
        safe = _escape_drawtext(title_text)
        parts.append(
            "[%s]drawtext=fontfile='%s':text='%s':fontcolor=white@0.92"
            ":fontsize=%d:x=(w-text_w)/2:y=h*0.08"
            ":borderw=3:bordercolor=black@0.55[titled]"
            % (last, font, safe, max(int(height / 18), 28)))
        last = "titled"

    parts.append("[%s]format=yuv420p[v]" % last)

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-profile:v", "high", "-level", "4.1",
        "-r", str(fps), "-g", str(fps * 2), "-keyint_min", str(fps),
        "-c:a", "aac", "-b:a", bitrate, "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-t", "%.3f" % seconds,
        out_path,
    ]
    return cmd


def _resolution(settings):
    raw = str(settings.get("video_resolution", "1920x1080")).lower()
    try:
        width, height = (int(v) for v in raw.split("x", 1))
    except ValueError:
        return 1920, 1080
    # x264 needs even dimensions for yuv420p.
    return width - (width % 2), height - (height % 2)


def _find_font():
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            # Inside a filtergraph a Windows drive colon has to be escaped
            # or ffmpeg reads it as an option separator.
            return path.replace("\\", "/").replace(":", r"\:")
    return ""


def _escape_drawtext(text):
    out = text.replace("\\", r"\\").replace("'", r"\'")
    for char in (":", "%", "[", "]", ","):
        out = out.replace(char, "\\" + char)
    return out


# ----------------------------------------------------------------------
# render


def render(audio_path, background, out_path, settings,
           title_text="", progress=None):
    if not have_ffmpeg():
        raise VideoError(
            "ffmpeg is not on PATH. Install it and reopen Anthem.")
    if not os.path.isfile(audio_path):
        raise VideoError("No audio at %s" % audio_path)
    if background and not os.path.isfile(background):
        raise VideoError("No background file at %s" % background)
    if background and kind_of(background) == "unknown":
        raise VideoError(
            "%s is not an image or video Anthem recognises."
            % os.path.basename(background))

    seconds = duration_of(audio_path)
    if seconds <= 0:
        raise VideoError(
            "Could not read the length of %s - is it a valid audio file?"
            % os.path.basename(audio_path))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cmd = build_command(audio_path, background, out_path, settings,
                        title_text, seconds)

    if progress:
        progress("Rendering video (%s, about %d seconds of audio)..."
                 % (settings.get("video_resolution", "1920x1080"), seconds))

    result = _run(cmd, timeout=max(1800, int(seconds * 12)))
    if result.returncode != 0 or not os.path.exists(out_path):
        raise VideoError(
            "ffmpeg failed.\n\n%s" % _tail(result.stdout))

    return out_path


def _tail(text, lines=14):
    rows = [r for r in (text or "").splitlines() if r.strip()]
    return "\n".join(rows[-lines:]) or "no output from ffmpeg"
