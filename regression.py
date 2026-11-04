"""Regression test for Anthem.

Covers the parts that break quietly: lyric structuring across every style,
the length setting reaching the backend, the ffmpeg graph actually
producing a valid file, and each error path returning a sentence a human
can act on rather than a traceback.

    python regression.py

Needs no API keys and spends nothing - the generation step is exercised
through the local-file backend.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anthem import (config, lyrics as lyrics_mod, metadata,  # noqa: E402
                    pipeline, providers, theme, video)

PASS, FAIL = [], []
WORK = None

SAMPLE = """We rise above the city lights
Chasing something we can't name

Feel the fire, feel it burn
Hold the night and never turn

Feel the fire, feel it burn
Hold the night and never turn"""


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print("  pass  %s" % name)
    else:
        FAIL.append((name, detail))
        print("  FAIL  %s %s" % (name, ("- " + detail) if detail else ""))


def section(title):
    print("\n%s" % title)
    print("-" * len(title))


# ----------------------------------------------------------------------


def test_lyrics():
    section("Lyrics structuring")
    styles = config.styles()

    for key in sorted(styles):
        pattern = styles[key]["structure"]
        out = lyrics_mod.structure(SAMPLE, pattern)
        tags = [l for l in out.splitlines() if lyrics_mod.TAG_RE.match(l)]
        check("%s: one tag per section" % key,
              len(tags) == len(pattern),
              "%d tags for %d sections" % (len(tags), len(pattern)))

        sung = [s for s in pattern
                if s.lower() not in lyrics_mod.INSTRUMENTAL]
        if sung:
            check("%s: vocal sections carry words" % key,
                  "Feel the fire" in out or "We rise above" in out)

    # The repeated block must land in the chorus, not a verse.
    trance = lyrics_mod.structure(SAMPLE, styles["trance"]["structure"])
    chorus_body = trance.split("[Chorus]")[1].strip().splitlines()[0]
    check("repeated block becomes the chorus",
          chorus_body.startswith("Feel the fire"), chorus_body)

    # Hand-written tags survive untouched.
    authored = "[Verse]\nmy own words\n\n[Drop]"
    check("existing tags are preserved",
          lyrics_mod.structure(authored, styles["club"]["structure"])
          == authored)

    check("empty lyrics give empty output",
          lyrics_mod.structure("", styles["trance"]["structure"]) == "")
    check("single block still works",
          "only line" in lyrics_mod.structure(
              "only line", styles["smooth"]["structure"]))
    check("title comes off the first strong line",
          lyrics_mod.suggest_title(SAMPLE) == "We Rise Above The City Lights",
          lyrics_mod.suggest_title(SAMPLE))
    check("word count ignores tags",
          lyrics_mod.word_count("[Verse]\none two three") == 3)


def test_metadata():
    section("YouTube metadata")
    styles = config.styles()

    title = metadata.build_title("Night Drive", "trance", styles)
    check("title carries the style", "Uplifting Trance" in title, title)
    check("title stays under 100 chars",
          len(metadata.build_title("x" * 200, "trance", styles)) <= 100)

    desc = metadata.build_description(
        "Night Drive", "trance", styles, lyrics=SAMPLE,
        channel_name="Test Channel")
    check("description states the disclosure",
          "Altered or synthetic content" in desc)
    check("description includes the lyrics", "Feel the fire" in desc)
    check("description drops section tags", "[Chorus]" not in desc)
    check("description names the channel", "Test Channel" in desc)
    check("description stays under 5000",
          len(metadata.build_description("t", "trance", styles,
                                         lyrics="word " * 4000)) <= 5000)

    tags = metadata.tags_for("trance", "Night Drive")
    check("tags include the genre", "trance" in tags)
    check("tags have no duplicates", len(tags) == len(set(tags)))
    check("tag field stays under 500 chars",
          len(", ".join(metadata.tags_for("trance", "x " * 200))) <= 500)

    check("slug strips punctuation",
          metadata.slug("Hello: World!") == "Hello_World")
    check("slug never returns empty", metadata.slug("***") == "track")


def test_config():
    section("Settings")
    data = config.load()
    check("the free backend is the default",
          data["provider"] == "file", data["provider"])
    check("the default backend needs no key",
          providers.get(data["provider"], data).configured())
    check("only local backends are registered",
          set(providers.ORDER) == {"acestep", "file"}, str(providers.ORDER))
    check("no paid-API settings remain",
          not any("suno" in k or "replicate" in k for k in config.DEFAULTS))
    check("local server address is configured",
          data["acestep_url"].startswith("http://localhost"))
    check("length default is auto", int(data.get("song_length", -1)) == 0)
    check("every length choice is unique",
          len({s for s, _ in config.LENGTH_CHOICES})
          == len(config.LENGTH_CHOICES))
    check("auto is the first length choice",
          config.LENGTH_CHOICES[0][0] == 0)

    backup = None
    if os.path.exists(config.SETTINGS_PATH):
        backup = config.SETTINGS_PATH + ".bak"
        shutil.copyfile(config.SETTINGS_PATH, backup)
    try:
        data["song_length"] = 240
        data["channel_name"] = "Round Trip"
        config.save(data)
        again = config.load()
        check("settings round-trip", again["song_length"] == 240
              and again["channel_name"] == "Round Trip")
        saved_keys = set(__import__("json").load(
            open(config.SETTINGS_PATH, encoding="utf-8")))
        check("private keys are not written to disk",
              not any(k.startswith("_") for k in saved_keys))
    finally:
        if backup:
            shutil.move(backup, config.SETTINGS_PATH)
        elif os.path.exists(config.SETTINGS_PATH):
            os.remove(config.SETTINGS_PATH)


def test_styles():
    section("Style presets")
    styles = config.styles()
    check("eight styles ship", len(styles) == 8, str(len(styles)))
    for key, style in sorted(styles.items()):
        missing = [f for f in ("label", "prompt", "bpm", "structure",
                               "default_length") if f not in style]
        check("%s: complete preset" % key, not missing, str(missing))
        sung = [s for s in style["structure"]
                if s.lower() not in lyrics_mod.INSTRUMENTAL]
        check("%s: has somewhere to sing" % key, bool(sung))


def test_video_graph():
    section("Video filter graph")
    settings = config.load()

    for motion in video.MOTIONS:
        for vis in video.VISUALIZERS:
            s = dict(settings, video_motion=motion, visualizer=vis)
            cmd = video.build_command("a.mp3", "b.jpg", "o.mp4", s,
                                      title_text="T", seconds=10)
            graph = cmd[cmd.index("-filter_complex") + 1]
            check("graph builds: %s + %s" % (motion, vis),
                  graph.endswith("[v]") and "[1:v]" in graph)

    cmd = video.build_command("a.mp3", "", "o.mp4", settings, seconds=10)
    check("no background falls back to a colour source",
          "lavfi" in cmd and "color=" in " ".join(cmd))

    s = dict(settings, visualizer="bars", visualizer_color="#FF0000")
    graph = video.build_command("a.mp3", "b.jpg", "o.mp4", s,
                                seconds=10)[
        video.build_command("a.mp3", "b.jpg", "o.mp4", s,
                            seconds=10).index("-filter_complex") + 1]
    check("stereo gets a colour per channel",
          "0xFF0000|0xFF0000" in graph)

    check("odd sizes are rounded for yuv420p",
          video._resolution({"video_resolution": "1921x1081"}) == (1920, 1080))
    check("bad size falls back to 1080p",
          video._resolution({"video_resolution": "nonsense"}) == (1920, 1080))
    check("drawtext escapes a colon",
          "\\:" in video._escape_drawtext("a: b"))
    check("image is detected", video.kind_of("x.JPG") == "image")
    check("video is detected", video.kind_of("x.MP4") == "video")
    check("junk is rejected", video.kind_of("x.txt") == "unknown")


def test_render():
    section("Real render")
    audio = os.path.join(WORK, "tone.mp3")
    image = os.path.join(WORK, "bg.jpg")
    _make_tone(audio, 6)
    _make_image(image)

    settings = config.load()
    out = os.path.join(WORK, "out.mp4")
    video.render(audio, image, out, settings, title_text="Regression")
    check("mp4 is produced", os.path.exists(out))

    probe = _probe(out)
    check("video is h264", "h264" in probe, probe[:120])
    check("audio is aac", "aac" in probe, probe[:120])
    check("frame size is 1920x1080",
          "width=1920" in probe and "height=1080" in probe)
    check("audio is 48 kHz", "sample_rate=48000" in probe)
    check("duration matches the audio",
          abs(video.duration_of(out) - 6.0) < 0.8,
          str(video.duration_of(out)))

    # A video background must loop rather than freeze or truncate.
    longer = os.path.join(WORK, "long.mp3")
    _make_tone(longer, 12)
    looped = os.path.join(WORK, "looped.mp4")
    video.render(longer, out, looped, settings)
    check("short background video loops to fit",
          abs(video.duration_of(looped) - 12.0) < 0.8,
          str(video.duration_of(looped)))


def test_pipeline():
    section("Pipeline end to end")
    audio = os.path.join(WORK, "tone.mp3")
    image = os.path.join(WORK, "bg.jpg")

    settings = dict(config.load(), provider="file")
    job = pipeline.Job(lyrics=SAMPLE, genre="trance", title="Reg Test",
                       background=image, source_audio=audio,
                       length_seconds=120)
    result = pipeline.run(job, settings, progress=lambda m: None)

    check("run folder is created", os.path.isdir(result.run_dir))
    check("one video", len(result.videos) == 1)
    check("one set of notes", len(result.notes_files) == 1)
    check("lyrics are saved beside it",
          os.path.exists(os.path.join(result.run_dir, "lyrics.txt")))

    with open(result.notes_files[0], encoding="utf-8") as fh:
        notes = fh.read()
    check("notes carry the title", "Reg Test" in notes)
    check("notes carry the disclosure",
          "Altered or synthetic content" in notes)
    check("notes point at the video", ".mp4" in notes)

    # A second run with the same title must not overwrite the first.
    second = pipeline.run(job, settings, progress=lambda m: None)
    check("repeat runs get their own folder",
          second.run_dir != result.run_dir)

    # Length must reach the request the backend receives.
    captured = {}

    class Spy(providers.Provider):
        name, label = "spy", "Spy"

        def configured(self):
            return True

        def generate(self, request, progress=None):
            captured["len"] = request.length_seconds
            captured["style"] = request.style_prompt
            captured["lyrics"] = request.lyrics
            return [providers.Track(title="x", audio_path=audio,
                                    provider="spy")]

    providers.REGISTRY["spy"] = Spy
    try:
        pipeline.run(
            pipeline.Job(lyrics=SAMPLE, genre="club", title="Spy",
                         length_seconds=240, make_video=False,
                         extra_style="female vocal"),
            dict(config.load(), provider="spy"), progress=lambda m: None)
        check("chosen length reaches the backend", captured["len"] == 240,
              str(captured.get("len")))
        check("extra style words are appended",
              captured["style"].endswith("female vocal"))
        check("backend receives tagged lyrics",
              "[Chorus]" in captured["lyrics"])

        pipeline.run(
            pipeline.Job(lyrics=SAMPLE, genre="club", title="Spy2",
                         length_seconds=0, make_video=False),
            dict(config.load(), provider="spy"), progress=lambda m: None)
        check("auto length uses the style default",
              captured["len"] == config.styles()["club"]["default_length"],
              str(captured.get("len")))
    finally:
        providers.REGISTRY.pop("spy", None)


def test_errors():
    section("Error paths")
    audio = os.path.join(WORK, "tone.mp3")
    settings = dict(config.load(), provider="file")

    def fails(name, job, settings_in, expect):
        try:
            pipeline.run(job, settings_in, progress=lambda m: None)
            check(name, False, "no error raised")
        except (providers.ProviderError, video.VideoError) as exc:
            check(name, expect.lower() in str(exc).lower(), str(exc)[:90])

    fails("unknown style is explained",
          pipeline.Job(lyrics=SAMPLE, genre="polka", source_audio=audio),
          settings, "unknown style")
    fails("missing lyrics are explained",
          pipeline.Job(lyrics="", genre="trance", source_audio=audio),
          settings, "no lyrics")
    fails("missing audio file is explained",
          pipeline.Job(lyrics=SAMPLE, genre="trance",
                       source_audio="nope.mp3"),
          settings, "no file at")
    fails("no audio chosen is explained",
          pipeline.Job(lyrics=SAMPLE, genre="trance", source_audio=""),
          settings, "pick the audio")
    fails("a stopped ACE-Step server is explained",
          pipeline.Job(lyrics=SAMPLE, genre="trance"),
          dict(config.load(), provider="acestep",
               acestep_url="http://localhost:9"), "not running")
    fails("unknown backend is explained",
          pipeline.Job(lyrics=SAMPLE, genre="trance"),
          dict(config.load(), provider="banana"), "unknown provider")

    before = set(os.listdir(config.OUTPUT_DIR))
    try:
        pipeline.run(pipeline.Job(lyrics=SAMPLE, genre="trance"),
                     dict(config.load(), provider="acestep",
                          acestep_url="http://localhost:9"),
                     progress=lambda m: None)
    except providers.ProviderError:
        pass
    check("a failed run leaves no empty folder",
          set(os.listdir(config.OUTPUT_DIR)) == before)

    try:
        video.render("nope.mp3", "", os.path.join(WORK, "x.mp4"),
                     config.load())
        check("missing audio is caught by the renderer", False)
    except video.VideoError as exc:
        check("missing audio is caught by the renderer",
              "no audio" in str(exc).lower(), str(exc)[:80])

    try:
        video.render(os.path.join(WORK, "tone.mp3"), "nope.jpg",
                     os.path.join(WORK, "x.mp4"), config.load())
        check("missing background is caught", False)
    except video.VideoError as exc:
        check("missing background is caught",
              "background" in str(exc).lower(), str(exc)[:80])


def test_theme():
    section("Theme")
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        font = theme.apply(root)
        check("fonts resolve", bool(font["ui"][0]))
        outer, content = theme.card(root, "Test")
        check("card returns a usable content frame",
              content.winfo_class() == "TFrame")
        label = tk.Label(content)
        label.grid(row=0, column=0)
        check("grid works inside a card", label.winfo_manager() == "grid")
        root.update_idletasks()
    finally:
        root.destroy()


def test_gui():
    section("Window")
    import gui as gui_mod
    app = gui_mod.AnthemApp()
    app.withdraw()
    try:
        app.update_idletasks()
        app.update()
        check("window builds", True)
        check("length dropdown is populated",
              len(app.length_values) == len(config.LENGTH_CHOICES))
        check("auto length selected by default",
              app._length_seconds() == 0)
        app.length_box.current(app.length_values.index(180))
        check("length choice reads back", app._length_seconds() == 180)

        app.provider_box.current(app.provider_keys.index("file"))
        app._on_provider()
        check("file backend reveals the audio picker",
              bool(app.source_row.winfo_manager()))
        app.provider_box.current(app.provider_keys.index("acestep"))
        app._on_provider()
        check("local generation hides the file picker",
              not app.source_row.winfo_manager())
        check("offline backend never asks for a key",
              "key" not in app.chip.cget("text").lower(),
              app.chip.cget("text"))

        app._load_example()
        check("example loads words",
              "word" in app.count_label.cget("text"))
        app.instrumental_var.set(True)
        app._on_instrumental()
        check("instrumental locks the lyrics box",
              str(app.lyrics_text.cget("state")) == "disabled")
        app.instrumental_var.set(False)
        app._on_instrumental()
        check("unticking unlocks it",
              str(app.lyrics_text.cget("state")) == "normal")

        for index in range(len(app.genre_keys)):
            app.genre_box.current(index)
            app._on_genre()
        check("every style selects cleanly", True)

        check("chip reports the backend state",
              any(word in app.chip.cget("text").lower()
                  for word in ("ready", "running")),
              app.chip.cget("text"))

        # The example text in "Extra style" must never reach the backend.
        check("placeholder is visible when empty",
              "female vocal" in app.extra_var.get(), app.extra_var.get())
        check("placeholder is not read as input",
              gui_mod._value(app.extra_entry, app.extra_var) == "",
              gui_mod._value(app.extra_entry, app.extra_var))
        app.extra_entry.event_generate("<FocusIn>")
        app.update()
        check("focus clears the placeholder", app.extra_var.get() == "")
        app.extra_var.set("real words")
        check("real input reads back",
              gui_mod._value(app.extra_entry, app.extra_var) == "real words")
        app.extra_var.set("")
        app.extra_entry.event_generate("<FocusOut>")
        app.update()
        check("placeholder returns when emptied",
              "female vocal" in app.extra_var.get()
              and gui_mod._value(app.extra_entry, app.extra_var) == "")

        # The free workflow must work with no account of any kind.
        app.provider_box.current(app.provider_keys.index("file"))
        app._on_provider()
        check("free backend is ready with no key",
              "no account needed" in app.chip.cget("text").lower(),
              app.chip.cget("text"))

        app._load_example()
        app._copy_for_generator()
        clip = app.clipboard_get()
        check("clipboard carries the style prompt", "STYLE / TAGS" in clip)
        check("clipboard carries tagged lyrics",
              "[Chorus]" in clip and "LYRICS" in clip)
        check("clipboard carries the length", "LENGTH" in clip)

        app.instrumental_var.set(True)
        app._on_instrumental()
        app._copy_for_generator()
        clip = app.clipboard_get()
        check("instrumental copies no lyrics", "LYRICS" not in clip)
        app.instrumental_var.set(False)
        app._on_instrumental()

        win = gui_mod.SettingsWindow(app)
        app.update_idletasks()
        app.update()
        check("settings window opens", len(win.vars) >= 7)
        check("settings expose only local options",
              all(not k.startswith(("suno_", "replicate_"))
                  for k, _, _ in win.vars))
        win.destroy()
    finally:
        app.destroy()


def test_cli():
    section("Command line")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    here = os.path.dirname(os.path.abspath(__file__))

    out = subprocess.run([sys.executable, "cli.py", "--list-styles"],
                         capture_output=True, text=True, cwd=here, env=env,
                         errors="replace")
    check("--list-styles works", out.returncode == 0 and "trance" in out.stdout)

    out = subprocess.run([sys.executable, "cli.py"], capture_output=True,
                         text=True, cwd=here, env=env, errors="replace")
    check("no input is rejected", out.returncode != 0)

    audio = os.path.join(WORK, "tone.mp3")
    lyric_file = os.path.join(WORK, "lyrics.txt")
    with open(lyric_file, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE)

    out = subprocess.run(
        [sys.executable, "cli.py", "--lyrics", lyric_file, "--genre",
         "smooth", "--title", "CLI Test", "--provider", "file",
         "--audio", audio, "--length", "120", "--no-video"],
        capture_output=True, text=True, cwd=here, env=env, errors="replace")
    check("full CLI run succeeds", out.returncode == 0,
          (out.stdout + out.stderr)[-200:])
    check("CLI reports its outputs", "upload" in out.stdout)


# ----------------------------------------------------------------------
# helpers


def _ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
                   + args, check=True, capture_output=True)


def _make_tone(path, seconds):
    _ffmpeg(["-f", "lavfi", "-i", "sine=f=110:d=%d" % seconds,
             "-f", "lavfi", "-i",
             "anoisesrc=d=%d:c=pink:a=0.1" % seconds,
             "-filter_complex",
             "[0:a][1:a]amix=inputs=2:duration=shortest,alimiter[a]",
             "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", path])


def _make_image(path):
    _ffmpeg(["-f", "lavfi", "-i",
             "gradients=s=1280x720:d=1:c0=0x0d1b3e:c1=0x8e2d5c",
             "-frames:v", "1", path])


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,width,height,sample_rate", "-of", "default",
         path], capture_output=True, text=True, errors="replace")
    return out.stdout


def main():
    global WORK
    if not video.have_ffmpeg():
        print("ffmpeg not found - cannot run the render tests.")
        return 2

    WORK = tempfile.mkdtemp(prefix="anthem_reg_")
    created = set()
    before = set(os.listdir(config.OUTPUT_DIR)) \
        if os.path.isdir(config.OUTPUT_DIR) else set()

    print("Anthem regression")
    print("scratch: %s" % WORK)

    for test in (test_lyrics, test_metadata, test_config, test_styles,
                 test_video_graph, test_render, test_pipeline, test_errors,
                 test_theme, test_gui, test_cli):
        try:
            test()
        except Exception:
            FAIL.append((test.__name__, "raised"))
            print("  FAIL  %s raised:" % test.__name__)
            traceback.print_exc()

    # Clean up anything the tests wrote into output/.
    if os.path.isdir(config.OUTPUT_DIR):
        created = set(os.listdir(config.OUTPUT_DIR)) - before
        for name in created:
            shutil.rmtree(os.path.join(config.OUTPUT_DIR, name),
                          ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)

    print("\n" + "=" * 56)
    print("%d passed, %d failed" % (len(PASS), len(FAIL)))
    if created:
        print("cleaned %d test run folder(s) from output/" % len(created))
    for name, detail in FAIL:
        print("  FAILED: %s %s" % (name, detail))
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
