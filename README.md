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
   diagram warns when a detector has none. The definition is written with one `[[sources]]` per source. Not possible in one definition: different steps for
   different detectors (make two definitions) and ROOT output for several detectors.
2. **Steps:** the processing as boxes on a canvas. Add a step, drag it where you like, click it to set its parameters (the ones that belong to the readout are taken
   from it). Drag from a filter's right-hand dot onto a step to make that step read the filtered trace (double-click the line to undo). The green boxes show the
   quantities that end up in the output.
3. **Files:** name the dataset and its output folder, choose the **output format** (Parquet, which goldpan reads back, or ROOT files in the layout of the collaboration's RQ files; ROOT
   needs uproot, one detector only, and the detector's number N from the registry unless you give one), check the metadata of each series, then **Validate** (runs `goldsluice check` on the definition and writes nothing), **Preview** or **Write and check**. The last line it prints is the
   `goldsluice run` command.

In an empty box, **Tab** fills in the grey suggestion.

| Option | |
|---|---|
| `--registry DIR` | folder of detector records (`goldpan.registry`); repeat for several; `GOLDPAN_REGISTRY` is used too |
| `--series-list CSV` | a CSV with a `series` column and what is known about each series (`nsdf_r76_series.csv`: `HV`, `trigger`, `type`, ...) to prefill the metadata |
| `--root DIR` | a folder of raw dumps to offer (default `~/idx`); repeat for several |
| `--folder DIR` | where the definition and the metadata are written (default: the current folder) |
| `--port N` | the port on 127.0.0.1 (default: any free one) |

## A detector that is not in the registry

The **+ Detector** tab describes a new detector (name, number, readout, channel map, and the evidence for each) and adds it to a registry folder with
`goldpan.registry.add_record`, which checks it exactly as the reader does and does not touch the rest of the file. Without `--registry` the record goes to a
`registry` folder inside `--folder`. The page only writes to the registry folders it was started with. To share a detector, add it to the NSDF-Data registry through a pull request.

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
