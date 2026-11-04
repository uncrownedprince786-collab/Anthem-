"""Write the YouTube paperwork that ships beside each video.

Uploading is deliberately manual. An automated uploader needs OAuth, a
Google Cloud project and a quota review, and a channel that gets it wrong
is a channel at risk - so Anthem writes a text file you paste from.
"""

import os
import re

# Tags YouTube's own search traffic actually uses for these genres.
GENRE_TAGS = {
    "trance": ["trance", "uplifting trance", "trance music", "edm",
               "festival trance", "vocal trance", "emotional trance"],
    "progressive": ["progressive house", "melodic house", "deep house",
                    "melodic techno", "edm", "anjunadeep"],
    "club": ["club music", "party music", "big room", "edm", "dance music",
             "festival anthem", "party anthem"],
    "techno": ["melodic techno", "techno", "afterlife", "dark techno",
               "electronic music", "underground techno"],
    "smooth": ["smooth music", "rnb", "soul music", "chill vibes",
               "late night music", "relaxing music"],
    "chill": ["chillout", "lofi", "chill music", "ambient", "relaxing music",
              "study music", "downtempo"],
    "hardstyle": ["hardstyle", "hard dance", "euphoric hardstyle", "edm",
                  "rawstyle", "festival"],
    "afro": ["afro house", "afrohouse", "organic house", "deep house",
             "tribal house", "sunset mix"],
}

DISCLOSURE = (
    "This track was created with AI music generation. When you upload, set "
    "\"Altered or synthetic content\" to Yes in YouTube's own upload form - "
    "the line in this description does not replace that toggle."
)


def tags_for(genre, title, extra=None):
    tags = list(GENRE_TAGS.get(genre, []))
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", title or "")]
    tags = words[:3] + tags
    for item in (extra or []):
        item = item.strip().lower()
        if item:
            tags.append(item)

    seen, out, budget = set(), [], 0
    for tag in tags:
        if tag in seen:
            continue
        # YouTube caps the tag field at 500 characters in total.
        if budget + len(tag) + 2 > 480:
            break
        seen.add(tag)
        out.append(tag)
        budget += len(tag) + 2
    return out


def build_title(song_title, genre, styles):
    label = (styles.get(genre) or {}).get("label", genre.title())
    base = song_title.strip() or "Untitled"
    full = "%s | %s" % (base, label)
    # YouTube truncates titles past 100 characters in most surfaces.
    return full if len(full) <= 100 else base[:97] + "..."


def build_description(song_title, genre, styles, lyrics="",
                      channel_name="", style_prompt=""):
    style = styles.get(genre) or {}
    label = style.get("label", genre.title())
    bpm = style.get("bpm")

    lines = ["%s - an original %s track." % (song_title, label.lower())]
    if bpm:
        lines.append("BPM: %s" % bpm)
    lines.append("")

    if style_prompt:
        lines += ["Style", style_prompt, ""]

    clean = _lyrics_block(lyrics)
    if clean:
        lines += ["Lyrics", "", clean, ""]

    lines += [DISCLOSURE, ""]

    if channel_name:
        lines += ["Subscribe to %s for more." % channel_name, ""]

    hashtags = " ".join(
        "#" + re.sub(r"[^a-z0-9]", "", t)
        for t in tags_for(genre, song_title)[:4]
        if re.sub(r"[^a-z0-9]", "", t)
    )
    if hashtags:
        lines.append(hashtags)

    text = "\n".join(lines)
    # YouTube's description limit is 5000 characters.
    return text if len(text) <= 5000 else text[:4990] + "\n[...]"


def _lyrics_block(lyrics):
    """Lyrics without the model's section tags, which read as noise."""
    out = []
    for line in (lyrics or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue
        if re.match(r"^[\[\(].*[\]\)]$", stripped):
            continue
        out.append(stripped)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def write(path, song_title, genre, styles, lyrics="", channel_name="",
          style_prompt="", video_path="", audio_path=""):
    title = build_title(song_title, genre, styles)
    description = build_description(
        song_title, genre, styles, lyrics, channel_name, style_prompt)
    tags = tags_for(genre, song_title)

    body = [
        "=" * 64,
        "YOUTUBE TITLE  (paste into the title field)",
        "=" * 64,
        title,
        "",
        "=" * 64,
        "DESCRIPTION  (paste into the description field)",
        "=" * 64,
        description,
        "",
        "=" * 64,
        "TAGS  (paste into the tags field, comma separated)",
        "=" * 64,
        ", ".join(tags),
        "",
        "=" * 64,
        "BEFORE YOU PUBLISH",
        "=" * 64,
        "1. Set 'Altered or synthetic content' to Yes. YouTube requires it",
        "   for AI-generated music and it is the one step nobody can skip.",
        "2. Confirm your music plan allows commercial use and monetisation.",
        "   The licence comes from the service that generated the audio.",
        "3. Make sure the background image or video is yours or licensed.",
        "   Stock footage with the wrong licence is the usual claim magnet.",
        "",
        "Files",
        "  video: %s" % (video_path or "-"),
        "  audio: %s" % (audio_path or "-"),
        "",
    ]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body))
    return path


def slug(text):
    keep = [c if c.isalnum() or c in " -_" else "" for c in (text or "")]
    return ("".join(keep).strip().replace(" ", "_") or "track")[:60]


def unique_dir(base, name):
    """A run folder that never clobbers an earlier render."""
    candidate = os.path.join(base, name)
    index = 2
    while os.path.exists(candidate):
        candidate = os.path.join(base, "%s_%d" % (name, index))
        index += 1
    os.makedirs(candidate, exist_ok=True)
    return candidate
