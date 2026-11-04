# Working on goldmap

goldmap uses **Git Flow** and **semantic versioning**, as NSDF-Data does (`RELEASING.md` there).

## Branches

| Branch | What it is |
|---|---|
| `main` | Released code only. Every commit on it is tagged `vX.Y.Z`. |
| `develop` | The integration branch. All work lands here first. |
| `feature/<name>` | One change, made from `develop`, finished by a pull request into `develop`. |
| `release/X.Y.Z` | Made from `develop` to get a release ready (version, `CHANGELOG.md`, last fixes). Finished by a pull request into `main`. |
| `hotfix/X.Y.Z` | An urgent fix made from `main`. Finished by a pull request into `main`, then merged back into `develop`. |

Rules:

- Never commit directly to `main` or `develop`. Make a branch and open a pull request.
- Finish a branch with a **merge commit** (not squash, not rebase). Never force-push.
- Delete a branch only after it is merged, and only one you made.
- A change a user would notice gets a line under `[Unreleased]` in `CHANGELOG.md`.
- Only a `release/*` or `hotfix/*` branch changes the version (`pyproject.toml` and `goldmap/__init__.py`, which must agree) or renames `[Unreleased]`.
- The tests (`python -m pytest`) run on Linux, Windows and macOS for every pull request; they must pass.

## A feature

```
git switch develop && git pull
git switch -c feature/<name>
# ... work, commit ...
git push -u origin feature/<name>
# open a pull request into develop
```

## A release

```
git switch develop && git pull
git switch -c release/X.Y.Z
# set the version in pyproject.toml and goldmap/__init__.py, rename [Unreleased] in CHANGELOG.md to [X.Y.Z] - date
# open a pull request into main; when it is merged:
git tag vX.Y.Z <the merge commit on main> && git push origin vX.Y.Z
# merge main back into develop (a pull request)
```

## Publishing to PyPI

goldmap is published as `goldmap` (https://pypi.org/project/goldmap/) by `.github/workflows/publish-goldmap.yml`. It runs when a tag `vX.Y.Z` is pushed: it checks that the tag, the two version numbers and the changelog agree (`python tools/check_release.py vX.Y.Z` does the same on your computer) and that the tag is on `main`, builds the wheel and the source archive, installs the wheel in a clean environment (goldpan and goldsluice come from PyPI) and starts it, and then uploads. No token is stored anywhere: PyPI trusts the workflow (a "trusted publisher"), and the upload waits for the maintainer to approve the `pypi` environment. Run by hand (Actions, *Publish goldmap*, *Run workflow*) it is a dry run that never uploads.

One-time setup (maintainer): GitHub, *Settings*, *Environments*, new environment `pypi`, *Required reviewers* yourself, and under *Deployment branches and tags* allow only tags matching `v*`. PyPI, project `goldmap`, *Manage*, *Publishing*, *Add a new publisher*, GitHub: owner `villano-lab`, repository `goldmap`, workflow `publish-goldmap.yml`, environment `pypi`. Then run the dry run once. A version on PyPI can never be replaced, so run the dry run first. **An AI agent never pushes a release tag.**

goldmap depends on `goldpan` and `goldsluice`, so a release of goldmap needs a released goldpan (and goldsluice) that has what it uses; the `dependencies` in `pyproject.toml` say which.
