# Repository Validation

## Latest Local Scan

Validated on 2026-11-13 against `main` at `ca7064b`:

- Ruff 0.17.2 lint passed
- Ruff formatting check passed (9 files)
- pytest passed (13 tests)
- pip-audit found no known vulnerabilities in `requirements.txt`
- `scripts/validate-github-workflow.ps1` and `scripts/validate-shared-ui.ps1` passed
- `scripts/Build-DocsSite.ps1` and `scripts/Test-DocsSite.ps1` passed (7 documents)
- YAML, JSON, and TOML files parsed cleanly; no merge markers or private keys found
- text files are normalized to LF through `.gitattributes`; `reload-arm-env.ps1` keeps
  its committed CRLF endings
- `docs-manifest.json` is rewritten only when the documented file set changes, so a docs
  build leaves the worktree clean

The checkout also has an `origin2` mirror remote whose version tags reuse names from
`origin` for different Git objects. Fetch branches from that mirror without `--tags`,
or remove/rename the remote if it is no longer part of the publishing workflow; a
blanket `git fetch --all --tags` will report tag-clobber conflicts.

## Automated Gates

GitHub Actions and both Azure Pipelines run the same application gates before packaging:

1. `ruff check .`
2. `ruff format --check .`
3. `pytest`
4. `pip-audit -r requirements.txt`

Runtime and development tools are pinned in `requirements.txt` and
`requirements-dev.txt`. Dependabot monitors Python and GitHub Actions updates.

## Test Coverage

`tests/test_app.py` validates:

- home page rendering and expected navigation
- liveness response and security headers
- rejection of Easy Auth headers outside a trusted boundary
- strict parsing and rejection of malformed Easy Auth principals
- successful trusted Easy Auth claim mapping
- MSAL callback success without bearer-token persistence
- callback error status and one-time flow cleanup
- fail-closed App Service startup without `FLASK_SECRET_KEY`

## Browser Validation

The home page was rendered at desktop and `390x844` mobile viewports. Validation
confirmed:

- centered top navigation
- no horizontal overflow
- no navigation overlap with page content
- no overlapping navigation controls
- all image assets loaded
- no browser console warnings or errors

## Pipeline Validation

- GitHub Actions uses job-scoped permissions and immutable action commit SHAs.
- Azure login uses protected service-principal credentials.
- Azure DevOps deployment stages are explicitly gated:
  - `refs/heads/sbx` -> `DeploySandbox`
  - `refs/heads/dev` -> `DeployDev`
  - `refs/heads/main` -> build validation only
- Pull requests never enter deployment stages.
- Optional targets skip when blank or absent.
- Temporary GitHub-hosted runner SCM access rules are removed in an `always()` step.
- GitHub staging snapshots exclude `.github/`, preventing mirrored workflows and
  Dependabot configuration from creating staging-side automation or pull requests.

## Local Commands

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\pip-audit.exe -r requirements.txt
```

Run locally with an explicit development secret:

```powershell
$env:FLASK_SECRET_KEY = 'replace-for-local-use'
.\.venv\Scripts\python.exe -m flask --app app run
```

`TRUST_EASY_AUTH_HEADERS=true` is for controlled local Easy Auth tests only. Do not
enable it on a directly reachable service outside an authentication proxy.
