"""ACE-Step running on this machine. No account, no key, no network.

ACE-Step 1.5 ships its own REST server. You start it once, it loads the
model onto your GPU, and Anthem talks to it over localhost. Nothing leaves
the computer and nothing is metered.

The model is MIT licensed and its model card permits commercial use of the
output, so tracks made this way are yours to monetise.

Protocol (ACE-Step 1.5 REST API, docs/en/API.md):
    GET  /health                  -> data.status == "ok"
    POST /release_task            -> data.task_id
    POST /query_result            -> status 0 queued/running, 1 done, 2 failed
    GET  /v1/audio?path=...       -> the finished audio file

Every response is wrapped as {data, code, error, timestamp, extra}.
"""

import json
import os
import time
import urllib.parse

from .. import http
from .base import Provider, ProviderError, Track

DEFAULT_BASE = "http://localhost:8001"

# ACE-Step caps a single render at ten minutes.
MIN_SECONDS = 10
MAX_SECONDS = 600


class LocalAceStepProvider(Provider):
    name = "acestep"
    label = "ACE-Step on this PC (free, offline)"

    def _base(self):
        return (self.settings.get("acestep_url")
                or DEFAULT_BASE).rstrip("/")

    def _headers(self):
        token = (self.settings.get("acestep_token") or "").strip()
        return {"Authorization": "Bearer %s" % token} if token else {}

    def configured(self):
        """True when the local server answers its health check."""
        try:
            info = http.get_json(self._base() + "/health",
                                 headers=self._headers(), timeout=4)
        except http.HttpError:
            return False
        return str((info.get("data") or {}).get("status", "")).lower() == "ok"

    def missing_message(self):
        return (
            "The ACE-Step server is not running at %s.\n\n"
            "Start it in a terminal, wait for it to load the model, then "
            "press Make my song again:\n"
            "    acestep-api\n\n"
            "Not installed yet? See SETUP-LOCAL.md in the Anthem folder."
            % self._base())

    # ------------------------------------------------------------------

    def generate(self, request, progress=None):
        if not self.configured():
            raise ProviderError(self.missing_message())

        seconds = max(MIN_SECONDS, min(int(request.length_seconds or 180),
                                       MAX_SECONDS))
        payload = {
            "prompt": request.style_prompt,
            "lyrics": "" if request.instrumental else request.lyrics,
            "audio_duration": seconds,
            "audio_format": "mp3",
            "seed": -1,
        }

        self._say(progress, "Sending the song to ACE-Step on this PC...")
        data = self._unwrap(
            http.post_json(self._base() + "/release_task",
                           headers=self._headers(), payload=payload))

        task_id = data.get("task_id") or data.get("taskId")
        if not task_id:
            raise ProviderError(
                "ACE-Step accepted the request but returned no task id: %s"
                % str(data)[:300])

        queued = data.get("queue_position")
        if queued:
            self._say(progress, "Queued at position %s." % queued)

        return self._poll(task_id, request, progress)

    def _poll(self, task_id, request, progress):
        timeout = int(self.settings.get("poll_timeout_seconds", 1800))
        deadline = time.time() + timeout
        waited = 0

        while time.time() < deadline:
            time.sleep(5)
            waited += 5
            try:
                data = self._unwrap(
                    http.post_json(self._base() + "/query_result",
                                   headers=self._headers(),
                                   payload={"task_id_list": [task_id]}))
            except http.HttpError as exc:
                if exc.status and 500 <= exc.status < 600:
                    continue           # the server is busy, not broken
                raise ProviderError(self._explain(exc)) from None

            entry = self._entry_for(data, task_id)
            if entry is None:
                continue

            status = entry.get("status")
            if status == 1:
                return self._collect(entry, request, progress)
            if status == 2:
                raise ProviderError(
                    "ACE-Step could not render this track: %s"
                    % (entry.get("error") or entry.get("message")
                       or "no reason given"))

            self._say(progress,
                      "Generating on this PC... %ds elapsed" % waited)

        raise ProviderError(
            "ACE-Step did not finish within %ds. On a slower GPU raise "
            "poll_timeout_seconds in settings.json." % timeout)

    # ------------------------------------------------------------------

    @staticmethod
    def _unwrap(response):
        """Pull `data` out of the standard wrapper, raising on an error."""
        if not isinstance(response, dict):
            raise ProviderError("Unexpected reply from ACE-Step: %s"
                                % str(response)[:200])
        code = response.get("code")
        if code is not None and int(code) != 200:
            raise ProviderError(
                "ACE-Step returned code %s: %s"
                % (code, response.get("error") or "no detail"))
        data = response.get("data")
        return data if isinstance(data, dict) else {"_raw": data}

    @staticmethod
    def _entry_for(data, task_id):
        """Find this task inside whatever shape query_result returned."""
        candidates = []
        for key in ("results", "task_list", "tasks", "list", "_raw"):
            value = data.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if not candidates:
            # A single-task reply may come back flat.
            return data if "status" in data else None
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if str(item.get("task_id", item.get("taskId", ""))) == str(task_id):
                return item
        return candidates[0] if isinstance(candidates[0], dict) else None

    def _collect(self, entry, request, progress):
        result = entry.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                raise ProviderError(
                    "ACE-Step finished but its result was unreadable: %s"
                    % result[:200]) from None
        if not isinstance(result, (dict, list)):
            raise ProviderError(
                "ACE-Step finished but returned no audio: %s"
                % str(result)[:200])

        files = []
        for item in (result if isinstance(result, list) else [result]):
            if isinstance(item, dict):
                path = item.get("file") or item.get("path") or item.get("url")
                if path:
                    files.append(path)
        if not files:
            raise ProviderError(
                "ACE-Step finished but named no audio file: %s"
                % str(result)[:200])

        out = []
        for index, path in enumerate(files, 1):
            url = self._audio_url(path)
            suffix = "" if len(files) == 1 else "_take%d" % index
            dest = os.path.join(
                self.settings["_run_dir"],
                "%s%s.mp3" % (_slug(request.title), suffix))
            self._say(progress, "Saving take %d..." % index)
            self.download(url, dest)
            out.append(Track(
                title=request.title,
                audio_path=dest,
                provider=self.name,
                style_prompt=request.style_prompt,
                lyrics="" if request.instrumental else request.lyrics,
                raw={"task": entry.get("task_id", "")},
            ))
        return out

    def _audio_url(self, path):
        """Build a download URL from whatever the server handed back."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return self._base() + path
        return (self._base() + "/v1/audio?path="
                + urllib.parse.quote(path, safe=""))

    @staticmethod
    def _explain(exc):
        if exc.status == 401:
            return ("ACE-Step rejected the token. Clear acestep_token in "
                    "settings.json, or set it to match the server.")
        if exc.status == 429:
            return "The ACE-Step server is at its queue limit. Try again."
        if exc.status == 0:
            return ("Lost contact with the ACE-Step server: %s. Is the "
                    "terminal still running?" % exc.body)
        return str(exc)


def _slug(text):
    keep = [c if c.isalnum() or c in " -_" else "" for c in text]
    return ("".join(keep).strip().replace(" ", "_") or "track")[:60]
