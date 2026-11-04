"""Anthem - desktop window.

Paste lyrics, pick a style, a length and a background. Press one button and
get a YouTube-ready MP4 with its title, description and tags beside it.

Tkinter on purpose: it ships with Python, idles around 35 MB, and opens
instantly on a machine where an Electron shell would not.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anthem import config, lyrics as lyrics_mod, pipeline  # noqa: E402
from anthem import providers, theme, video                 # noqa: E402

GAP = 10

BG_FILETYPES = [
    ("Image or video", "*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.mov *.mkv "
                       "*.avi *.webm *.m4v"),
    ("Images", "*.jpg *.jpeg *.png *.bmp *.webp"),
    ("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
    ("All files", "*.*"),
]
AUDIO_FILETYPES = [
    ("Audio", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus"),
    ("All files", "*.*"),
]

# Where to read about running the model locally. Documentation only -
# Anthem never sends your work anywhere.
ACESTEP_HELP = "https://github.com/ace-step/ACE-Step-1.5"


class AnthemApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anthem")
        self.minsize(1180, 600)
        self._fit_to_screen(1460, 780)

        self.settings = config.load()
        self.styles = config.styles()
        self.font = theme.apply(self)

        self.messages = queue.Queue()
        self.worker = None
        self.last_run_dir = ""

        self._build()
        self._pump()
        self._startup()

    # geometry() sizes the CLIENT area; Windows then draws a title bar and
    # borders outside it, and the taskbar eats the bottom of the screen.
    # Ignore either and the action bar ends up behind the taskbar, which is
    # what happens on this 1536x864 panel.
    TASKBAR_ALLOWANCE = 48
    FRAME_ALLOWANCE = 45
    TOP_MARGIN = 10

    def _fit_to_screen(self, want_w, want_h):
        """Size and place the window inside the usable desktop."""
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        max_h = (screen_h - self.TASKBAR_ALLOWANCE - self.FRAME_ALLOWANCE
                 - self.TOP_MARGIN * 2)
        width = min(want_w, screen_w - 60)
        height = min(want_h, max_h)
        x = max((screen_w - width) // 2, 0)
        self.geometry("%dx%d+%d+%d" % (width, height, x, self.TOP_MARGIN))

    # ------------------------------------------------------------------
    # layout

    def _build(self):
        self.columnconfigure(0, weight=1)
        # The body takes most of the slack; the log keeps a readable floor
        # but never squeezes the sidebar cards off the bottom.
        self.rowconfigure(1, weight=5)
        self.rowconfigure(2, weight=1)

        self._build_header()

        body = ttk.Frame(self, padding=(GAP, GAP, GAP, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3, uniform="col")
        body.columnconfigure(1, weight=2, uniform="col")
        body.columnconfigure(2, weight=2, uniform="col")
        body.rowconfigure(0, weight=1)

        self._build_lyrics(body)
        self._build_sidebar(body)
        self._build_progress()
        self._build_actions()

    def _build_header(self):
        outer = tk.Frame(self, bg=theme.BORDER)
        outer.grid(row=0, column=0, sticky="ew", padx=GAP, pady=(GAP, 0))
        bar = ttk.Frame(outer, style="Panel.TFrame", padding=(18, 14))
        bar.pack(fill="both", expand=True, padx=1, pady=1)
        bar.columnconfigure(1, weight=1)

        left = ttk.Frame(bar, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Anthem", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Lyrics to a YouTube-ready music video",
                  style="Subtitle.TLabel").pack(anchor="w")

        right = ttk.Frame(bar, style="Panel.TFrame")
        right.grid(row=0, column=2, sticky="e")
        self.chip = tk.Label(right, text="", bg=theme.PANEL,
                             fg=theme.MUTED, font=self.font["ui_bold"],
                             cursor="hand2")
        self.chip.pack(anchor="e")
        self.chip.bind("<Button-1>", lambda _e: self._open_settings())
        self.chip_hint = ttk.Label(right, text="", style="Muted.TLabel")
        self.chip_hint.pack(anchor="e")

    def _build_lyrics(self, parent):
        outer, inner = theme.card(parent, "Lyrics")
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, GAP // 2))
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(2, weight=1)

        self.hint = ttk.Label(
            inner, style="Muted.TLabel", wraplength=560, justify="left",
            text=("Leave a blank line between sections. Repeat a block and "
                  "it becomes the chorus. Tags like [Verse] are added to fit "
                  "the style - write your own and they are kept."))
        self.hint.grid(row=0, column=0, sticky="w", pady=(0, 10))

        wrap = tk.Frame(inner, bg=theme.BORDER)
        wrap.grid(row=2, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)

        # Small natural height so the box shrinks before the sidebar does;
        # its row weight lets it take every spare pixel.
        self.lyrics_text = tk.Text(wrap, height=6, undo=True)
        theme.style_text(self.lyrics_text, self.font["lyrics"])
        self.lyrics_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(wrap, orient="vertical",
                               command=self.lyrics_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.lyrics_text.configure(yscrollcommand=scroll.set)
        self.lyrics_text.bind("<KeyRelease>", self._on_lyrics_change)

        foot = ttk.Frame(inner, style="Panel.TFrame")
        foot.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        foot.columnconfigure(1, weight=1)
        self.count_label = ttk.Label(foot, text="0 words",
                                     style="Muted.TLabel")
        self.count_label.grid(row=0, column=0, sticky="w")
        ttk.Button(foot, text="Load example",
                   command=self._load_example).grid(row=0, column=2)
        ttk.Button(foot, text="Clear",
                   command=self._clear_lyrics).grid(row=0, column=3,
                                                    padx=(6, 0))

    def _build_sidebar(self, parent):
        """Two short columns rather than one tall stack.

        This runs on a 1536x864 screen with 816px of usable height, so
        width is the resource there is plenty of and height is not.
        """
        mid = ttk.Frame(parent)
        mid.grid(row=0, column=1, sticky="nsew", padx=GAP // 2)
        mid.columnconfigure(0, weight=1)
        self._build_song_card(mid)

        right = ttk.Frame(parent)
        right.grid(row=0, column=2, sticky="nsew", padx=(GAP // 2, 0))
        right.columnconfigure(0, weight=1)
        self._build_sound_card(right)
        self._build_picture_card(right)

    def _build_song_card(self, parent):
        outer, box = theme.card(parent, "Song")
        outer.grid(row=0, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)

        ttk.Label(box, text="Title", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", pady=4)
        self.title_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.title_var).grid(
            row=0, column=1, sticky="ew", padx=(10, 0), pady=4)

        ttk.Label(box, text="Style", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=4)
        self.genre_keys = sorted(self.styles,
                                 key=lambda k: self.styles[k]["label"])
        self.genre_box = ttk.Combobox(
            box, state="readonly",
            values=[self.styles[k]["label"] for k in self.genre_keys])
        self.genre_box.current(self.genre_keys.index("trance")
                               if "trance" in self.genre_keys else 0)
        self.genre_box.grid(row=1, column=1, sticky="ew", padx=(10, 0),
                            pady=4)
        self.genre_box.bind("<<ComboboxSelected>>", self._on_genre)

        ttk.Label(box, text="Length", style="Panel.TLabel").grid(
            row=2, column=0, sticky="w", pady=4)
        self.length_values = [s for s, _ in config.LENGTH_CHOICES]
        self.length_box = ttk.Combobox(
            box, state="readonly",
            values=[label for _, label in config.LENGTH_CHOICES])
        saved = int(self.settings.get("song_length", 0) or 0)
        self.length_box.current(self.length_values.index(saved)
                                if saved in self.length_values else 0)
        self.length_box.grid(row=2, column=1, sticky="ew", padx=(10, 0),
                             pady=4)
        self.length_box.bind("<<ComboboxSelected>>", self._on_lyrics_change)

        self.instrumental_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Instrumental (no vocals)",
                        variable=self.instrumental_var,
                        command=self._on_instrumental).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.style_note = ttk.Label(box, style="Muted.TLabel",
                                    wraplength=330, justify="left")
        self.style_note.grid(row=4, column=0, columnspan=2, sticky="w",
                             pady=(10, 0))

    def _build_sound_card(self, parent):
        outer, box = theme.card(parent, "Sound")
        outer.grid(row=0, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)

        ttk.Label(box, text="Made by", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", pady=4)
        self.provider_keys = [k for k, _ in providers.labels()]
        self.provider_box = ttk.Combobox(
            box, state="readonly",
            values=[lab for _, lab in providers.labels()])
        current = self.settings.get("provider", "file")
        self.provider_box.current(
            self.provider_keys.index(current)
            if current in self.provider_keys else 0)
        self.provider_box.grid(row=0, column=1, sticky="ew", padx=(10, 0),
                               pady=4)
        self.provider_box.bind("<<ComboboxSelected>>", self._on_provider)

        ttk.Label(box, text="Extra style", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=4)
        self.extra_var = tk.StringVar()
        self.extra_entry = ttk.Entry(box, textvariable=self.extra_var)
        self.extra_entry.grid(row=1, column=1, sticky="ew",
                              padx=(10, 0), pady=4)
        _placeholder(self.extra_entry, self.extra_var,
                     "female vocal, 140 BPM, no breakdown")

        # Shown only for the "music I already have" backend.
        self.source_row = ttk.Frame(box, style="Panel.TFrame")
        self.source_row.columnconfigure(0, weight=1)

        ttk.Button(self.source_row, text="Copy style + lyrics",
                   command=self._copy_for_generator).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(self.source_row, text="Your music file",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2,
                                             sticky="w", pady=(0, 4))
        self.source_var = tk.StringVar()
        ttk.Entry(self.source_row, textvariable=self.source_var).grid(
            row=2, column=0, sticky="ew")
        ttk.Button(self.source_row, text="Choose...",
                   command=self._pick_audio).grid(row=2, column=1,
                                                  padx=(6, 0))

        ttk.Label(self.source_row, text="3. The file you downloaded",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2,
                                             sticky="w", pady=(0, 4))
        self.source_var = tk.StringVar()
        ttk.Entry(self.source_row, textvariable=self.source_var).grid(
            row=2, column=0, sticky="ew")
        ttk.Button(self.source_row, text="Choose...",
                   command=self._pick_audio).grid(row=2, column=1,
                                                  padx=(6, 0))

    def _build_picture_card(self, parent):
        outer, box = theme.card(parent, "Picture")
        outer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        box.columnconfigure(0, weight=1)

        row = ttk.Frame(box, style="Panel.TFrame")
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.bg_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.bg_var).grid(row=0, column=0,
                                                      sticky="ew")
        ttk.Button(row, text="Choose...",
                   command=self._pick_background).grid(row=0, column=1,
                                                       padx=(6, 0))

        grid = ttk.Frame(box, style="Panel.TFrame")
        grid.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        grid.columnconfigure(1, weight=1)

        ttk.Label(grid, text="Visualizer", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", pady=4)
        self.vis_keys = list(video.VISUALIZERS)
        self.vis_box = ttk.Combobox(
            grid, state="readonly",
            values=[video.VISUALIZERS[k] for k in self.vis_keys])
        saved = self.settings.get("visualizer", "bars")
        self.vis_box.current(self.vis_keys.index(saved)
                             if saved in self.vis_keys else 0)
        self.vis_box.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)

        ttk.Label(grid, text="Motion", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=4)
        self.motion_keys = list(video.MOTIONS)
        self.motion_box = ttk.Combobox(
            grid, state="readonly",
            values=[video.MOTIONS[k] for k in self.motion_keys])
        saved = self.settings.get("video_motion", "kenburns")
        self.motion_box.current(self.motion_keys.index(saved)
                                if saved in self.motion_keys else 0)
        self.motion_box.grid(row=1, column=1, sticky="ew", padx=(10, 0),
                             pady=4)


    def _build_progress(self):
        outer, box = theme.card(self, "Progress")
        outer.grid(row=2, column=0, sticky="nsew", padx=GAP, pady=(GAP, 0))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        wrap = tk.Frame(box, bg=theme.BORDER)
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)

        self.log = tk.Text(wrap, height=4, state="disabled")
        theme.style_text(self.log, self.font["mono"])
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

        self.log.tag_configure("ok", foreground=theme.OK)
        self.log.tag_configure("warn", foreground=theme.WARN)
        self.log.tag_configure("bad", foreground=theme.BAD)
        self.log.tag_configure("muted", foreground=theme.MUTED)
        self.log.tag_configure("path", foreground=theme.ACCENT_HI)

    def _build_actions(self):
        self.progress = ttk.Progressbar(
            self, style="Thin.Horizontal.TProgressbar", mode="indeterminate")
        self.progress.grid(row=3, column=0, sticky="ew", padx=GAP,
                           pady=(GAP, 0))
        # An idle indeterminate bar parks a stray block at the left edge,
        # so it only exists while something is actually running.
        self.progress.grid_remove()

        bar = ttk.Frame(self, padding=(GAP, 10, GAP, GAP))
        bar.grid(row=4, column=0, sticky="ew")
        bar.columnconfigure(2, weight=1)

        self.go_btn = ttk.Button(bar, text="Make my song",
                                 style="Accent.TButton", command=self._start)
        self.go_btn.grid(row=0, column=0)

        self.video_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Render the video", style="Bg.TCheckbutton",
                        variable=self.video_var).grid(row=0, column=1,
                                                      padx=(GAP, 0))

        self.status = ttk.Label(bar, text="Ready.", style="Status.TLabel")
        self.status.grid(row=0, column=2, sticky="w", padx=GAP)

        self.open_btn = ttk.Button(bar, text="Open output folder",
                                   command=self._open_folder,
                                   state="disabled")
        self.open_btn.grid(row=0, column=3, padx=(0, 6))
        ttk.Button(bar, text="Settings",
                   command=self._open_settings).grid(row=0, column=4)

    # ------------------------------------------------------------------
    # reactions

    def _genre_key(self):
        index = self.genre_box.current()
        return self.genre_keys[index if index >= 0 else 0]

    def _provider_key(self):
        index = self.provider_box.current()
        return self.provider_keys[index if index >= 0 else 0]

    def _length_seconds(self):
        index = self.length_box.current()
        return self.length_values[index if index >= 0 else 0]

    def _on_genre(self, _event=None):
        style = self.styles[self._genre_key()]
        blurb = style["prompt"]
        if len(blurb) > 108:
            blurb = blurb[:105].rsplit(",", 1)[0] + "..."
        self.style_note.configure(
            text="%s BPM - %s" % (style.get("bpm", "?"), blurb))
        self._on_lyrics_change()

    def _on_instrumental(self):
        singing = not self.instrumental_var.get()
        self.lyrics_text.configure(
            state="normal" if singing else "disabled",
            fg=theme.TEXT if singing else theme.MUTED)
        self._on_lyrics_change()

    def _on_provider(self, _event=None):
        if self._provider_key() == "file":
            self.source_row.grid(row=3, column=0, columnspan=2,
                                 sticky="ew", pady=(10, 0))
        else:
            self.source_row.grid_remove()
        self._refresh_chip()

    def _on_lyrics_change(self, _event=None):
        raw = self.lyrics_text.get("1.0", "end")
        words = len(raw.split())
        blocks = len(lyrics_mod.split_blocks(raw))
        seconds = self._length_seconds()
        if not seconds:
            seconds = self.styles[self._genre_key()].get("default_length", 200)
            suffix = " (style default)"
        else:
            suffix = ""
        self.count_label.configure(
            text="%d word%s - %d block%s - target %d:%02d%s"
                 % (words, "" if words == 1 else "s",
                    blocks, "" if blocks == 1 else "s",
                    seconds // 60, seconds % 60, suffix))

    def _load_example(self):
        path = os.path.join(config.ASSETS_DIR, "example_lyrics.txt")
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.insert("1.0", text)
        self.instrumental_var.set(False)
        self._on_instrumental()

    def _clear_lyrics(self):
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self._on_instrumental()

    def _pick_background(self):
        path = filedialog.askopenfilename(
            title="Pick the image or video behind your song",
            initialdir=_first_dir(os.path.join(config.ASSETS_DIR,
                                               "backgrounds"),
                                  config.ASSETS_DIR),
            filetypes=BG_FILETYPES)
        if path:
            self.bg_var.set(path)

    def _copy_for_generator(self):
        """Put the style prompt and tagged lyrics on the clipboard.

        Useful when something other than Anthem renders the audio: the
        arrangement still comes from here, and a flat wall of lyrics is
        what makes a generated track wander, whoever sings it.
        """
        style = self.styles[self._genre_key()]
        prompt = pipeline.style_prompt_for(
            self._genre_key(), self.styles,
            _value(self.extra_entry, self.extra_var))

        parts = ["STYLE / TAGS", prompt, ""]
        if not self.instrumental_var.get():
            raw = self.lyrics_text.get("1.0", "end").strip()
            if raw:
                parts += ["LYRICS",
                          lyrics_mod.structure(raw, style["structure"]), ""]
        seconds = self._length_seconds() or style.get("default_length", 200)
        parts.append("LENGTH  %d:%02d" % (seconds // 60, seconds % 60))

        text = "\n".join(parts)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # make it survive this window closing
        self._say("Copied the style and lyrics, ready to paste.", "ok")

    def _pick_audio(self):
        # The generator hands the file to the browser, so Downloads is
        # where it will be - open there rather than in the app folder.
        path = filedialog.askopenfilename(
            title="Pick the song you downloaded",
            initialdir=_first_dir(
                os.path.join(os.path.expanduser("~"), "Downloads"),
                config.ASSETS_DIR),
            filetypes=AUDIO_FILETYPES)
        if path:
            self.source_var.set(path)

    def _open_folder(self):
        target = self.last_run_dir or config.OUTPUT_DIR
        if not os.path.isdir(target):
            return
        if sys.platform == "win32":
            os.startfile(target)  # noqa: S606 - the user asked to see it
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])

    # ------------------------------------------------------------------
    # backend status chip

    def _refresh_chip(self):
        key = self._provider_key()
        backend = providers.get(key, self.settings)
        label = dict(providers.labels())[key]
        if key == "file":
            self.chip.configure(text="  Ready - no account needed",
                                fg=theme.OK)
            self.chip_hint.configure(text="Free forever")
        elif backend.configured():
            self.chip.configure(text="  ACE-Step running - fully offline",
                                fg=theme.OK)
            self.chip_hint.configure(text="Nothing leaves this PC")
        else:
            # Nothing here is ever gated on a key. The only thing that can
            # be missing is the local server.
            self.chip.configure(text="  ACE-Step server not running",
                                fg=theme.WARN)
            self.chip_hint.configure(text="See SETUP-LOCAL.md")

    # ------------------------------------------------------------------
    # running

    def _start(self):
        if self.worker and self.worker.is_alive():
            return

        job = pipeline.Job(
            lyrics=self.lyrics_text.get("1.0", "end").strip(),
            genre=self._genre_key(),
            title=self.title_var.get().strip(),
            background=self.bg_var.get().strip().strip('"'),
            instrumental=self.instrumental_var.get(),
            length_seconds=self._length_seconds(),
            extra_style=_value(self.extra_entry, self.extra_var),
            source_audio=self.source_var.get().strip(),
            make_video=self.video_var.get(),
        )

        if not job.instrumental and not job.lyrics:
            messagebox.showinfo(
                "Nothing to sing",
                "Write some lyrics, press Load example, or tick "
                "Instrumental.")
            return
        if job.make_video and not job.background:
            if not messagebox.askyesno(
                    "No background",
                    "No image or video chosen. Render on a plain dark "
                    "background instead?"):
                return

        self.settings = config.load()
        self.settings["provider"] = self._provider_key()
        self.settings["visualizer"] = _key_for(
            video.VISUALIZERS, self.vis_box.get(), "bars")
        self.settings["video_motion"] = _key_for(
            video.MOTIONS, self.motion_box.get(), "kenburns")

        # Remember the length choice for next launch.
        saved = config.load()
        saved["song_length"] = job.length_seconds
        config.save(saved)

        self.go_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.status.configure(text="Working...", style="Status.TLabel")
        self.progress.grid()
        self.progress.start(14)
        self._clear_log()

        self.worker = threading.Thread(target=self._work, args=(job,),
                                       daemon=True)
        self.worker.start()

    def _work(self, job):
        try:
            result = pipeline.run(
                job, self.settings,
                progress=lambda m: self.messages.put(("log", m)))
            self.messages.put(("done", result))
        except Exception as exc:  # shown in the window, never a traceback
            self.messages.put(("error", str(exc)))

    def _pump(self):
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "log":
                    self._say(payload)
                elif kind == "done":
                    self._finished(payload)
                elif kind == "error":
                    self._failed(payload)
        except queue.Empty:
            pass
        self.after(150, self._pump)

    def _finished(self, result):
        self.last_run_dir = result.run_dir
        self.progress.stop()
        self.progress.grid_remove()
        self.go_btn.configure(state="normal")
        self.open_btn.configure(state="normal")
        self.status.configure(text="Finished in %d seconds."
                                   % result.seconds, style="Good.TLabel")
        self._say("")
        for path in result.videos:
            self._say("video   %s" % path, "path")
        for track in result.tracks:
            self._say("audio   %s" % track.audio_path, "path")
        for path in result.notes_files:
            self._say("upload  %s" % path, "path")
        self._say("")
        self._say("Open the _youtube.txt for the title, description and "
                  "tags, and remember to set 'Altered or synthetic "
                  "content' to Yes when you upload.", "muted")

    def _failed(self, message):
        self.progress.stop()
        self.progress.grid_remove()
        self.go_btn.configure(state="normal")
        self.status.configure(text="Stopped.", style="Bad.TLabel")
        self._say("")
        self._say(message, "bad")

    # ------------------------------------------------------------------
    # log

    def _say(self, message, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _startup(self):
        self._on_genre()
        self._on_provider()
        self._on_lyrics_change()

        if not video.have_ffmpeg():
            self._say("ffmpeg is not on PATH. Audio will still generate, "
                      "but no video can be rendered.", "warn")

        key = self._provider_key()
        backend = providers.get(key, self.settings)

        if key == "file":
            self._say("Ready. No account, no key, nothing to pay.", "ok")
            self._say("")
            self._say("Pick the music file you already have, choose a "
                      "background, and press Make my song.")
            self._say("")
            self._say("To generate the music here instead, switch 'Made by' "
                      "to ACE-Step and start its server - see "
                      "SETUP-LOCAL.md.", "muted")
            return

        if backend.configured():
            self._say("Ready. ACE-Step is running on this PC - everything "
                      "stays offline.", "ok")
            return

        self._say(backend.missing_message(), "warn")
        self._say("")
        self._say("Setup guide: SETUP-LOCAL.md   Model: %s"
                  % ACESTEP_HELP, "path")
        self._say("Meanwhile, switch 'Made by' to \"Free - music I "
                  "downloaded\" to build videos from a file you already "
                  "have.", "muted")

    # ------------------------------------------------------------------

    def _open_settings(self):
        SettingsWindow(self)


class SettingsWindow(tk.Toplevel):
    GROUPS = [
        ("ACE-Step server  -  runs on this PC", [
            ("acestep_url", "Server address", False),
            ("acestep_token", "Token (only if you set one)", True),
            ("poll_timeout_seconds", "Give up after (seconds)", False),
        ]),
        ("Video", [
            ("video_resolution", "Size (e.g. 1920x1080)", False),
            ("video_fps", "Frames per second", False),
            ("visualizer_color", "Visualizer colour (#RRGGBB)", False),
            ("audio_bitrate", "Audio bitrate", False),
        ]),
        ("Channel", [
            ("channel_name", "Your channel name", False),
        ]),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.font = parent.font
        self.title("Anthem settings")
        self.configure(bg=theme.BG)
        self.transient(parent)
        self.resizable(False, False)

        data = config.load()
        self.vars = []

        head = ttk.Frame(self, padding=(GAP, GAP, GAP, 0))
        head.pack(fill="x")
        ttk.Label(head, text="Settings", style="TLabel",
                  font=self.font["ui_bold"]).pack(anchor="w")
        ttk.Label(head,
                  text=("Saved to settings.json in the Anthem folder. "
                        "That file holds your keys - do not share it."),
                  style="MutedBg.TLabel").pack(anchor="w", pady=(2, 0))

        for group, fields in self.GROUPS:
            outer, box = theme.card(self, group)
            outer.pack(fill="x", padx=GAP, pady=(GAP, 0))
            box.columnconfigure(1, weight=1)
            for row, (key, label, secret) in enumerate(fields):
                ttk.Label(box, text=label, style="Panel.TLabel").grid(
                    row=row, column=0, sticky="w", pady=4)
                var = tk.StringVar(value=str(data.get(key, "")))
                entry = ttk.Entry(box, textvariable=var, width=46,
                                  show="*" if secret else "")
                entry.grid(row=row, column=1, sticky="ew", padx=(10, 0),
                           pady=4)
                self.vars.append((key, label, var))
                if secret:
                    ttk.Button(
                        box, text="Show",
                        command=lambda e=entry: e.configure(show="")).grid(
                        row=row, column=2, padx=(6, 0))
            if group.startswith("ACE-Step"):
                link = tk.Label(box, text="How to run ACE-Step locally",
                                bg=theme.PANEL, fg=theme.ACCENT_HI,
                                font=self.font["small"], cursor="hand2")
                link.grid(row=len(fields), column=1, sticky="w",
                          padx=(10, 0), pady=(6, 0))
                link.bind("<Button-1>",
                          lambda _e: webbrowser.open(ACESTEP_HELP))

        bar = ttk.Frame(self, padding=GAP)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(
            side="right", padx=(0, 8))

        self.update_idletasks()
        self.grab_set()

    def _save(self):
        data = config.load()
        for key, label, var in self.vars:
            value = var.get().strip()
            if key in ("video_fps", "poll_timeout_seconds"):
                try:
                    value = int(value or 30)
                except ValueError:
                    messagebox.showerror(
                        "Anthem", "%s must be a number." % label)
                    return
            data[key] = value
        path = config.save(data)
        self.parent.settings = config.load()
        self.parent._refresh_chip()
        self.parent._say("Settings saved to %s" % path, "ok")
        self.destroy()


def _first_dir(*candidates):
    """The first of these folders that exists, for a file dialog."""
    for path in candidates:
        if path and os.path.isdir(path):
            return path
    return os.path.expanduser("~")


def _placeholder(entry, var, text):
    """Grey example text inside an empty entry.

    The hint lives in the variable while it shows, so anything reading the
    field must go through _value() or it will treat the example as input.
    """
    entry._ph_on = False

    def show():
        if not var.get():
            entry._ph_on = True
            var.set(text)
            entry.configure(foreground=theme.MUTED)

    def clear(_event=None):
        if entry._ph_on:
            entry._ph_on = False
            var.set("")
        entry.configure(foreground=theme.TEXT)

    def restore(_event=None):
        if not var.get():
            show()

    entry.bind("<FocusIn>", clear)
    entry.bind("<FocusOut>", restore)
    show()


def _value(entry, var):
    """An entry's real content - never the placeholder text."""
    return "" if getattr(entry, "_ph_on", False) else var.get().strip()


def _key_for(mapping, label, fallback):
    """Turn a human label from a combobox back into its settings key."""
    for key, text in mapping.items():
        if text == label:
            return key
    return fallback


def main():
    config.ensure_dirs()
    AnthemApp().mainloop()


if __name__ == "__main__":
    main()
