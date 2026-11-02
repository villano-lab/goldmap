"""The local web server: one page and a small JSON API, on 127.0.0.1 only.

The app reads folders and writes files for whoever can talk to it, so it answers only a browser that was given the page by this process:
the page carries a random token that every request must send back (`X-Goldmap-Token`), and the `Host` header must be the address of the
server (a page on another site cannot read or guess either, which closes the usual ways a web page reaches a program on localhost).
"""
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import build, catalog

STATIC = Path(__file__).parent / "static"


class Config:
    """What the server starts with: the registry folders, the series list, the folders of raw data and where to write."""

    def __init__(self, registry=(), series_list=None, roots=(), folder=None):
        self.registry = [str(r) for r in registry]
        self.series_list = str(series_list) if series_list else None
        self.roots = [str(r) for r in roots]
        self.folder = str(folder) if folder else str(Path.cwd())

    def registries(self) -> list:
        """The registry folders to read: the ones given, or the default one when it already exists."""
        return self.registry or ([self.default_registry()] if Path(self.default_registry()).is_dir() else [])

    def default_registry(self) -> str:
        """Where a new detector goes when no registry folder was given: ``registry`` inside the folder files are written to."""
        return str(Path(self.folder) / "registry")

    def targets(self) -> list:
        """The registry folders a detector may be added to: the given ones, or the default one."""
        return self.registry or [self.default_registry()]


def make_server(config: Config, port: int = 0) -> ThreadingHTTPServer:
    """A server for `config` on 127.0.0.1 (port 0: any free port). Its `token` attribute is the secret the page carries."""
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        server_version = "goldmap"

        def log_message(self, *args):                                    # quiet
            pass

        def _allowed(self) -> bool:
            host = self.headers.get("Host", "")
            return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def _send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj))

        def _guard(self) -> bool:
            if not self._allowed():
                self._json(403, {"error": "unexpected Host header"})
                return False
            if self.headers.get("X-Goldmap-Token") != token:
                self._json(403, {"error": "missing or wrong token: open the page the app started"})
                return False
            return True

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                if not self._allowed():
                    return self._json(403, {"error": "unexpected Host header"})
                page = (STATIC / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                return self._send(200, page, "text/html")
            if not self._guard():
                return
            try:
                if url.path == "/api/state":
                    facts = catalog.series_facts(config.series_list) if config.series_list else {}
                    return self._json(200, {"algorithms": catalog.algorithms(), "detectors": catalog.detectors(config.registries()),
                                            "readouts": catalog.readouts(config.registries()), "registry": config.registries(),
                                            "targets": config.targets(), "roots": config.roots, "folder": config.folder, "facts": facts,
                                            "output_root": os.environ.get("GOLDSLUICE_OUTPUT", "").strip() or "~/goldsluice-output"})
                if url.path == "/api/scan":
                    root = parse_qs(url.query).get("root", [""])[0]
                    return self._json(200, {"series": catalog.scan(root)})
            except (ValueError, OSError, KeyError) as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            self._json(404, {"error": "no such address"})

        def do_POST(self):
            if not self._guard():
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json(415, {"error": "send JSON"})
            try:
                form = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                folder = form.pop("folder", None) or config.folder
                if self.path == "/api/detector/preview":
                    return self._json(200, {"text": build.detector_preview(form)})
                if self.path == "/api/detector/add":
                    target = form.pop("target", None) or config.targets()[0]
                    if target not in config.targets():
                        return self._json(400, {"error": f"a detector can only be added to {config.targets()}"})
                    return self._json(200, build.detector_add(form, target))
                if self.path == "/api/validate":
                    return self._json(200, build.validate(form, folder))
                if self.path == "/api/preview":
                    return self._json(200, {"text": build.preview(form, folder)})
                if self.path == "/api/write":
                    return self._json(200, build.write(form, folder))
            except (ValueError, OSError, KeyError, TypeError) as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:                                       # a bug, or a library that is too old: say so instead of dropping the connection
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            self._json(404, {"error": "no such address"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = token
    return server


def serve_in_thread(server) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t
