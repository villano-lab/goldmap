# Changelog

All notable changes to goldmap. The format follows [Keep a Changelog](https://keepachangelog.com/), the versions follow [semantic versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-04

The first release. It needs `goldpan` 0.3.0 and `goldsluice` 0.1.0 (both on PyPI): `pip install goldmap`.

### Added

- A local browser app (`python -m goldmap`) that makes the dataset definition and the run-metadata CSV for a goldsluice processing, and checks them with goldpan and goldsluice.
- Tabs Data, Steps, Files and + Detector. Data: scan a folder of dumps, filters on HV, trigger, type, source and length, choose the detector from the registry.
- A steps canvas of draggable boxes: drag a filter's dot onto a step to chain them, numbered run order, Tab completes the grey suggestions.
- Several sources (different detectors or folders) in one processing, a registry chooser with a checkbox per registry folder, and different steps for different sources (`sources = [...]` on a step, definition format 7).
- A + Detector tab that writes a detector into a registry folder.
- Output as Parquet or ROOT (ROOT needs uproot and one detector).
- Validate (`goldsluice check` in a temporary folder), Preview, and Write and check.
- Start from an existing definition, registries and definitions in any folder, Browse… buttons.
- Local only: the server listens on 127.0.0.1, every request needs a token, and the Host header must match.
