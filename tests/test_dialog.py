"""The folder window: what it gives back, and the page's way to it. No window is opened here: the process is replaced."""
import json
import subprocess

import pytest

from goldmap import dialog, server
from test_server import call


def fake_run(returncode, stdout="", stderr=""):
    def run(args, **kwargs):
        assert args[-2:] == ["C:/start", "a title"]                                        # the start folder and the title reach the window
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)
    return run


def test_the_chosen_folder_comes_back_and_closing_the_window_gives_nothing(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run(0, "C:/data/registry\n"))
    assert dialog.choose_folder("C:/start", "a title") == "C:/data/registry"
    monkeypatch.setattr(subprocess, "run", fake_run(0, "\n"))
    assert dialog.choose_folder("C:/start", "a title") == ""


def test_a_computer_that_cannot_open_the_window_says_so(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run(1, stderr="Traceback ...\n_tkinter.TclError: no display name"))
    with pytest.raises(ValueError, match="no display name.*type the path"):
        dialog.choose_folder("C:/start", "a title")


def test_the_page_asks_for_the_window_through_the_api(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(dialog, "choose_folder", lambda start, title: asked.append((start, title)) or "C:/picked")
    srv = server.make_server(server.Config([], None, [], tmp_path / "work"))
    server.serve_in_thread(srv)
    try:
        status, data = call(srv, "POST", "/api/choose-folder", {"start": "C:/here", "title": "Pick one"}, token=srv.token)
        assert status == 200 and json.loads(data) == {"path": "C:/picked"} and asked == [("C:/here", "Pick one")]
        assert call(srv, "POST", "/api/choose-folder", {}, token=None)[0] == 403                     # only the page goldmap served
    finally:
        srv.shutdown()
        srv.server_close()
