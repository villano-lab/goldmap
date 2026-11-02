import shutil

import pytest

from goldpan import dataset, registry
from goldmap import build, catalog
from test_build import form


@pytest.fixture
def two_detectors(tmp_path, registry):
    """A copy of the registry with a second detector, TEST-B, that has two channels and a name of its own."""
    reg = tmp_path / "registry"
    shutil.copytree(registry, reg)
    from goldpan import registry as r
    r.add_record(reg, "detectors", "TEST-B", {"readout": "DCRC_RUN76", "status": "inferred", "evidence": "a test detector, two channels",
                                              "idx": {"channels": {"PhX": [0, 0], "PhY": [0, 1]}, "roles": {"PhX": "phonon", "PhY": "phonon"}}})
    return reg


def test_the_detectors_say_which_registry_file_they_come_from(two_detectors):
    by_name = {d["name"]: d for d in catalog.detectors([two_detectors])}
    assert by_name["TEST-B"]["origin"].endswith("detectors.toml") and by_name["NAI-S2"]["origin"].endswith("run76.toml")


def test_two_sources_with_different_detectors_make_one_definition(tmp_path, idx, two_detectors):
    f = form(idx, two_detectors, tmp_path / "out")
    f["sources"] = [{"name": "raw", "format": "idx", "root": str(idx), "series": ["07221111_2153"], "detector": "NAI-S2"},
                    {"name": "raw2", "format": "idx", "root": str(idx), "series": ["07221112_0943"], "detector": "TEST-B"}]
    f["steps"] = [{"algorithm": "baseline", "channels": "role:phonon",
                   "params": {"glitch_samples": "@readout.glitch_samples", "pretrigger_samples": "@readout.pretrigger_samples"}}]
    f["metadata_rows"] = f["metadata_rows"]
    result = build.write(f, tmp_path / "work")
    assert result["problem"] is None and len(result["files"]) == 5
    spec = dataset.load(result["definition"])
    assert [(s.name, s.detector) for s in spec.sources] == [("raw", "NAI-S2"), ("raw2", "TEST-B")]
    assert [p.name for p in spec.sources[1].files()] == ["07221112_0943_F0001", "07221112_0943_F0002"]
    assert spec.sources[1].read["channels"] == {"PhX": [0, 0], "PhY": [0, 1]}              # each source took the channels of its own detector
    assert build.validate(f, tmp_path / "work2") == {"ok": True, "files": 5, "series": 2, "steps": 1, "problem": None}
    assert not (tmp_path / "work2").exists()


def test_the_same_source_name_twice_is_refused(tmp_path, idx, two_detectors):
    f = form(idx, two_detectors, tmp_path / "out")
    f["sources"] = [{"name": "raw", "format": "idx", "root": str(idx), "series": ["07221111_2153"], "detector": "NAI-S2"},
                    {"name": "raw", "format": "idx", "root": str(idx), "series": ["07221112_0943"], "detector": "TEST-B"}]
    with pytest.raises(ValueError, match="unique"):
        build.write(f, tmp_path / "work")


def test_detectors_and_readouts_say_which_registry_folder_they_are_in(tmp_path, registry):
    from goldpan import registry as r
    extra = tmp_path / "extra"
    r.add_record(extra, "detectors", "TEST-C", {"readout": "DCRC_RUN76", "status": "inferred", "evidence": "a test detector in a second registry folder"})
    folders = [str(extra), str(registry)]
    by_name = {d["name"]: d for d in catalog.detectors(folders)}
    assert by_name["TEST-C"]["registry"] == str(extra) and by_name["NAI-S2"]["registry"] == str(registry)
    assert {x["registry"] for x in catalog.readouts(folders)} == {str(registry)}
    assert catalog.detectors([]) == []
