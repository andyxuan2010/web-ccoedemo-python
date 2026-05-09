# Pipeline Guide

This repository currently includes three pipeline definitions:

1. GitHub Actions ZIP deploy in `.github/workflows/azure-webapp.yml`
2. Azure DevOps ZIP deploy with App Service build automation in `azure-pipelines.yml`
3. Azure DevOps Run From Package deploy in `run_from_package.yml`

The first two are the main operational paths for this repo today. The Run From Package pipeline is kept as an alternate Azure DevOps option when immutable package behavior is required.

## At A Glance

| Pipeline | Platform | Build style | Deploy style | Current role |
| --- | --- | --- | --- | --- |
| `.github/workflows/azure-webapp.yml` | GitHub Actions | Package source into `app.zip` | ZIP deploy with Oryx build on App Service | Main GitHub-based CI/CD path |
| `azure-pipelines.yml` | Azure DevOps | Package source into `app.zip` | ZIP deploy with Oryx build on App Service | Main Azure DevOps CI/CD path |
| `run_from_package.yml` | Azure DevOps | Build self-contained package with vendored Python deps | `WEBSITE_RUN_FROM_PACKAGE=1` package-mounted deploy | Optional alternate ADO path |

## 1. GitHub Actions

File: `.github/workflows/azure-webapp.yml`

### Trigger model

- Runs on push to `main`, `dev`, and `sbx`
- Runs on pull requests targeting `main`, `dev`, and `sbx`
- Supports manual `workflow_dispatch` with optional deploy toggle

### Flow

1. Resolve branch context to `prod`, `dev`, or `sbx`
2. Use GitHub-hosted Ubuntu runner and Python `3.12`
3. Stage `app.py`, `requirements.txt`, `templates/`, and `static/`
4. Archive the app into `app.zip`
5. Upload the package as a workflow artifact
6. Run deployment prechecks for credentials and target names
7. Validate package contents and startup command before deploy
8. Sign in with `azure/login`
9. Deploy to up to three App Service targets with ZIP deploy and Oryx build
10. Optionally publish clean snapshots to a stage GitHub repo and an Azure DevOps mirror repo

### Key characteristics

- Uses `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
- Uses `ENABLE_ORYX_BUILD=true`
- Removes `WEBSITE_RUN_FROM_PACKAGE` and `PYTHONPATH` if they are present
- Sets Linux runtime to `PYTHON|3.12`
- Sets startup to `gunicorn ... app:app`
- Skips secondary and third targets safely when blank or not found

## 2. Azure DevOps ZIP Deploy

File: `azure-pipelines.yml`

### Trigger model

- Currently triggers on `main`
- Pull request validation is also scoped to `main`
- Uses the self-hosted Linux pool `IaCRunner`

### Flow

1. Resolve environment and subscription from branch name
2. Resolve a local Python `3.12` interpreter on the self-hosted runner
3. Stage app source files into a package folder
4. Archive the package as `app.zip`
5. Publish the ZIP as pipeline artifact `drop`
6. In deploy stage, check primary, secondary, and third targets separately
7. Download the artifact only when at least one target is eligible
8. Run SCM/Kudu connectivity prechecks
9. Configure Linux runtime and startup command
10. Enable Oryx build settings and deploy the ZIP with Azure CLI

### Key characteristics

- Mirrors the GitHub Actions deployment model closely
- Uses Azure CLI tasks instead of `azure/login`
- Stores target metadata in pipeline variables
- Skips missing optional targets without failing the whole stage
- Best fit when the team wants Azure DevOps as the primary orchestrator

## 3. Azure DevOps Run From Package

File: `run_from_package.yml`

### Trigger model

- Triggers are intentionally disabled right now with `none`
- Uses the same self-hosted Linux pool `IaCRunner`

### Flow

1. Resolve a local Python `3.12` interpreter on the runner
2. Install dependencies into `.python_packages/lib/site-packages`
3. Copy app code and static assets into the package root
4. Archive the full package as `app.zip`
5. Publish the ZIP as pipeline artifact `drop`
6. Deploy to one or more App Services with Azure CLI
7. Set `WEBSITE_RUN_FROM_PACKAGE=1`
8. Set `PYTHONPATH` to the packaged site-packages path
9. Remove Oryx build settings so the app runs from the mounted package

### Key characteristics

- Produces a more self-contained package than the other two pipelines
- Keeps dependencies inside the artifact instead of relying on App Service build
- Uses package-mounted runtime behavior, which is more rigid for Python App Service
- Best reserved for cases where immutable package semantics are required

## Recommended Usage

- Use `.github/workflows/azure-webapp.yml` when the delivery flow is centered on GitHub.
- Use `azure-pipelines.yml` when the delivery flow is centered on Azure DevOps.
- Use `run_from_package.yml` only when the team explicitly wants a packaged dependency bundle and `WEBSITE_RUN_FROM_PACKAGE` behavior.

For a broader comparison of deployment patterns, including Deployment Center and custom containers, see `docs/DEPLOYMENT_METHODS.md`.
