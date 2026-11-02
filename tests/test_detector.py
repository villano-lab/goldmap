import json

import pytest

from goldmap import build, catalog, server
from test_server import call

FORM = {"name": "TEST-DET", "number": "4", "description": "a test detector", "status": "inferred",
        "evidence": "the wiring sheet of the test setup; not checked on a file", "series": ["S1", " "],
        "readout": None,
        "new_readout": {"name": "TEST_READOUT", "pretrigger_samples": "500", "glitch_samples": "10", "sample_period_s": "8e-7", "status": "inferred",
                        "evidence": "measured on three test dumps"},
        "channels": [{"name": "PhA", "detector": "0", "input": "0", "role": "phonon"}, {"name": "PhB", "detector": "0", "input": "1", "role": "phonon"},
                     {"name": "", "detector": "", "input": "", "role": ""}]}


def test_the_form_becomes_a_detector_and_a_readout_record():
    (name, table), readout = build.detector_records(FORM)
    assert name == "TEST-DET" and table["number"] == 4 and table["readout"] == "TEST_READOUT" and table["series"] == ["S1"]
    assert table["idx"] == {"channels": {"PhA": [0, 0], "PhB": [0, 1]}, "roles": {"PhA": "phonon", "PhB": "phonon"}}
    assert readout == ("TEST_READOUT", {"pretrigger_samples": 500, "glitch_samples": 10, "sample_period_s": 8e-7, "status": "inferred",
                                        "evidence": "measured on three test dumps"})


def test_add_writes_both_records_and_the_catalog_reads_them_back(tmp_path):
    folder = tmp_path / "reg"
    result = build.detector_add(FORM, folder)
    assert [p.split("\\")[-1].split("/")[-1] for p in result["files"]] == ["readouts.toml", "detectors.toml"]
    det = {d["name"]: d for d in catalog.detectors([folder])}["TEST-DET"]
    assert det["readout"] == "TEST_READOUT" and det["number"] == 4 and [c["name"] for c in det["channels"]] == ["PhA", "PhB"]
    assert [r["name"] for r in catalog.readouts([folder])] == ["TEST_READOUT"]
    assert "[detectors.TEST-DET2]" in build.detector_preview({**FORM, "name": "TEST-DET2", "new_readout": None, "readout": "TEST_READOUT"})


def test_a_detector_may_use_a_readout_that_exists_and_a_refused_form_writes_nothing(tmp_path):
    folder = tmp_path / "reg"
    build.detector_add(FORM, folder)
    before = {p.name: p.read_text(encoding="utf-8") for p in folder.iterdir()}
    second = {**FORM, "name": "TEST-DET2", "new_readout": None, "readout": "TEST_READOUT"}
    build.detector_add(second, folder)
    after = {p.name: p.read_text(encoding="utf-8") for p in folder.iterdir()}
    for bad, match in (({**FORM, "name": ""}, "name"), ({**FORM, "name": "TEST-DET"}, "already"),
                       ({**FORM, "name": "X", "evidence": ""}, "evidence"), ({**FORM, "name": "X", "status": ""}, "status"),
                       ({**FORM, "name": "X", "new_readout": {**FORM["new_readout"], "name": "TEST_READOUT"}}, "already"),
                       ({**FORM, "name": "X", "new_readout": {**FORM["new_readout"], "pretrigger_samples": ""}}, "pretrigger_samples"),
                       ({**FORM, "name": "X", "new_readout": None, "readout": "NOPE"}, "no readout"),
                       ({**FORM, "name": "X", "channels": [FORM["channels"][0], FORM["channels"][0]]}, "twice")):
        with pytest.raises(ValueError, match=match):
            build.detector_add(bad, folder)
    assert {p.name: p.read_text(encoding="utf-8") for p in folder.iterdir()} == after and after != before


@pytest.fixture
def running(tmp_path):
    srv = server.make_server(server.Config([], None, [], tmp_path / "work"))
    server.serve_in_thread(srv)
    yield srv
    srv.shutdown()
    srv.server_close()


def test_the_api_adds_a_detector_to_the_default_registry_and_only_there(running, tmp_path):
    status, data = call(running, "GET", "/api/state", token=running.token)
    state = json.loads(data)
    assert state["detectors"] == [] and state["targets"] == [str(tmp_path / "work" / "registry")]
    status, data = call(running, "POST", "/api/detector/preview", FORM, token=running.token)
    assert status == 200 and "[readouts.TEST_READOUT]" in json.loads(data)["text"] and not (tmp_path / "work" / "registry").exists()
    status, data = call(running, "POST", "/api/detector/add", {**FORM, "target": str(tmp_path / "elsewhere")}, token=running.token)
    assert status == 400 and "can only be added" in json.loads(data)["error"] and not (tmp_path / "elsewhere").exists()
    status, data = call(running, "POST", "/api/detector/add", FORM, token=running.token)
    assert status == 200 and (tmp_path / "work" / "registry" / "detectors.toml").exists()
    state = json.loads(call(running, "GET", "/api/state", token=running.token)[1])
    assert [d["name"] for d in state["detectors"]] == ["TEST-DET"] and [r["name"] for r in state["readouts"]] == ["TEST_READOUT"]
    assert call(running, "POST", "/api/detector/add", FORM, token=None)[0] == 403
