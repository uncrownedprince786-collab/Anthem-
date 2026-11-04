"""Anthem from the command line.

The window is the main way in; this exists for batches - a folder of lyric
files turned into videos overnight, which is tedious to click through.

    python cli.py --lyrics song.txt --genre trance --background art.jpg
    python cli.py --list-styles
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anthem import config, pipeline, providers, video  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="anthem",
        description="Turn lyrics into a YouTube-ready music video.")
    parser.add_argument("--lyrics", help="path to a .txt file of lyrics")
    parser.add_argument("--text", help="lyrics inline instead of a file")
    parser.add_argument("--genre", default="trance",
                        help="style key, see --list-styles")
    parser.add_argument("--title", default="", help="song title")
    parser.add_argument("--background", default="",
                        help="image or video behind the song")
    parser.add_argument("--provider", default="",
                        help="acestep (local) or file")
    parser.add_argument("--audio", default="",
                        help="existing audio file (with --provider file)")
    parser.add_argument("--extra", default="",
                        help="extra style words, e.g. 'female vocal, 140 BPM'")
    parser.add_argument("--length", type=int, default=0,
                        help="target length in seconds")
    parser.add_argument("--instrumental", action="store_true",
                        help="no vocals")
    parser.add_argument("--no-video", action="store_true",
                        help="audio and notes only")
    parser.add_argument("--list-styles", action="store_true")
    args = parser.parse_args(argv)

    styles = config.styles()

    if args.list_styles:
        width = max(len(k) for k in styles)
        for key in sorted(styles):
            style = styles[key]
            print("%-*s  %-26s %s BPM"
                  % (width, key, style["label"], style.get("bpm", "?")))
        return 0

    text = args.text or ""
    if args.lyrics:
        if not os.path.isfile(args.lyrics):
            parser.error("no lyrics file at %s" % args.lyrics)
        with open(args.lyrics, "r", encoding="utf-8") as fh:
            text = fh.read()

    if not text.strip() and not args.instrumental:
        parser.error("give --lyrics, --text, or --instrumental")

    settings = config.load()
    if args.provider:
        settings["provider"] = args.provider

    if not video.have_ffmpeg() and not args.no_video:
        print("ffmpeg is not on PATH - rendering audio only.")
        args.no_video = True

    job = pipeline.Job(
        lyrics=text,
        genre=args.genre,
        title=args.title,
        background=args.background,
        instrumental=args.instrumental,
        length_seconds=args.length,
        extra_style=args.extra,
        source_audio=args.audio,
        make_video=not args.no_video,
    )

    try:
        result = pipeline.run(job, settings, progress=_say)
    except (providers.ProviderError, video.VideoError) as exc:
        print("\nStopped: %s" % exc)
        return 1

    print("\nFinished in %d seconds." % result.seconds)
    for path in result.videos:
        print("  video : %s" % path)
    for track in result.tracks:
        print("  audio : %s" % track.audio_path)
    for path in result.notes_files:
        print("  upload: %s" % path)
    return 0


def _say(message):
    print("  %s" % message, flush=True)


if __name__ == "__main__":
    sys.exit(main())
