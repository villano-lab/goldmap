# goldmap

Lay out a goldsluice processing in the browser. A local app: it looks at the raw data on your disk, asks you for the detector and the processing
steps, and writes the two files a `goldsluice run` needs:

- the **dataset definition** (`<name>.dataset.toml`, the format of `goldpan.dataset`), and
- the **run metadata** (`series.csv`: HV, trigger setting and so on per series, `goldpan.runmeta`), which the definition refers to.

goldpan and goldsluice do the checking, so a file goldmap writes is one they accept: the definition is written with `goldpan.dataset.dump` (checked
exactly as `load` checks a file) and then `goldsluice check` lists the raw files it would process. goldmap sits on top of both; nothing in them
depends on it (NSDF-Data issue 162).

## Use

```
python -m goldmap --registry ~/NSDF-Data/registry --series-list ~/NSDF-Data/data_analysis/R76/series_lists/nsdf_r76_series.csv --root C:/NSDF/idx --folder ~/survey
```

The page opens in your browser (the address is also printed). The page has three steps, one tab each:

1. **Data:** the folder of the dumps and the series in it. Narrow them with filters on what is known about each series (HV range, trigger, type, source, length) and
   choose all that are shown; pick the detector from the registry.
   **Registries:** under the detector box, a checkbox per registry folder (the ones given with `--registry`) says which are in use. Only the detectors and readouts of the
   ticked folders are offered, and the definition names only those. A registry that a source's detector comes from cannot be switched off until that source uses
   another detector.
   **Several sources:** raw data from different detectors (or different folders) are separate *sources*. **+ Add a source** gives each its own folder, series, filters and
   detector (the chips above the folder box switch between them). All the registry folders you started goldmap with are merged, so the detectors of
   two registries can be used in one processing. The steps apply to every source: `role:phonon` means each detector's own phonon channels, and a box on the
   diagram warns when a detector has none. The definition is written with one `[[sources]]` per source. **Different steps for different sources:** every raw-data box starts out connected to every step. Double-click a line from a raw-data box to take that
   source off the step, or untick it under *Runs on* in the step's card; drag from the raw-data box's right-hand dot onto a step to put it back. The definition then gets
   `sources = [...]` on that step (this needs a goldpan with definition format 7). A step that reads a filter can only run where the filter runs, and every source needs at least one
   step; removing a source removes the steps that ran on it alone. ROOT output is for one detector only.
2. **Steps:** the processing as boxes on a canvas. Add a step, drag it where you like, click it to set its parameters (the ones that belong to the readout are taken
   from it). Drag from a filter's right-hand dot onto a step to make that step read the filtered trace (double-click the line to undo). The green boxes show the
   quantities that end up in the output.
3. **Files:** name the dataset and its output folder, choose the **output format** (Parquet, which goldpan reads back, or ROOT files in the layout of the collaboration's RQ files; ROOT
   needs uproot, one detector only, and the detector's number N from the registry unless you give one), check the metadata of each series, then **Validate** (runs `goldsluice check` on the definition and writes nothing), **Preview** or **Write and check**. The last line it prints is the
   `goldsluice run` command.

In an empty box, **Tab** fills in the grey suggestion.

**Start from an existing definition**, at the top of the Data tab, opens a `.dataset.toml` (the ones in `--folder` are listed; any other path works too)
and fills the three tabs from it: its sources and series, its steps with their parameters and links, its run metadata and its names. Change what you
need, give it a new name on the Files tab and write it; writing it under the old name replaces the file you opened. goldpan loads the file first, so
one it refuses does not open.

- The series of a source are found on the disk from its `paths` or `glob`, so a `glob` over many series opens as the series it matches. A pattern
  that matches nothing on this computer is reported, and its series stay chosen when the pattern names them.
- A registry the definition names that goldmap does not read yet is picked up (and said so).
- Columns of the run metadata that the page does not show (`dumps_in_output`, `from`, ...) are kept and written back as they were.
- A definition goldmap cannot represent is refused with the reason: a source that sets its own `readout` or `read` (goldmap takes those from the
  registry), a format other than idx, dumps of one source in several folders, or an algorithm or parameter the installed goldsluice does not have.

Several definitions in one folder share its `series.csv`, so writing one keeps the rows of the other series already in the file and replaces only the
rows of the series it chose.

| Option | |
|---|---|
| `--registry DIR` | folder of detector records (`goldpan.registry`); repeat for several; `GOLDPAN_REGISTRY` is used too |
| `--series-list CSV` | a CSV with a `series` column and what is known about each series (`nsdf_r76_series.csv`: `HV`, `trigger`, `type`, ...) to prefill the metadata |
| `--root DIR` | a folder of raw dumps to offer (default `~/idx`); repeat for several |
| `--folder DIR` | where the definition and the metadata are written (default: the current folder); the Files tab can name another, which is made if it does not exist |
| `--port N` | the port on 127.0.0.1 (default: any free one) |

## Registries

goldmap reads the registry folders given with `--registry`. Two more ways need no restart: **Use a registry from another folder**, under *Registries*
on the Data tab, picks up an existing registry folder (goldpan reads it, so a folder with no records or a broken one is refused), and the
**+ Detector** tab makes a registry by writing a detector into a new folder. Either folder is read from then on and ticked; the tick says which
registries a processing uses, and the definition names only the ticked ones.

Both folder boxes have a **Browse…** button that opens the computer's own folder window (a browser does not tell a page the path of a folder it
picks, so goldmap opens the window itself, with tkinter in a separate process; it can appear behind the browser). Where it cannot open (no tkinter,
no display), the path can still be typed.

## A detector that is not in the registry

The **+ Detector** tab describes a new detector (name, number, readout, channel map, and the evidence for each) and adds it to a registry folder with
`goldpan.registry.add_record`, which checks it exactly as the reader does and does not touch the rest of the file. Without `--registry` the record goes to a
`registry` folder inside `--folder`; the box under the form names any other folder (the ones given with `--registry` are suggested). A folder that does
not exist is made, and a folder that was not a registry yet is read as one from then on and ticked for the processing, so the registry and the
definitions can live in different places. To share a detector, add it to the NSDF-Data registry through a pull request.

## Safety

The app reads folders and writes files for whoever can talk to it, so it listens on `127.0.0.1` only, and answers only the page it served: the page
carries a random token that every request must send back, and the `Host` header must be the server's own address.

## Test

```
python -m pytest
```

The tests use the registry folder of the NSDF-Data checkout that goldpan was installed from, and skip without it.

## License

MIT, see [LICENSE](LICENSE).

## Contributing

Git Flow: work on `feature/*` branches from `develop`, pull requests into `develop`, releases through `release/X.Y.Z` into `main`. See `CONTRIBUTING.md`; changes are listed in `CHANGELOG.md`.
