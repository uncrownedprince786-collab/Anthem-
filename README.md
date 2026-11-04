# Anthem

Turn lyrics into a YouTube-ready music video, on your own machine.

Paste lyrics, pick a style, a length and a picture. Out comes a 1080p MP4
with its title, description and tags written beside it.

**Free and local by design.** No account, no sign-up, no API key, no metered
service. Nothing is uploaded and nothing expires.

Double-click **Anthem.cmd** to open it.

## How the audio gets made

Two backends, both free, neither needing an account:

**ACE-Step on this PC** — [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5)
runs locally and generates the music from your lyrics. Needs a GPU with
**6 GB of VRAM or more**. See [SETUP-LOCAL.md](SETUP-LOCAL.md). This is what
the project is for.

**Music I already have** — point Anthem at any mp3 you own. It still shapes
the lyrics, renders the video and writes the YouTube text. Works on any
machine, needs nothing at all. Use this until the hardware is ready.

Paid API backends were removed on purpose. This project does not call
anything you have to log into or pay for.

## What runs where

| Step | Where |
|---|---|
| Shaping lyrics into sections | your PC, instant |
| Generating the music | your PC, via the local ACE-Step server |
| Rendering the video | your PC, ffmpeg, roughly realtime |
| Title, description, tags | your PC, instant |

Every row is local. The only network call Anthem ever makes is to
`localhost`.

## Requirements

- **Python 3.12** — Anthem needs no pip packages at all, standard library only
- **ffmpeg** on PATH — for the video
- For local generation: a GPU, per [SETUP-LOCAL.md](SETUP-LOCAL.md)

## What ships with it

**Backgrounds** — `assets/backgrounds/` holds seven 1920x1080 images, one
per mood: `trance_night`, `progressive_deep`, `club_heat`, `techno_steel`,
`smooth_amber`, `chill_teal`, `afro_sunset`. Generated with ffmpeg, so they
are yours outright — no stock licence, no Content ID risk.

**Starter lyrics** — `assets/lyrics/` has three complete sets written to
work with the structurer: `trance_never_fades`, `club_turn_it_up`,
`smooth_two_in_the_morning`.

## Writing lyrics

Leave a blank line between sections. Repeat a block and it becomes the
chorus:

```
We rise above the city lights
Holding on until the morning

Feel the fire, feel it burn
Never coming back again

Feel the fire, feel it burn
Never coming back again
```

Anthem turns that into the tagged form music models follow, fitted to the
genre — trance gets `[Intro] [Verse] [Build] [Drop] [Breakdown] [Chorus]
[Build] [Drop] [Outro]`, smooth R&B gets verses and choruses. Write your own
`[Verse]` tags and they are kept.

This matters more than it looks. Lyrics pasted as a flat wall of text give
the model no arrangement to build, which is the usual reason a generated
track wanders off.

## Styles and length

`trance`, `progressive`, `club`, `techno`, `smooth`, `chill`, `hardstyle`,
`afro`. Each carries a tuned prompt, a BPM and a section pattern. Edit
`anthem/styles.json` to change one or add your own — it is plain text.

**Length** runs from 1:00 to 6:00, or *Auto*, which uses the style's own
default. ACE-Step accepts 10–600 seconds and Anthem clamps to that.

**Extra style** is appended to the preset, for things like
`female vocal, 140 BPM, no breakdown`.

## The video

- Background: any image or video. Video loops to the length of the song.
- Motion: slow zoom (Ken Burns), slow pan, or static.
- Visualizer: frequency bars, waveform, spectrum, or none.
- Output: 1920x1080, H.264 high, 48 kHz AAC, faststart — YouTube's own
  recommended delivery settings.

Each run gets its own folder under `output/`, so nothing overwrites.

## Before you publish

Each run writes a `_youtube.txt` with the things that matter:

1. **Set "Altered or synthetic content" to Yes** in YouTube's upload form.
   It is required for AI-generated music, and the line in the description
   does not count as doing it.
2. **Licence.** ACE-Step is MIT licensed and its model card permits
   commercial use of the output. If you bring your own mp3 from elsewhere,
   that file's licence is on you.
3. **Own your background.** Stock footage under the wrong licence is the
   most common source of a Content ID claim.

## Command line

```
python cli.py --lyrics song.txt --genre trance --length 210 --background art.jpg
python cli.py --list-styles
```

## Testing

```
python regression.py
```

Covers lyric structuring across every style, the YouTube metadata, the
ffmpeg graph in all twelve motion/visualizer combinations, a real render
probed for codec and duration, the full pipeline, and every error path. It
needs no GPU and no network, and it cleans up after itself.

## Layout

```
Anthem.cmd          double-click launcher
gui.py              the window
cli.py              command line
regression.py       the test suite
SETUP-LOCAL.md      getting ACE-Step running on your GPU
anthem/
  config.py         settings, paths, length choices
  theme.py          the dark theme
  lyrics.py         raw lyrics -> tagged sections
  styles.json       the genre presets
  http.py           tiny urllib JSON client
  providers/
    local_acestep.py  ACE-Step on this PC
    local_file.py     music you already have
  video.py          ffmpeg filter graph and render
  metadata.py       YouTube title, description, tags
  pipeline.py       ties it together
output/             one folder per run
assets/             backgrounds and starter lyrics
```

## Licence

MIT. ACE-Step is a separate project under its own MIT licence.
