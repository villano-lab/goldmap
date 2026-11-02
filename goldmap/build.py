"""The form of the page -> the dataset definition and the run-metadata table -> the files.

The form is plain JSON (what the page sends)::

    {"name": "r76-82v", "output": "C:/NSDF/goldsluice-output/r76-82v", "description": "...",
     "registry": ["C:/Users/me/NSDF-Data/registry"],
     "sources": [{"name": "side2", "format": "idx", "root": "C:/NSDF/idx", "series": ["07221111_2153", ...], "detector": "NAI-S2"}],
     "steps": [{"algorithm": "peak", "channels": "role:phonon", "params": {"glitch_samples": "@readout.glitch_samples", "amps_per_adc": 1.5e-9}},
               {"algorithm": "lowpass", "name": "lp", "channels": "role:phonon", "params": {...}}],
     "metadata": [{"series": "07221111_2153", "hv_v": -82.2, "trigger": "DCRC1pB 10", "trigger_value": 10}, ...]}

`goldpan.dataset` writes and checks the definition and `goldpan.runmeta` the table; nothing here knows the rules of either.
"""
import os
from pathlib import Path

from goldpan import dataset, runmeta

NUMERIC_COLUMNS = ("hv_v", "trigger_value", "duration_min")
"""Columns of the metadata table that are numbers; the others are text."""
METADATA_FILE = "series.csv"
"""The file name of the metadata table, written beside the definition."""


def _posix(path) -> str:
    return str(path).replace("\\", "/")


def _registry_path(folder: Path, registry: str) -> str:
    """The registry folder as the definition writes it: relative to the folder of the definition when that is possible, else as given."""
    given = Path(registry).expanduser()
    try:
        relative = _posix(os.path.relpath(given, folder))
    except ValueError:                                                  # another drive (Windows)
        return _posix(given)
    return relative if relative.count("../") <= 3 else _posix(given)     # a path that climbs far up is clearer written in full


def _source(form_source: dict, index: int) -> dict:
    series = list(form_source.get("series", []))
    root = str(form_source.get("root", "")).rstrip("/\\")
    if not series or not root:
        raise ValueError(f"source {index + 1}: choose the folder of the raw data and at least one series")
    out = {"name": form_source.get("name") or f"source{index + 1}", "format": form_source.get("format", "idx"),
           "paths": [f"{_posix(root)}/{s}_F[0-9][0-9][0-9][0-9]" for s in series],         # one pattern per series; every pattern must match a dump
           "detector": form_source.get("detector", "")}
    if not out["detector"]:
        raise ValueError(f"source {index + 1}: choose a detector")
    return out


def _step(form_step: dict, index: int) -> dict:
    if not form_step.get("algorithm"):
        raise ValueError(f"step {index + 1}: choose an algorithm")
    out = {"algorithm": form_step["algorithm"], "channels": form_step.get("channels") or "all"}
    for key in ("name", "input", "suffix"):
        if form_step.get(key):
            out[key] = form_step[key]
    if form_step.get("params"):
        out["params"] = dict(form_step["params"])
    return out


def definition(form: dict, folder) -> dict:
    """The dataset definition (a mapping with the layout of the file, for `goldpan.dataset.dumps`) that the form describes, for a file in `folder`."""
    folder = Path(folder).expanduser().resolve()
    if not form.get("name") or not form.get("output"):
        raise ValueError("give the dataset a name and an output folder")
    head = {"name": form["name"], "output": _posix(form["output"])}
    if form.get("description"):
        head["description"] = form["description"]
    if form.get("registry"):
        head["registry"] = [_registry_path(folder, r) for r in form["registry"]]
    if form.get("metadata"):
        head["metadata"] = METADATA_FILE
    if not form.get("sources"):
        raise ValueError("add at least one source")
    return {"dataset": head, "sources": [_source(s, i) for i, s in enumerate(form["sources"])],
            "processing": [_step(s, i) for i, s in enumerate(form.get("steps", []))]}


def table(rows: list) -> dict:
    """The metadata table (``{column: values}``, `series` first) of the rows the form gives (``[{"series": ..., "hv_v": ...}, ...]``)."""
    if not rows:
        raise ValueError("the metadata table has no rows")
    columns = ["series"] + sorted({k for r in rows for k in r if k != "series"})
    out = {}
    for c in columns:
        values = [r.get(c) for r in rows]
        if c in NUMERIC_COLUMNS:
            values = [None if v in (None, "") else float(v) for v in values]
        else:
            values = [None if v in (None, "") else str(v) for v in values]
        if all(v is None for v in values):
            continue                                                    # a column nobody filled in is not written
        out[c] = values
    return out


def header(form: dict) -> str:
    return f"Made with goldmap. Check:  python -m goldsluice check {form['name']}.dataset.toml"


def preview(form: dict, folder) -> str:
    """The text of the definition file, checked by goldpan; `ValueError` says what is wrong."""
    return dataset.dumps(definition(form, folder), base=folder, header=header(form))


def write(form: dict, folder) -> dict:
    """Write `<name>.dataset.toml` (and `series.csv` when the form has metadata rows) into `folder`, then ask goldsluice to check the definition.
    Returns ``{"definition", "metadata", "files", "problem"}``: the paths written, the raw files that were found, and why the check failed
    (`None` if it passed). A form that goldpan refuses writes nothing and raises `ValueError`."""
    folder = Path(folder).expanduser().resolve()
    if form.get("metadata_rows"):
        form = {**form, "metadata": True}
    spec = definition(form, folder)
    text = dataset.dumps(spec, base=folder, header=header(form))             # refuse before anything is written
    folder.mkdir(parents=True, exist_ok=True)
    meta = None
    if form.get("metadata_rows"):
        meta = folder / METADATA_FILE
        runmeta.write_table(meta, table(form["metadata_rows"]))
    path = folder / f"{form['name']}.dataset.toml"
    path.write_text(text, encoding="utf-8", newline="\n")
    files, problem = [], None
    try:
        from goldsluice import batch
        files = [_posix(item[-1]) for item in batch.check(path, allow_output_in_repo=False)]      # (source name, file) pairs
    except (ValueError, OSError) as e:
        problem = str(e)
    return {"definition": str(path), "metadata": str(meta) if meta else None, "files": files, "problem": problem}
