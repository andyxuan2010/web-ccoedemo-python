# Repository Scan and Validation Report

## Scope

Validated repository structure, Python app syntax/import readiness, auth flow wiring, and deployment automation intent across Azure DevOps and GitHub Actions.

## Files Reviewed

- `app.py`
- `templates/base.html`
- `templates/index.html`
- `templates/profile.html`
- `templates/auth_error.html`
- `.github/workflows/azure-webapp.yml`
- `azure-pipelines.yml`
- `run_from_package.yml`
- `requirements.txt`

## Validation Checks Run

1. `python -m py_compile app.py`
- Result: pass (syntax is valid)

2. `python -c "import app; ..."`
- Result: pass in project virtual environment
- Command used: `.venv\Scripts\python.exe -c "import app; print(bool(app.app))"`
- Output: `True`

3. `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- Result: pass
- Status: required runtime dependencies are installed in `.venv`

## Findings

1. Code structure is coherent for a demo app:
- App factory pattern used.
- Route separation for MSAL and Easy Auth is clear.
- Helper methods normalize claims and isolate auth URL builders.

2. Pipeline design is consistent with multi-target App Service zip-deploy:
- Build + deploy stages are defined.
- The active GitHub Actions and Azure DevOps ZIP-deploy paths build a source ZIP and rely on App Service Oryx build automation from `requirements.txt`.
- The shared Azure DevOps deploy template handles a primary target plus an optional secondary target from the same package.
- The alternate `run_from_package.yml` pipeline still vendors dependencies into `.python_packages` and retains its optional third target.
- Python 3.12 is the configured runtime across the active pipeline definitions.

3. Environment caveat:
- Validation passes in `.venv`. Using a different interpreter (outside `.venv`) can fail if dependencies are not installed there.
- Any prebuilt local package artifacts must match the target interpreter architecture.

## Recommended Next Validation Steps

1. Create/activate virtual environment.
2. Install dependencies from `requirements.txt`.
3. Re-run:
   - `python -m py_compile app.py`
   - `python -c "import app; print(bool(app.app))"`
4. Run app for functional validation:
   - `python app.py`
   - Open `http://localhost:5000`

5. Validate pipeline behavior:
   - optional secondary targets skip cleanly when blank or missing in the main ZIP-deploy flows
   - the alternate `run_from_package.yml` third target also skips cleanly when blank or missing
   - each eligible Linux App Service receives the same packaged artifact

## Key Architecture Notes

- Two auth modes are intentionally supported in parallel for side-by-side comparison.
- Easy Auth mode depends on Azure App Service request headers and cannot be fully simulated locally without header injection.
- Session timeline and auth health panels provide built-in observability for demo and troubleshooting.
