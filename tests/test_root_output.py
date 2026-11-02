import shutil

import pytest

from goldpan import dataset
from goldmap import build
from test_build import form
from test_multisource import two_detectors   # noqa: F401  (the fixture)


def root_form(idx, registry, tmp_path, **extra):
    f = form(idx, registry, tmp_path / "out")
    f["output_format"] = "root"
    f.update(extra)
    return f


def test_root_output_is_written_with_the_number_of_the_detector_in_the_registry(tmp_path, idx, registry):
    result = build.write(root_form(idx, registry, tmp_path), tmp_path / "work")
    spec = dataset.load(result["definition"])
    assert spec.output_format == "root" and spec.root_detector == 1 and result["problem"] is None          # NAI-S2 is number 1 in the registry
    assert 'output_format = "root"' in build.preview(root_form(idx, registry, tmp_path), tmp_path / "work")


def test_the_number_can_be_given_and_then_wins(tmp_path, idx, registry):
    spec = dataset.load(build.write(root_form(idx, registry, tmp_path, root_detector="7"), tmp_path / "work")["definition"])
    assert spec.root_detector == 7
    with pytest.raises(ValueError, match="whole number|is not a number"):
        build.definition(root_form(idx, registry, tmp_path, root_detector="x"), tmp_path)


def test_parquet_stays_the_default_and_writes_neither_key(tmp_path, idx, registry):
    text = build.preview(form(idx, registry, tmp_path / "out"), tmp_path / "work")
    assert "output_format" not in text and "root_detector" not in text


def test_root_output_for_two_detectors_is_refused(tmp_path, idx, two_detectors):
    f = root_form(idx, two_detectors, tmp_path)
    f["sources"] = [{"name": "raw", "format": "idx", "root": str(idx), "series": ["07221111_2153"], "detector": "NAI-S2"},
                    {"name": "raw2", "format": "idx", "root": str(idx), "series": ["07221112_0943"], "detector": "TEST-B"}]
    with pytest.raises(ValueError, match="one detector only"):
        build.preview(f, tmp_path / "work")


def test_validate_says_when_uproot_is_missing(tmp_path, idx, registry, monkeypatch):
    import importlib.util
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None if name == "uproot" else real(name, *a, **k))
    result = build.validate(root_form(idx, registry, tmp_path), tmp_path / "work")
    assert result["ok"] is False and "needs the package uproot" in result["problem"]
    assert build.validate(form(idx, registry, tmp_path / "out"), tmp_path / "work")["ok"] is True          # Parquet does not
