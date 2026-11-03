import pytest

from goldpan import dataset, runmeta
from goldmap import build


def form(idx, registry, output, **extra):
    return {"name": "r76-test", "output": str(output), "description": "a test", "registry": [str(registry)],
            "sources": [{"name": "raw", "format": "idx", "root": str(idx), "series": ["07221111_2153", "07221112_0943"], "detector": "NAI-S2"}],
            "steps": [{"algorithm": "lowpass", "name": "lp", "channels": "role:phonon",
                       "params": {"cutoff_hz": 50000.0, "order": 4, "sample_period_s": "@readout.sample_period_s"}},
                      {"algorithm": "peak", "channels": "role:phonon", "input": "lp", "suffix": "_lp",
                       "params": {"glitch_samples": "@readout.glitch_samples", "pretrigger_samples": "@readout.pretrigger_samples", "amps_per_adc": 1.5e-9}}],
            "metadata_rows": [{"series": "07221111_2153", "hv_v": "-82.2", "trigger": "DCRC1pB 10", "trigger_value": "10"},
                              {"series": "07221112_0943", "hv_v": -82.2, "trigger": "DCRC1pB 10", "trigger_value": 10}], **extra}


def test_write_makes_a_definition_goldpan_loads_and_a_table_it_reads(tmp_path, idx, registry):
    folder = tmp_path / "work" / "survey"
    result = build.write(form(idx, registry, tmp_path / "out"), folder)
    assert result["problem"] is None and len(result["files"]) == 5
    spec = dataset.load(result["definition"])
    assert spec.name == "r76-test" and [s.algorithm for s in spec.steps] == ["lowpass", "peak"]
    assert spec.steps[1].input == "lp" and spec.steps[1].suffix == "_lp" and spec.source().detector == "NAI-S2"
    assert [p.name for p in spec.source().files()] == ["07221111_2153_F0001", "07221111_2153_F0002", "07221111_2153_F0003", "07221112_0943_F0001", "07221112_0943_F0002"]
    table = spec.run_metadata()
    assert list(table["series"]) == ["07221111_2153", "07221112_0943"] and list(table["hv_v"]) == [-82.2, -82.2] and list(table["trigger_value"]) == [10.0, 10.0]
    assert "trigger" in table and "duration_min" not in table                       # a column nobody filled in is not written
    assert (folder / "series.csv").exists() and runmeta.read_table(folder / "series.csv")["series"].dtype.kind == "U"
    assert result["metadata"] == str(folder.resolve() / "series.csv")


def test_the_folder_of_the_definition_is_made_beside_its_registry_and_a_refused_form_leaves_none(tmp_path, idx, registry):
    import shutil
    reg = tmp_path / "project" / "registry"
    shutil.copytree(registry, reg)
    folder = tmp_path / "project" / "processing" / "r76"                                     # does not exist; the registry is written ../../registry
    assert "registry" in build.preview(form(idx, reg, tmp_path / "out"), folder) and not (tmp_path / "project" / "processing").exists()
    result = build.write(form(idx, reg, tmp_path / "out"), folder)
    assert result["problem"] is None and dataset.load(result["definition"]).registry.detectors()
    bad = form(idx, reg, tmp_path / "out")
    bad["steps"][1]["input"] = "nobody"                                                    # goldpan refuses a step that reads an unknown name
    with pytest.raises(ValueError):
        build.write(bad, tmp_path / "project" / "other" / "deeper")
    assert not (tmp_path / "project" / "other").exists()


def test_a_registry_given_relative_to_the_start_folder_is_found_from_a_definition_far_away(tmp_path, idx, registry, monkeypatch):
    import shutil
    shutil.copytree(registry, tmp_path / "start" / "registry")
    monkeypatch.chdir(tmp_path / "start")                                                   # goldmap --registry registry, started here
    result = build.write(form(idx, "registry", tmp_path / "out"), tmp_path / "far" / "away" / "processing")
    assert result["problem"] is None and dataset.load(result["definition"]).registry.detectors()
    near = build.write(form(idx, "registry", tmp_path / "out"), tmp_path / "start" / "processing")
    assert 'registry = ["../registry"]' in open(near["definition"], encoding="utf-8").read()       # close by: still written relative


def test_the_check_reports_a_series_that_is_not_on_the_disk_but_the_files_are_written(tmp_path, idx, registry):
    f = form(idx, registry, tmp_path / "out")
    f["sources"][0]["series"].append("07229999_0001")
    result = build.write(f, tmp_path / "survey")
    assert result["problem"] and "07229999_0001" in result["problem"] and result["files"] == []
    assert (tmp_path / "survey" / "r76-test.dataset.toml").exists()


def test_a_form_goldpan_refuses_writes_nothing(tmp_path, idx, registry):
    folder = tmp_path / "survey"
    for change, match in (({"name": ""}, "name"), ({"sources": []}, "source"),
                          ({"steps": [{"algorithm": "peak", "channels": "role:phonon", "input": "nobody", "params": {}}]}, "not the name of an earlier step")):
        with pytest.raises(ValueError, match=match):
            build.write({**form(idx, registry, tmp_path / "out"), **change}, folder)
    bad = form(idx, registry, tmp_path / "out")
    bad["sources"][0]["detector"] = ""
    with pytest.raises(ValueError, match="detector"):
        build.write(bad, folder)
    assert not folder.exists()


def test_preview_is_the_text_that_write_puts_in_the_file(tmp_path, idx, registry):
    f = form(idx, registry, tmp_path / "out")
    text = build.preview({**f, "metadata": True}, tmp_path / "survey")
    assert text.startswith("# Made with goldmap.") and 'detector = "NAI-S2"' in text and "[processing.params]" in text
    build.write(f, tmp_path / "survey")
    assert (tmp_path / "survey" / "r76-test.dataset.toml").read_text(encoding="utf-8") == text


def test_the_table_skips_empty_columns_and_makes_numbers_of_the_numeric_ones():
    t = build.table([{"series": "A", "hv_v": "0", "type": ""}, {"series": "B", "hv_v": "-34.0", "trigger": "x"}])
    assert list(t) == ["series", "hv_v", "trigger"] and t["hv_v"] == [0.0, -34.0] and t["trigger"] == [None, "x"]
    with pytest.raises(ValueError, match="no rows"):
        build.table([])


def test_the_registry_is_written_relative_when_it_is_near_and_in_full_when_it_is_far(tmp_path):
    near = tmp_path / "registry"
    assert build._registry_path(tmp_path / "work", near) == "../registry"
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    assert build._registry_path(deep, near) == near.as_posix()
