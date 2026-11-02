from pathlib import Path

import pytest

import goldpan

REGISTRY = Path(goldpan.__file__).resolve().parents[2] / "registry"       # the NSDF-Data registry, when goldpan is the one of a checkout


@pytest.fixture
def registry():
    if not (REGISTRY / "run76.toml").exists():
        pytest.skip("needs the registry folder of an NSDF-Data checkout next to goldpan")
    return REGISTRY


@pytest.fixture
def idx(tmp_path):
    """A folder of raw dumps of two series, as the idx adapter names them."""
    root = tmp_path / "idx"
    for series, n in (("07221111_2153", 3), ("07221112_0943", 2)):
        for k in range(1, n + 1):
            (root / f"{series}_F{k:04d}").mkdir(parents=True)
    (root / "notes").mkdir()
    return root
