# Running ACE-Step on your own machine

This is the point of the project: generate music here, on hardware you own,
with no account, no key and no metered API. The model is
[ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5), MIT licensed, and
its model card permits commercial use of the output — so tracks made this
way are yours to put on a monetised channel.

## What the hardware has to be

From the [official install guide](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/INSTALL.md):

| VRAM | What runs |
|---|---|
| 4 GB | Music model only, language model disabled |
| **6 GB** | **Music + language model — the realistic floor** |
| 8–16 GB | Larger DiT and LM, comfortable |
| 16–24 GB | XL models |
| 24 GB+ | Full XL + 4B LM |

Also: **~10 GB disk** for the models, **16 GB system RAM**, and
**Python 3.11 or 3.12** (not 3.13). NVIDIA/CUDA is the recommended path;
AMD ROCm, Intel XPU and Apple Silicon are supported, and CPU works but is
described by the project as "significantly slower".

Aim for **6 GB of VRAM or more**. Below that the language model is disabled
and lyric handling suffers.

## Install

```bash
git clone https://github.com/ace-step/ACE-Step-1.5
cd ACE-Step-1.5
```

Follow that repo's INSTALL guide for your GPU. On Windows with NVIDIA there
is a portable package that needs CUDA 12.8.

## Start the server

```bash
acestep-api
```

It listens on `http://localhost:8001` and loads the model into VRAM on first
use, which takes a minute or two. Leave the terminal open while you work.

Check it is up:

```bash
curl http://localhost:8001/health
```

You want `{"data":{"status":"ok"}, ...}`.

## Point Anthem at it

1. Open Anthem.
2. Set **Made by** to *ACE-Step on this PC*.
3. The header chip should turn green and read **ACE-Step running — fully
   offline**.

If it says *ACE-Step server not running*, the server isn't up or isn't on
`localhost:8001`. Change the address in **Settings → ACE-Step server** if
you started it elsewhere, or set `ACESTEP_URL` in your environment.

That's it. **Make my song** now generates the audio locally and renders the
video locally. Nothing is uploaded, nothing is counted, nothing expires.

## Notes

- **Length** maps to ACE-Step's `audio_duration`, which accepts 10–600
  seconds. Anthem clamps to that range.
- **Timeout**: generation on a modest GPU can take several minutes.
  Anthem waits 30 minutes by default; raise
  *Settings → Give up after (seconds)* if your card is slower.
- **Token**: only needed if you deliberately started the server with
  authentication enabled. Leave it empty otherwise.
- The server queues requests, so Anthem reports your queue position while
  it waits.

## Until you have the hardware

Set **Made by** to *Free — music I downloaded* and point Anthem at any mp3
you already own. It still shapes your lyrics, builds the 1080p video and
writes the YouTube title, description and tags. The **Copy style + lyrics**
button puts the arrangement on your clipboard for use anywhere.
