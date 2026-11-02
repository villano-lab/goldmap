import json

import pytest

from goldpan import registry
from goldmap import build, server
from test_build import form
from test_server import call


def test_validate_checks_the_definition_and_writes_nothing(tmp_path, idx, registry):
    work = tmp_path / "work"
    result = build.validate(form(idx, registry, tmp_path / "out"), work)
    assert result == {"ok": True, "files": 5, "series": 2, "steps": 2, "problem": None}
    assert not work.exists()                                                      # nothing was written where the files would go


def test_validate_reports_what_goldsluice_check_finds_wrong(tmp_path, idx, registry):
    f = form(idx, registry, tmp_path / "out")
    f["sources"][0]["series"].append("07229999_0001")
    result = build.validate(f, tmp_path / "work")
    assert result["ok"] is False and "07229999_0001" in result["problem"] and result["files"] == 0


def test_validate_refuses_what_goldpan_refuses(tmp_path, idx, registry):
    f = form(idx, registry, tmp_path / "out")
    f["steps"][1]["input"] = "nobody"
    with pytest.raises(ValueError, match="not the name of an earlier step"):
        build.validate(f, tmp_path / "work")


@pytest.fixture
def running(tmp_path, idx, registry):
    srv = server.make_server(server.Config([registry], None, [idx], tmp_path / "work"))
    server.serve_in_thread(srv)
    yield srv
    srv.shutdown()
    srv.server_close()


def test_the_api_validates(running, tmp_path, idx, registry):
    status, data = call(running, "POST", "/api/validate", form(idx, registry, tmp_path / "out"), token=running.token)
    assert status == 200 and json.loads(data)["ok"] is True and not (tmp_path / "work" / "r76-test.dataset.toml").exists()


def test_an_unexpected_exception_is_answered_not_dropped(running, monkeypatch):
    def broken(form, folder):
        raise RuntimeError("something nobody expected")
    monkeypatch.setattr(build, "preview", broken)
    status, data = call(running, "POST", "/api/preview", {"name": "x"}, token=running.token)
    assert status == 500 and "RuntimeError: something nobody expected" in json.loads(data)["error"]


def test_a_goldpan_without_add_record_gives_a_clear_message(monkeypatch):
    monkeypatch.delattr(registry, "add_record")
    with pytest.raises(ValueError, match="too old to add a detector"):
        build.detector_preview({"name": "X"})
