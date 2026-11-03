"""The form of the page -> the dataset definition and the run-metadata table -> the files.

The form is plain JSON (what the page sends)::

    {"name": "r76-82v", "output": "C:/NSDF/goldsluice-output/r76-82v", "description": "...",
     "registry": ["C:/Users/me/NSDF-Data/registry"],
     "sources": [{"name": "side2", "format": "idx", "root": "C:/NSDF/idx", "series": ["07221111_2153", ...], "detector": "NAI-S2"}],
     "steps": [{"algorithm": "peak", "channels": "role:phonon", "params": {"glitch_samples": "@readout.glitch_samples", "amps_per_adc": 1.5e-9}},
               {"algorithm": "lowpass", "name": "lp", "channels": "role:phonon", "params": {...}}],
     "metadata": [{"series": "07221111_2153", "hv_v": -82.2, "trigger": "DCRC1pB 10", "trigger_value": 10}, ...]}

`open_definition` goes the other way: an existing definition file -> the form, to start another processing from it.
`goldpan.dataset` writes and checks the definition and `goldpan.runmeta` the table; nothing here knows the rules of either.
"""
import contextlib
import glob as globmod
import importlib.util
import inspect
import os
import re
import shutil
import tempfile
from pathlib import Path

from goldpan import dataset, runmeta

NUMERIC_COLUMNS = ("hv_v", "trigger_value", "duration_min")
"""Columns of the metadata table that are numbers; the others are text."""
METADATA_COLUMNS = ("hv_v", "trigger", "trigger_value", "type", "source_shield", "duration_min")
"""The columns of the metadata table the page shows, after `series` (its `META`)."""
METADATA_FILE = "series.csv"
"""The file name of the metadata table, written beside the definition."""


def _posix(path) -> str:
    return str(path).replace("\\", "/")


def _registry_path(folder: Path, registry: str, absolute: bool = False) -> str:
    """The registry folder as the definition writes it: relative to the folder of the definition when that is close, else in full. A relative
    `registry` (``--registry registry``) is taken from the folder goldmap was started in, as it is read; written as given it would be read
    from the folder of the definition instead."""
    given = Path(registry).expanduser()
    given = given if given.is_absolute() else given.resolve()
    if absolute:
        return _posix(given.resolve())
    try:
        relative = _posix(os.path.relpath(given, folder))
    except ValueError:                                                  # another drive (Windows)
        return _posix(given)
    return relative if relative.count("../") <= 1 else _posix(given)     # a path that climbs far up is clearer written in full


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
    for key in ("name", "input", "suffix", "sources"):                    # `sources`: the names of the sources the step runs on (all, when it is not there)
        if form_step.get(key):
            out[key] = form_step[key]
    if form_step.get("params"):
        out["params"] = dict(form_step["params"])
    return out


def definition(form: dict, folder, absolute: bool = False) -> dict:
    """The dataset definition (a mapping with the layout of the file, for `goldpan.dataset.dumps`) that the form describes, for a file in `folder`.
    With `absolute` the registry folders are written in full, for a definition that is not going to stay in `folder`."""
    folder = Path(folder).expanduser().resolve()
    if not form.get("name") or not form.get("output"):
        raise ValueError("give the dataset a name and an output folder")
    head = {"name": form["name"], "output": _posix(form["output"])}
    if form.get("description"):
        head["description"] = form["description"]
    if form.get("registry"):
        head["registry"] = [_registry_path(folder, r, absolute) for r in form["registry"]]
    if form.get("metadata"):
        head["metadata"] = METADATA_FILE
    if form.get("output_format") == "root":
        if len({s.get("detector") for s in form.get("sources", [])}) > 1:
            raise ValueError("ROOT output is for one detector only (one zip<N> tree): use Parquet, or make one definition per detector")
        head["output_format"] = "root"
        if form.get("root_detector") not in (None, ""):
            head["root_detector"] = _number(form["root_detector"], "the ROOT detector number", int)
    if not form.get("sources"):
        raise ValueError("add at least one source")
    return {"dataset": head, "sources": [_source(s, i) for i, s in enumerate(form["sources"])],
            "processing": [_step(s, i) for i, s in enumerate(form.get("steps", []))]}


def table(rows: list) -> dict:
    """The metadata table (``{column: values}``, `series` first) of the rows the form gives (``[{"series": ..., "hv_v": ...}, ...]``)."""
    if not rows:
        raise ValueError("the metadata table has no rows")
    columns = ["series"] + list(dict.fromkeys(k for r in rows for k in r if k != "series"))      # in the order they first appear
    out = {}
    for c in columns:
        values = [r.get(c) for r in rows]
        given = [v for v in values if v not in (None, "")]
        if c in NUMERIC_COLUMNS or (given and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in given)):    # a number column of an opened table stays one
            values = [None if v in (None, "") else float(v) for v in values]
        else:
            values = [None if v in (None, "") else str(v) for v in values]
        if all(v is None for v in values):
            continue                                                    # a column nobody filled in is not written
        out[c] = values
    return out


def _rows(columns: dict) -> list:
    """A table (``{column: values}``, as `goldpan.runmeta.read_table` gives it) -> its rows, an empty cell (NaN or "") left out."""
    rows = []
    for k in range(len(columns["series"])):
        row = {}
        for c, values in columns.items():
            v = values[k]
            v = v.item() if hasattr(v, "item") else v
            if not (v is None or v == "" or (isinstance(v, float) and v != v)):
                row[c] = v
        rows.append(row)
    return rows


def _merged(path: Path, rows: list) -> list:
    """`rows`, after the rows of the other series in the metadata table already at `path`: several definitions in one folder share the file,
    so writing one must not take away the series of the others. A series in `rows` replaces its old row."""
    if not path.exists():
        return rows
    mine = {r["series"] for r in rows}
    return [r for r in _rows(runmeta.read_table(path)) if r["series"] not in mine] + rows


def header(form: dict) -> str:
    return f"Made with goldmap. Check:  python -m goldsluice check {form['name']}.dataset.toml"


@contextlib.contextmanager
def _folder_for_check(folder: Path, keep: bool):
    """`folder`, made if it does not exist, for goldpan's check of a definition that will be in it: a registry written relative to it
    (``../registry``) is looked up through it, and Linux and macOS cannot go through ``..`` of a folder that is not there. What was made is
    removed again unless `keep`, or when the check fails, so a refused form (and a preview) leaves nothing behind."""
    top = None
    for p in [folder, *folder.parents]:                                   # the outermost folder that has to be made
        if p.exists():
            break
        top = p
    folder.mkdir(parents=True, exist_ok=True)
    try:
        yield folder
    except BaseException:
        if top is not None:
            shutil.rmtree(top, ignore_errors=True)
        raise
    if top is not None and not keep:
        shutil.rmtree(top, ignore_errors=True)


def preview(form: dict, folder) -> str:
    """The text of the definition file, checked by goldpan; `ValueError` says what is wrong. Nothing is written."""
    folder = Path(folder).expanduser().resolve()
    with _folder_for_check(folder, keep=False):
        return dataset.dumps(definition(form, folder), base=folder, header=header(form))


def validate(form: dict, folder=None) -> dict:
    """Check the form without writing anything into the user's folders: the definition is made in a temporary folder (with the registry folders in full),
    goldpan checks it as it does when it loads a file, and goldsluice's `check` looks for the raw files and for an output folder inside a repository.
    Returns ``{"ok", "files", "series", "steps", "problem"}``; `ValueError` when the form itself is refused by goldpan."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if form.get("metadata_rows"):
            form = {**form, "metadata": True}
        spec = definition(form, tmp, absolute=True)
        text = dataset.dumps(spec, base=tmp)
        if form.get("metadata_rows"):
            runmeta.write_table(tmp / METADATA_FILE, table(form["metadata_rows"]))
        path = tmp / "validate.dataset.toml"
        path.write_text(text, encoding="utf-8", newline="\n")
        files, problem = [], None
        try:
            from goldsluice import batch
            files = batch.check(path, allow_output_in_repo=False)
        except (ValueError, OSError) as e:
            problem = str(e)
        if problem is None and form.get("output_format") == "root" and importlib.util.find_spec("uproot") is None:
            problem = "ROOT output needs the package uproot (python -m pip install uproot, or goldpan[root])"
    return {"ok": problem is None, "files": len(files), "series": sum(len(s["series"]) for s in form["sources"]), "steps": len(form.get("steps", [])), "problem": problem}


def write(form: dict, folder) -> dict:
    """Write `<name>.dataset.toml` (and `series.csv` when the form has metadata rows) into `folder`, then ask goldsluice to check the definition.
    Returns ``{"definition", "metadata", "files", "problem"}``: the paths written, the raw files that were found, and why the check failed
    (`None` if it passed). A form that goldpan refuses writes nothing and raises `ValueError`."""
    folder = Path(folder).expanduser().resolve()
    if form.get("metadata_rows"):
        form = {**form, "metadata": True}
    spec = definition(form, folder)
    with _folder_for_check(folder, keep=True):                                # made if it does not exist; removed again if goldpan refuses
        text = dataset.dumps(spec, base=folder, header=header(form))         # refuse before anything is written
    meta = None
    if form.get("metadata_rows"):
        meta = folder / METADATA_FILE
        runmeta.write_table(meta, table(_merged(meta, form["metadata_rows"])))
    path = folder / f"{form['name']}.dataset.toml"
    path.write_text(text, encoding="utf-8", newline="\n")
    files, problem = [], None
    try:
        from goldsluice import batch
        files = [_posix(item[-1]) for item in batch.check(path, allow_output_in_repo=False)]      # (source name, file) pairs
    except (ValueError, OSError) as e:
        problem = str(e)
    return {"definition": str(path), "metadata": str(meta) if meta else None, "files": files, "problem": problem}


# ---- an existing definition -> the form, to start another processing from it

_DUMP = re.compile(r"^(\d{8}_\d{4})_F\d{4}$")
_SERIES_IN_PATTERN = re.compile(r"(\d{8}_\d{4})_F")


def _same_folder(a, b) -> bool:
    try:
        return Path(a).expanduser().resolve() == Path(b).expanduser().resolve()
    except OSError:
        return False


def _open_source(raw: dict, source, notes: list) -> dict:
    """One `[[sources]]` table -> a source of the form: the folder of its dumps and the series they belong to, found on the disk.
    A pattern that matches nothing here (the data are on another computer) still gives its series when the pattern names them."""
    for key in ("readout", "read"):
        if key in raw:
            raise ValueError(f"source {source.name!r} sets {key!r} in the file; goldmap takes the readout and the channels from the registry's detector "
                             "and could not keep it. Edit this definition by hand, or move those into a registry record")
    if source.format != "idx":
        raise ValueError(f"source {source.name!r}: goldmap knows the idx format only, not {source.format!r}")
    dumps, folders, missing = [], [], []
    for pattern in source.patterns:
        expanded = Path(pattern).expanduser()
        expanded = expanded if expanded.is_absolute() else source.base / expanded
        found = [Path(f) for f in sorted(globmod.glob(str(expanded)))] if any(ch in pattern for ch in "*?[") else ([expanded] if expanded.exists() else [])
        found = [f for f in found if _DUMP.match(f.name)]
        if found:
            dumps += found
        else:
            missing.append(pattern)
        folders.append(expanded.parent)
    series = sorted({_DUMP.match(d.name).group(1) for d in dumps})
    for pattern in missing:
        named = _SERIES_IN_PATTERN.search(Path(pattern).name)
        if named:
            series = sorted(set(series) | {named.group(1)})
        notes.append(f"source {source.name!r}: {pattern} matches no dump on this computer" + ("" if named else ", so its series are not known"))
    roots = sorted({_posix(d.parent.resolve()) for d in dumps} or {_posix(f.resolve()) for f in folders})
    if len(roots) > 1:
        raise ValueError(f"source {source.name!r} reads dumps from several folders ({', '.join(roots)}); goldmap gives a source one folder: "
                         "split it into one source per folder by hand")
    return {"name": source.name, "format": source.format, "root": roots[0] if roots else "", "series": series, "detector": source.detector}


def open_definition(path, registries=(), use=None) -> dict:
    """The form (the JSON the page sends, see the top of this module) of the definition file `path` and of its run metadata, so that a processing
    can start from an existing one. goldpan loads and checks the file first. Returns ``{"form", "notes"}``: `notes` say what could not be carried
    over as it is (a registry goldmap was not started with, a series not on this computer, a metadata column the page does not show).
    `registries` are the registry folders goldmap reads; the form names those of them that the definition names. Another folder the definition
    names is picked up with `use(folder)` (which returns the name goldmap gives it) when one is given.
    `ValueError` for a file goldmap cannot represent (a source that sets its own readout or channels, another format, an unknown algorithm)."""
    path = Path(path).expanduser().resolve()
    spec = dataset.load(path)
    raw, notes = spec.raw, []
    head = raw.get("dataset", {})
    form = {"name": spec.name, "output": head.get("output", ""), "description": head.get("description", ""), "folder": _posix(path.parent),
            "output_format": spec.output_format, "root_detector": head.get("root_detector", "")}
    wanted = [path.parent / Path(r).expanduser() for r in head.get("registry", [])]
    form["registry"] = [r for r in registries if any(_same_folder(r, w) for w in wanted)]
    for w in wanted:
        if not any(_same_folder(r, w) for r in registries):
            if use is not None and w.is_dir():                         # goldpan loaded the file, so the folder is a registry it can read
                form["registry"].append(use(_posix(w.resolve())))
                notes.append(f"picked up the registry {_posix(w.resolve())}, which the definition names")
            else:
                notes.append(f"the definition names the registry {_posix(w.resolve())}, which goldmap does not read: use it under Registries on the Data tab")
    form["sources"] = [_open_source(r, s, notes) for r, s in zip(raw.get("sources", []), spec.sources)]
    from goldsluice import ALGORITHMS
    form["steps"] = []
    for i, step in enumerate(raw.get("processing", [])):
        algorithm = step.get("algorithm")
        if algorithm not in ALGORITHMS:
            raise ValueError(f"step {i + 1}: this goldsluice has no algorithm {algorithm!r} (it has {', '.join(sorted(ALGORITHMS))}); "
                             "rebuild goldsluice from an NSDF-Data checkout that has it (maturin develop --release in goldsluice/) and start goldmap again")
        known = list(inspect.signature(ALGORITHMS[algorithm].problem).parameters)[1:]
        extra = sorted(set(step.get("params", {})) - set(known))
        if extra:
            raise ValueError(f"step {i + 1} ({algorithm}): parameter(s) {extra} that this goldsluice's {algorithm} does not take ({', '.join(known)})")
        form["steps"].append({k: step[k] for k in ("algorithm", "channels", "params", "name", "input", "suffix", "sources") if k in step})
    table_ = spec.run_metadata()
    if table_ is not None:
        hidden = [c for c in table_ if c != "series" and c not in METADATA_COLUMNS]
        if hidden:
            notes.append(f"the run metadata also has column(s) {', '.join(hidden)}, which the page does not show; they are written back as they are")
        form["metadata_rows"] = _rows(table_)
    return {"form": form, "notes": notes}


# ---- a detector for the registry

def _number(value, name, kind=float):
    if value in (None, ""):
        raise ValueError(f"{name}: give a number")
    try:
        return kind(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: {value!r} is not a number") from None


def _optional_int(value, name):
    return None if value in (None, "") else _number(value, name, int)


def detector_records(form: dict) -> tuple:
    """``(detector, readout)`` from the detector form: each is ``(name, table)`` for `goldpan.registry`, the readout `None` when the detector uses one
    that exists. The form: ``{"name", "number", "description", "status", "evidence", "series": [...], "readout": "<name>" or None,
    "new_readout": {"name", "pretrigger_samples", "glitch_samples", "sample_period_s", "status", "evidence"} or None,
    "channels": [{"name", "detector", "input", "role"}]}`` (the idx format: ``detector`` is the index of the board in the dump, ``input`` the channel on it)."""
    name = (form.get("name") or "").strip()
    if not name:
        raise ValueError("give the detector a name")
    readout = None
    new = form.get("new_readout")
    if new:
        rname = (new.get("name") or "").strip()
        if not rname:
            raise ValueError("give the new readout a name")
        table = {"pretrigger_samples": _number(new.get("pretrigger_samples"), "pretrigger_samples", int),
                 "glitch_samples": _number(new.get("glitch_samples"), "glitch_samples", int),
                 "sample_period_s": _number(new.get("sample_period_s"), "sample_period_s"),
                 "status": new.get("status") or "", "evidence": (new.get("evidence") or "").strip()}
        readout = (rname, table)
        readout_name = rname
    else:
        readout_name = form.get("readout") or None
    table = {}
    for key in ("number", "type_code", "tower", "plane"):
        value = _optional_int(form.get(key), key)
        if value is not None:
            table[key] = value
    if readout_name:
        table["readout"] = readout_name
    table["status"] = form.get("status") or ""
    table["evidence"] = (form.get("evidence") or "").strip()
    if (form.get("description") or "").strip():
        table["description"] = form["description"].strip()
    if form.get("series"):
        table["series"] = [s.strip() for s in form["series"] if s.strip()]
    channels = [c for c in form.get("channels", []) if (c.get("name") or "").strip()]
    if channels:
        names = [c["name"].strip() for c in channels]
        if len(set(names)) != len(names):
            raise ValueError("a channel name is used twice")
        table["idx"] = {"channels": {c["name"].strip(): [_number(c.get("detector"), f"{c['name']}: detector", int), _number(c.get("input"), f"{c['name']}: input", int)]
                                     for c in channels},
                        "roles": {c["name"].strip(): (c.get("role") or "").strip() for c in channels if (c.get("role") or "").strip()}}
        if not table["idx"]["roles"]:
            del table["idx"]["roles"]
    return (name, table), readout


def _registry_module():
    from goldpan import registry
    if not hasattr(registry, "add_record"):
        raise ValueError("this goldpan is too old to add a detector (goldpan.registry.add_record came with NSDF-Data pull request 200): "
                         f"update the NSDF-Data checkout that {registry.__file__} belongs to (merge develop into its branch), then start goldmap again")
    return registry


def _plain(error: ValueError) -> ValueError:
    """goldpan's message without the 'the new record: ' it starts with (there is no file to name)."""
    return ValueError(str(error).replace("the new record: ", "", 1))


def detector_preview(form: dict) -> str:
    """The text that would be added to the registry (the readout first, when the form makes one), checked by goldpan."""
    registry = _registry_module()
    detector, readout = detector_records(form)
    try:
        parts = ([registry.record_text("readouts", *readout)] if readout else []) + [registry.record_text("detectors", *detector)]
    except ValueError as e:
        raise _plain(e) from None
    return "\n".join(parts)


def detector_add(form: dict, folder) -> dict:
    """Add the detector (and its new readout) to the registry folder `folder`. Nothing is written unless both are accepted: the names are checked
    against the folder first. Returns ``{"files": [the files written]}``."""
    registry = _registry_module()
    detector, readout = detector_records(form)
    detector_preview(form)                                              # goldpan's own checks, before anything is written
    reg = registry.load(Path(folder).expanduser(), use_environment=False) if Path(folder).expanduser().is_dir() else registry.Registry()
    if detector[0] in reg.detectors():
        raise ValueError(f"the registry already has a detector named {detector[0]!r}")
    if readout and readout[0] in reg.readouts():
        raise ValueError(f"the registry already has a readout named {readout[0]!r}")
    files = []
    if readout:
        files.append(str(registry.add_record(folder, "readouts", *readout)))
    files.append(str(registry.add_record(folder, "detectors", *detector)))
    return {"files": files}
