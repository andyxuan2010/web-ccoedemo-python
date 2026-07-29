# Pipeline Guide

This repository currently includes three pipeline definitions:

1. GitHub Actions ZIP deploy in `.github/workflows/azure-webapp.yml`
2. Azure DevOps ZIP deploy with App Service build automation in `azure-pipelines.yml`
3. Azure DevOps Run From Package deploy in `run_from_package.yml`

The first two are the main operational paths for this repo today. The Run From Package pipeline remains the alternate Azure DevOps option when immutable package behavior is required.

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

1. Run `deployment-precheck` to validate branch-specific Azure OIDC and target inputs
2. Run Ruff, pytest, and pip-audit on Python `3.12`
3. Build and upload `app.zip` with seven-day artifact retention
4. Create an annotated semantic version tag on non-PR success
5. Run `pre-publish-check` for optional GitHub and ADO mirror publishing
6. Log into Azure through GitHub OIDC using branch-specific client ID, tenant ID, and subscription ID
7. Deploy to the branch-specific primary App Service and optional secondary target
8. Optionally publish clean snapshots to a stage GitHub repo and an Azure DevOps mirror repo

### Key characteristics

- Uses short-lived OIDC tokens; each GitHub Environment must have a matching federated identity credential
- Maps branches deterministically to protected environments: `main` -> `prod`,
  `dev` -> `dev`, and `sbx` -> `sbx`
- Defaults `GITHUB_TOKEN` to read-only and grants `contents: write` only to tag creation
- Pins third-party actions to full commit SHAs
- Keeps semantic tag creation aligned with the Azure DevOps logic
- Skips optional secondary targets safely when blank or not found
- Uses `az webapp deploy --type zip` with Oryx build automation enabled

## 2. Azure DevOps ZIP Deploy

File: `azure-pipelines.yml`

### Trigger model

- Triggers on `main`, `dev`, and `sbx`
- Pull request validation also covers `main`, `dev`, and `sbx`
- Uses the Microsoft-hosted `Azure Pipelines` pool on `ubuntu-latest`

### Flow

1. Run Ruff, pytest, and pip-audit
2. Build the Python app package once and publish it as artifact `drop`
3. Run `DeploySandbox` only for `refs/heads/sbx`
4. Run `DeployDev` only for `refs/heads/dev`
5. Build-validate `main` without a checked-in production deployment stage
6. Use `azure-pipelines/deploy-stage.yml` as the shared deploy-stage template

### Deploy-stage behavior

Each deploy stage:

1. Checks the primary target
2. Checks the optional secondary target
3. Downloads `drop/app.zip` only when at least one target is deployable
4. Runs SCM/Kudu DNS, TCP `443`, and HTTPS preflight checks
5. Configures Linux runtime `PYTHON|3.12`
6. Sets Gunicorn startup to `app:app`
7. Removes `WEBSITE_RUN_FROM_PACKAGE` and `PYTHONPATH`
8. Enables `SCM_DO_BUILD_DURING_DEPLOYMENT=true` and `ENABLE_ORYX_BUILD=true`
9. Deploys with Azure CLI ZIP deploy

### Stage-specific targets

- `DeploySandbox`
  - service connection: `sc-platform-sbx`
  - primary app: `web-platform-cc-sbx-python`
- `DeployDev`
  - service connection: `sc-platform-dev`
  - primary app: `web-platform-eus-dev-python`

### Key characteristics

- Uses the shared `IaC/template` repo through the `templates` alias
- The external template reference currently follows `refs/heads/main`; protect that
  repository and pin a reviewed tag or commit before treating it as a hardened control
- Uses compile-time service connection values so Azure DevOps validates them correctly
- Keeps the active shared deploy template focused on the primary target plus an optional secondary target
- Avoids the old tag-creation `141` failure pattern

## 3. Azure DevOps Run From Package

File: `run_from_package.yml`

### Trigger model

- Triggers are intentionally disabled with `none`
- It remains the alternate/manual pipeline

### Key characteristics

- Packages dependencies into the artifact
- Runs the same Ruff, pytest, and pip-audit gates before packaging
- Sets `WEBSITE_RUN_FROM_PACKAGE=1`
- Includes optional primary, secondary, and third App Service targets
- Keeps a more immutable delivery model than the main ZIP-deploy pipelines

## Recommended Usage

- Use `.github/workflows/azure-webapp.yml` when the delivery flow is centered on GitHub.
- Use `azure-pipelines.yml` when the delivery flow is centered on Azure DevOps.
- Use `run_from_package.yml` only when the team explicitly wants packaged dependencies and `WEBSITE_RUN_FROM_PACKAGE` behavior.

For a broader comparison of deployment patterns, including Deployment Center and custom containers, see `docs/DEPLOYMENT_METHODS.md`.
