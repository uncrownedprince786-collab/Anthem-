"""Shape raw lyrics into the tagged form music models follow best.

Suno-family models read section tags - [Verse], [Chorus], [Drop] - as
structural instructions. Lyrics pasted as a flat wall of text give the model
nothing to build an arrangement around, which is the single most common
reason a generated track wanders. This module adds the tags when they are
missing and leaves them alone when you wrote your own.
"""

import re

TAG_RE = re.compile(r"^\s*[\[\(]\s*([A-Za-z0-9 /&'-]+)\s*[\]\)]\s*$")

# Sections that carry no sung words. We keep them, but they never get lyrics.
INSTRUMENTAL = {"intro", "outro", "build", "drop", "breakdown", "break",
                "instrumental", "solo", "interlude"}

HOOK_SECTIONS = {"chorus", "pre-chorus", "hook"}


def has_tags(text):
    return any(TAG_RE.match(line) for line in text.splitlines())


def split_blocks(text):
    """Split on blank lines into blocks of non-empty lines."""
    blocks, current = [], []
    for line in text.splitlines():
        if line.strip():
            current.append(line.rstrip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def structure(text, pattern):
    """Fit lyric blocks to a genre's section pattern.

    Repeated identical blocks become the chorus, which is how most people
    actually write lyrics without thinking about it. Verses are handed out in
    order and cycle if the pattern asks for more of them than you wrote.
    """
    text = (text or "").strip()
    if not text:
        return ""
    if has_tags(text):
        return text  # Author knows what they want.

    blocks = split_blocks(text)
    if not blocks:
        return ""

    # A block that appears more than once is the hook.
    counts, chorus = {}, None
    for block in blocks:
        key = "\n".join(line.strip().lower() for line in block)
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > 1 and chorus is None:
            chorus = block

    verses = [b for b in blocks if b != chorus]
    if not verses:
        verses = blocks  # Every block was the same; use it everywhere.
    if chorus is None:
        # No repeat to lean on: the last block is the most likely hook, unless
        # taking it would leave nothing to sing in the verses.
        chorus = verses.pop() if len(verses) > 1 else verses[0]

    out, v_index = [], 0
    for section in pattern:
        low = section.lower()
        if low in INSTRUMENTAL:
            out.append("[%s]" % section)
        elif low in HOOK_SECTIONS:
            out.append("[%s]\n%s" % (section, "\n".join(chorus)))
        else:
            block = verses[v_index % len(verses)]
            out.append("[%s]\n%s" % (section, "\n".join(block)))
            v_index += 1

    return "\n\n".join(out)


def word_count(text):
    stripped = [line for line in text.splitlines() if not TAG_RE.match(line)]
    return len(" ".join(stripped).split())


def suggest_title(text, fallback="Untitled"):
    """The first strong line of the hook makes a decent working title."""
    for line in text.splitlines():
        clean = line.strip()
        if not clean or TAG_RE.match(clean):
            continue
        words = clean.strip(" .,!?-—").split()
        if 2 <= len(words) <= 8:
            return " ".join(w.capitalize() if w.islower() else w for w in words)
    return fallback
