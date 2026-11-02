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

The page opens in your browser (the address is also printed). Choose the folder of the dumps and the series, the detector (from the registry), add
the steps (each algorithm asks for its parameters; the ones that belong to the readout are taken from it), check the metadata of each series, name the
dataset and its output folder, then **Preview** or **Write the files and check them**. The last line it prints is the `goldsluice run` command.

| Option | |
|---|---|
| `--registry DIR` | folder of detector records (`goldpan.registry`); repeat for several; `GOLDPAN_REGISTRY` is used too |
| `--series-list CSV` | a CSV with a `series` column and what is known about each series (`nsdf_r76_series.csv`: `HV`, `trigger`, `type`, ...) to prefill the metadata |
| `--root DIR` | a folder of raw dumps to offer (default `~/idx`); repeat for several |
| `--folder DIR` | where the definition and the metadata are written (default: the current folder) |
| `--port N` | the port on 127.0.0.1 (default: any free one) |

## Safety

The app reads folders and writes files for whoever can talk to it, so it listens on `127.0.0.1` only, and answers only the page it served: the page
carries a random token that every request must send back, and the `Host` header must be the server's own address.

## Test

```
python -m pytest
```

The tests use the registry folder of the NSDF-Data checkout that goldpan was installed from, and skip without it.
