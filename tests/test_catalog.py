import pytest

from goldpan import dataset
from goldmap import catalog


def test_the_readout_fields_are_the_ones_goldpan_accepts():
    assert set(catalog.READOUT_FIELDS) == set(dataset._READOUT)


def test_algorithms_tell_the_form_what_to_ask_for():
    by_name = {a["name"]: a for a in catalog.algorithms()}
    peak = by_name["peak"]
    assert peak["kind"] == "quantities" and peak["outputs"] == ["adc_max", "current_max"]
    assert {p["name"]: p["readout"] for p in peak["params"]} == {"glitch_samples": True, "pretrigger_samples": True, "amps_per_adc": False}
    lowpass = by_name["lowpass"]
    assert lowpass["kind"] == "trace" and lowpass["outputs"] == [] and {"cutoff_hz", "order"} <= {p["name"] for p in lowpass["params"]}
    assert all(a["summary"] for a in by_name.values())


def test_scan_groups_dump_folders_by_series_and_ignores_the_rest(idx):
    assert catalog.scan(idx) == [{"series": "07221111_2153", "dumps": 3, "first": 1, "last": 3},
                                 {"series": "07221112_0943", "dumps": 2, "first": 1, "last": 2}]
    with pytest.raises(ValueError, match="not a folder"):
        catalog.scan(idx / "nowhere")


def test_series_facts_read_a_series_list(tmp_path):
    path = tmp_path / "list.csv"
    path.write_text("series,type,source_shield,HV,trigger,duration_min\n07221111_2153,Side2,PuBe,-82.2,DCRC1pB 10,55\n"
                    "07220401_1453,test,,,NaI array,\n", encoding="utf-8")
    facts = catalog.series_facts(path)
    assert facts["07221111_2153"] == {"hv_v": -82.2, "trigger": "DCRC1pB 10", "trigger_value": 10.0, "type": "Side2", "source_shield": "PuBe", "duration_min": 55.0}
    assert facts["07220401_1453"] == {"hv_v": None, "trigger": "NaI array", "trigger_value": None, "type": "test", "source_shield": None, "duration_min": None}
    (tmp_path / "bad.csv").write_text("name\nx\n", encoding="utf-8")
    with pytest.raises(ValueError, match="series"):
        catalog.series_facts(tmp_path / "bad.csv")


def test_detectors_come_from_the_registry(registry):
    by_name = {d["name"]: d for d in catalog.detectors([registry])}
    nai = by_name["NAI-S2"]
    assert nai["readout"] == "DCRC_RUN76" and nai["status"] == "inferred" and nai["readout_record"]["config"]["sample_period_s"] == pytest.approx(0.8e-6)
    assert {c["name"] for c in nai["channels"]} == {"Side2pA", "Side2pB", "Side2pC", "Side2pD", "Side2pE", "Side2pF"}
    assert {c["role"] for c in nai["channels"]} == {"phonon"}
