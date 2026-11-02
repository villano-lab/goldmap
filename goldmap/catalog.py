"""What the page can offer: the algorithms, the detectors, the series found on a disk, and what a series list says about each series."""
import csv
import dataclasses
import inspect
import re
from pathlib import Path

READOUT_FIELDS = ("pretrigger_samples", "glitch_samples", "sample_period_s")
"""The parameters a step may take from the readout of the data (`"@readout.<field>"` in the definition, `goldpan.dataset`)."""

_DUMP = re.compile(r"^(\d{8}_\d{4})_F(\d{4})$")
_NUMERIC = ("hv_v", "trigger_value", "duration_min")


def algorithms() -> list:
    """The goldsluice algorithms: ``{"name", "kind", "outputs", "params": [{"name", "readout"}], "summary"}``, by name. A parameter whose name is a
    field of the readout can be taken from it; the others are numbers the user gives (the algorithms have no defaults)."""
    from goldsluice import ALGORITHMS
    out = []
    for name, module in sorted(ALGORITHMS.items()):
        params = list(inspect.signature(module.problem).parameters)[1:]            # the first is the trace length
        kind = getattr(module, "KIND", "quantities")
        doc = (inspect.getdoc(module) or "").strip().splitlines()
        out.append({"name": name, "kind": kind, "outputs": [] if kind == "trace" else list(module.OUTPUTS),
                    "params": [{"name": p, "readout": p in READOUT_FIELDS} for p in params], "summary": doc[0] if doc else ""})
    return out


def detectors(folders=()) -> list:
    """The detectors of the registry made of `folders` (and `GOLDPAN_REGISTRY`): ``{"name", "number", "readout", "status", "description",
    "channels": [{"name", "role"}], "readout_record"}``, by name. `channels` are those of the idx defaults."""
    from goldpan import registry
    reg = registry.load(*[Path(f).expanduser() for f in folders])
    out = []
    for name, rec in sorted(reg.detectors().items()):
        idx = rec.read.get("idx", {})
        roles = idx.get("roles", {})
        readout = dataclasses.asdict(reg.readout(rec.readout)) if rec.readout and reg.has_readout(rec.readout) else None
        out.append({"name": name, "number": rec.number, "readout": rec.readout, "status": rec.status, "description": rec.description,
                    "channels": [{"name": c, "role": roles.get(c, "")} for c in idx.get("channels", {})], "readout_record": readout})
    return out


def scan(root) -> list:
    """The series of dump folders found directly in `root` (named ``<series>_F<nnnn>``, like ``07221203_2025_F0001``): ``{"series", "dumps",
    "first", "last"}``, by series. Raises `ValueError` if `root` is not a folder."""
    folder = Path(root).expanduser()
    if not folder.is_dir():
        raise ValueError(f"{root}: not a folder")
    found = {}
    for entry in folder.iterdir():
        m = _DUMP.match(entry.name)
        if m:
            found.setdefault(m.group(1), []).append(int(m.group(2)))
    return [{"series": s, "dumps": len(n), "first": min(n), "last": max(n)} for s, n in sorted(found.items())]


def _number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def series_facts(path) -> dict:
    """What a series list (a CSV with a ``series`` column; ``nsdf_r76_series.csv`` of NSDF-Data) says about each series, as the columns of the
    run-metadata table: ``{series: {"hv_v", "trigger", "trigger_value", "type", "source_shield", "duration_min"}}``. An empty or missing value is `None`.
    ``trigger_value`` is the number at the end of the trigger text (``DCRC1pA 2`` gives 2.0)."""
    with open(Path(path).expanduser(), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or "series" not in rows[0]:
        raise ValueError(f"{path}: needs a 'series' column")
    out = {}
    for r in rows:
        trigger = (r.get("trigger") or "").strip()
        value = _number(trigger.rsplit(" ", 1)[-1]) if " " in trigger else None
        out[r["series"]] = {"hv_v": _number(r.get("HV", r.get("hv_v"))), "trigger": trigger or None, "trigger_value": value,
                            "type": (r.get("type") or "").strip() or None, "source_shield": (r.get("source_shield") or "").strip() or None,
                            "duration_min": _number(r.get("duration_min"))}
    return out


def readouts(folders=()) -> list:
    """The readouts of the registry made of `folders`: ``{"name", "pretrigger_samples", "glitch_samples", "sample_period_s", "status"}``, by name."""
    from goldpan import registry
    reg = registry.load(*[Path(f).expanduser() for f in folders])
    return [{"name": name, **dataclasses.asdict(rec.config), "status": rec.status} for name, rec in sorted(reg.readouts().items())]
