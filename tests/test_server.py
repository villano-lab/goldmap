import http.client
import json
from pathlib import Path

import pytest

from goldmap import server


@pytest.fixture
def running(tmp_path, idx, registry):
    srv = server.make_server(server.Config([registry], None, [idx], tmp_path / "work"))
    server.serve_in_thread(srv)
    yield srv
    srv.shutdown()
    srv.server_close()


def call(srv, method, path, body=None, token=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_port)
    headers = {"Host": host or f"127.0.0.1:{srv.server_port}"}
    if token:
        headers["X-Goldmap-Token"] = token
    if body is not None:
        headers["Content-Type"] = "application/json"
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    r = c.getresponse()
    data = r.read().decode("utf-8")
    c.close()
    return r.status, data


def test_the_page_carries_the_token_and_the_api_needs_it(running):
    status, page = call(running, "GET", "/")
    assert status == 200 and running.token in page and "__TOKEN__" not in page
    assert call(running, "GET", "/api/state")[0] == 403
    assert call(running, "GET", "/api/state", token="wrong")[0] == 403
    status, data = call(running, "GET", "/api/state", token=running.token)
    state = json.loads(data)
    assert status == 200 and "peak" in {a["name"] for a in state["algorithms"]} and "NAI-S2" in {d["name"] for d in state["detectors"]}
    assert state["registry_full"] == {f: str(Path(f).resolve()).replace("\\", "/") for f in state["registry"]}        # the page shows where each one is


def test_a_request_with_another_host_name_is_refused(running):
    assert call(running, "GET", "/", host="evil.example")[0] == 403
    assert call(running, "GET", "/api/state", token=running.token, host="evil.example")[0] == 403


def test_scan_preview_and_write_work_through_the_api(running, tmp_path, idx, registry):
    status, data = call(running, "GET", "/api/scan?root=" + str(idx).replace("\\", "/"), token=running.token)
    assert status == 200 and [s["series"] for s in json.loads(data)["series"]] == ["07221111_2153", "07221112_0943"]
    assert call(running, "GET", "/api/scan?root=/nowhere/at/all", token=running.token)[0] == 400
    form = {"name": "web", "output": str(tmp_path / "out"), "registry": [str(registry)],
            "sources": [{"root": str(idx), "series": ["07221111_2153"], "detector": "NAI-S2"}],
            "steps": [{"algorithm": "baseline", "channels": "role:phonon",
                       "params": {"glitch_samples": "@readout.glitch_samples", "pretrigger_samples": "@readout.pretrigger_samples"}}]}
    status, data = call(running, "POST", "/api/preview", {**form, "folder": str(tmp_path / "web")}, token=running.token)
    assert status == 200 and 'name = "web"' in json.loads(data)["text"]
    assert not (tmp_path / "web").exists()                                           # a preview writes nothing
    status, data = call(running, "POST", "/api/write", {**form, "folder": str(tmp_path / "web")}, token=running.token)
    result = json.loads(data)
    assert status == 200 and result["problem"] is None and (tmp_path / "web" / "web.dataset.toml").exists()
    status, data = call(running, "POST", "/api/write", {**form, "name": ""}, token=running.token)
    assert status == 400 and "name" in json.loads(data)["error"]
    assert call(running, "POST", "/api/write", {}, token=None)[0] == 403
