# Repository Validation

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
- Azure login uses OIDC workload identity federation.
- Azure DevOps deployment stages are explicitly gated:
  - `refs/heads/sbx` -> `DeploySandbox`
  - `refs/heads/dev` -> `DeployDev`
  - `refs/heads/main` -> build validation only
- Pull requests never enter deployment stages.
- Optional targets skip when blank or absent.
- Temporary GitHub-hosted runner SCM access rules are removed in an `always()` step.

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
