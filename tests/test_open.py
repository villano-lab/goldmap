"""Open an existing definition: the form it gives writes the same definition and the same run metadata again."""
import json

import pytest

from goldpan import dataset, runmeta
from goldmap import build, server
from test_build import form
from test_server import call


def steps_of(path):
    """The steps of a definition as goldpan reads them."""
    return [(s.algorithm, s.channels, dict(s.params), s.name, s.input, s.suffix, s.sources) for s in dataset.load(path).steps]


def test_what_goldmap_wrote_opens_and_writes_the_same_definition_under_a_new_name(tmp_path, idx, registry):
    folder = tmp_path / "work"
    first = build.write(form(idx, registry, tmp_path / "out", output_format="parquet"), folder)
    opened = build.open_definition(first["definition"], [str(registry)])
    f = opened["form"]
    assert opened["notes"] == []
    assert f["name"] == "r76-test" and f["description"] == "a test" and f["registry"] == [str(registry)]
    assert f["sources"] == [{"name": "raw", "format": "idx", "root": str(idx.resolve()).replace("\\", "/"),
                             "series": ["07221111_2153", "07221112_0943"], "detector": "NAI-S2"}]
    assert [s.get("input") for s in f["steps"]] == [None, "lp"] and f["steps"][1]["suffix"] == "_lp"
    second = build.write({**f, "name": "r76-test-2"}, folder)
    assert second["problem"] is None
    assert steps_of(second["definition"]) == steps_of(first["definition"])
    assert [p.name for p in dataset.load(second["definition"]).source().files()] == [p.name for p in dataset.load(first["definition"]).source().files()]
    table = runmeta.read_table(folder / "series.csv")
    assert list(table["hv_v"]) == [-82.2, -82.2] and list(table["trigger"]) == ["DCRC1pB 10", "DCRC1pB 10"]


def test_a_definition_with_a_glob_opens_with_the_series_its_dumps_belong_to(tmp_path, idx, registry):
    path = tmp_path / "glob.dataset.toml"
    path.write_text(f'[dataset]\nname = "g"\noutput = "{(tmp_path / "out").as_posix()}"\nregistry = ["{registry.as_posix()}"]\n'
                    f'[[sources]]\nname = "side2"\nformat = "idx"\nglob = "{idx.as_posix()}/0722*_F[0-9][0-9][0-9][0-9]"\ndetector = "NAI-S2"\n', encoding="utf-8")
    f = build.open_definition(path, [str(registry)])["form"]
    assert f["sources"][0]["series"] == ["07221111_2153", "07221112_0943"] and f["steps"] == [] and "metadata_rows" not in f


def test_what_cannot_be_carried_over_as_it_is_is_said(tmp_path, idx, registry):
    pattern = f"{idx.as_posix()}/07229999_0001_F[0-9][0-9][0-9][0-9]"                     # a series that is not on this computer
    path = tmp_path / "far.dataset.toml"
    path.write_text(f'[dataset]\nname = "far"\noutput = "{(tmp_path / "out").as_posix()}"\nregistry = ["{registry.as_posix()}"]\nmetadata = "far.csv"\n'
                    f'[[sources]]\nname = "side2"\nformat = "idx"\npaths = ["{pattern}"]\ndetector = "NAI-S2"\n', encoding="utf-8")
    runmeta.write_table(tmp_path / "far.csv", {"series": ["07229999_0001"], "hv_v": [-82.0], "dumps_in_output": [12.0], "from": ["a note"]})
    opened = build.open_definition(path, [])                                                 # goldmap was started without the registry
    notes = " | ".join(opened["notes"])
    assert "matches no dump on this computer" in notes and "was not started with" in notes and "dumps_in_output, from" in notes
    f = opened["form"]
    assert f["sources"][0]["series"] == ["07229999_0001"] and f["registry"] == []
    assert f["metadata_rows"] == [{"series": "07229999_0001", "hv_v": -82.0, "dumps_in_output": 12.0, "from": "a note"}]
    table = build.table(f["metadata_rows"])                                                  # the columns the page does not show are written back
    assert table == {"series": ["07229999_0001"], "dumps_in_output": [12.0], "from": ["a note"], "hv_v": [-82.0]}


def test_writing_a_second_definition_into_the_folder_keeps_the_metadata_of_the_first(tmp_path, idx, registry):
    folder = tmp_path / "work"
    build.write(form(idx, registry, tmp_path / "out"), folder)                              # both series, in the shared series.csv
    f = build.open_definition(folder / "r76-test.dataset.toml", [str(registry)])["form"]
    f["sources"][0]["series"] = ["07221112_0943"]
    f["metadata_rows"] = [{"series": "07221112_0943", "hv_v": "-60", "trigger": "DCRC1pA 2", "trigger_value": "2"}]
    build.write({**f, "name": "second"}, folder)
    table = runmeta.read_table(folder / "series.csv")
    assert list(table["series"]) == ["07221111_2153", "07221112_0943"] and list(table["hv_v"]) == [-82.2, -60.0]
    assert dataset.load(folder / "r76-test.dataset.toml").run_metadata() is not None              # the first one still finds every series it has


def test_a_definition_goldmap_cannot_represent_is_refused_with_the_reason(tmp_path, idx, registry):
    head = f'[dataset]\nname = "x"\noutput = "{(tmp_path / "out").as_posix()}"\nregistry = ["{registry.as_posix()}"]\n'
    source = f'[[sources]]\nname = "side2"\nformat = "idx"\nglob = "{idx.as_posix()}/0722*_F*"\ndetector = "NAI-S2"\n'
    own = tmp_path / "own.dataset.toml"
    own.write_text(head + source + 'readout = "DCRC_RUN76"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="sets 'readout'"):
        build.open_definition(own, [str(registry)])
    extra = tmp_path / "extra.dataset.toml"
    extra.write_text(head + source + '[[processing]]\nalgorithm = "baseline"\nchannels = "all"\n[processing.params]\nglitch_samples = 10\n'
                     'pretrigger_samples = 500\nwindow = 3\n', encoding="utf-8")
    with pytest.raises(ValueError):                                                          # goldpan or goldmap refuses a parameter the algorithm does not take
        build.open_definition(extra, [str(registry)])


def test_open_and_the_list_of_definitions_work_through_the_api(tmp_path, idx, registry):
    srv = server.make_server(server.Config([registry], None, [idx], tmp_path / "work"))
    server.serve_in_thread(srv)
    try:
        build.write(form(idx, registry, tmp_path / "out"), tmp_path / "work")
        status, data = call(srv, "GET", "/api/definitions", token=srv.token)
        assert status == 200 and [p.replace("\\", "/").rsplit("/", 1)[-1] for p in json.loads(data)["definitions"]] == ["r76-test.dataset.toml"]
        status, data = call(srv, "POST", "/api/open", {"path": "r76-test.dataset.toml"}, token=srv.token)        # relative to the folder files go to
        assert status == 200 and json.loads(data)["form"]["name"] == "r76-test"
        assert call(srv, "POST", "/api/open", {"path": "nothing.dataset.toml"}, token=srv.token)[0] == 400
        assert call(srv, "POST", "/api/open", {"path": "r76-test.dataset.toml"})[0] == 403
    finally:
        srv.shutdown()
        srv.server_close()
