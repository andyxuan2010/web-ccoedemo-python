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
- Dependency vendoring into `.python_packages` matches Linux App Service expectations.
- Primary, secondary, and third App Service targets can be deployed from the same package.
- Python 3.12 should be available locally on the self-hosted runner or in `Agent.ToolsDirectory`; Python 3.11 remains an explicit fallback if 3.12 is unavailable. The pipeline does not rely on unsupported GitHub-registry downloads.
- The application code and Python dependencies are compatible with a 32-bit Python runtime when packages are installed for that target architecture.
- The current pipeline deploys to Linux App Service Python runtimes, so 32-bit support applies to the app itself rather than to the built-in App Service hosting stack.

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
   - secondary and third targets skip cleanly when blank or missing
   - each eligible Linux App Service receives the same packaged artifact

## Key Architecture Notes

- Two auth modes are intentionally supported in parallel for side-by-side comparison.
- Easy Auth mode depends on Azure App Service request headers and cannot be fully simulated locally without header injection.
- Session timeline and auth health panels provide built-in observability for demo and troubleshooting.
