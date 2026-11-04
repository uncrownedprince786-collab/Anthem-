"""Tiny JSON-over-HTTP helper.

Deliberately built on urllib so Anthem installs with zero pip packages -
one less thing to go wrong on a machine that is already tight on space.
"""

import json
import urllib.error
import urllib.request


class HttpError(RuntimeError):
    def __init__(self, status, body, url):
        self.status = status
        self.body = body
        self.url = url
        super().__init__("HTTP %s from %s: %s" % (status, url, body[:400]))


def _request(method, url, headers=None, payload=None, timeout=120):
    data = None
    headers = dict(headers or {})
    headers.setdefault("User-Agent", "Anthem/1.0")
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise HttpError(exc.code, body, url) from None
    except urllib.error.URLError as exc:
        raise HttpError(0, str(exc.reason), url) from None

    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except ValueError:
        raise HttpError(status, body, url) from None


def post_json(url, headers=None, payload=None, timeout=120):
    return _request("POST", url, headers, payload, timeout)


def get_json(url, headers=None, timeout=120):
    return _request("GET", url, headers, None, timeout)
