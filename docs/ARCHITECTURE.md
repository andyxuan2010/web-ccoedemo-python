# Architecture Overview

## Purpose

This project demonstrates two authentication integration patterns for Microsoft Entra ID in a single Flask web app:

- `MSAL` (app-owned OpenID Connect authorization code flow)
- `Easy Auth` (Azure App Service-owned authentication with identity headers)

## Components

- `Flask app` (`app.py`)
- `MSAL Confidential Client` (`msal.ConfidentialClientApplication`)
- `Azure App Service Easy Auth` endpoints (`/.auth/login/aad`, `/.auth/logout`)
- `Jinja UI templates` in `templates/`
- `Static assets` in `static/img/`
- `GitHub Actions workflow` in `.github/workflows/azure-webapp.yml`
- `Azure DevOps pipelines` in `azure-pipelines.yml` and `run_from_package.yml`

## Runtime Architecture

### Application Layer

- App initializes through `create_app()`.
- `ProxyFix` is enabled for reverse-proxy correctness on App Service.
- Session config:
  - `SESSION_COOKIE_HTTPONLY = True`
  - `SESSION_COOKIE_SAMESITE = Lax`
  - `SESSION_COOKIE_SECURE = True` when running on App Service
  - `PERMANENT_SESSION_LIFETIME = 30 minutes`

### Authentication Modes

1. `MSAL mode`
- Start at `/login/msal`
- Build auth flow via `initiate_auth_code_flow(...)`
- Callback at `AAD_REDIRECT_PATH` (default `/auth/callback`)
- Exchange code for token using `acquire_token_by_auth_code_flow(...)`
- Store `id_token_claims` and access token in session

2. `Easy Auth mode`
- Start at `/login/easyauth`
- Redirect to App Service `/.auth/login/aad`
- App reads `X-MS-CLIENT-PRINCIPAL` request header
- Decode Base64 principal JSON and normalize claims to a dictionary

## Route Map

- `/`: Home page with mode selection cards
- `/login` -> `/login/msal`
- `/login/msal`: Starts MSAL sign-in
- `/login/easyauth`: Starts Easy Auth sign-in
- `/auth/callback` (configurable): MSAL callback handler
- `/profile` -> `/profile/msal`
- `/profile/msal`: Profile from session MSAL claims
- `/profile/easyauth`: Profile from Easy Auth header claims
- `/logout` -> `/logout/msal`
- `/logout/msal`: Clears MSAL session keys
- `/logout/easyauth`: Redirects through App Service logout
- `/logout/all`: Clears session and Easy Auth sign-out if active

## Data and Session Model

Session keys used:

- `msal_user`
- `msal_access_token`
- `auth_flow`
- `session_timeline`

Timeline events are capped to the 12 most recent entries.

## UI Behavior Highlights

- Shared side panel shows:
  - active auth modes
  - auth health status checks
  - session timeline
  - idle sign-out countdown (5 minutes when signed in)
- Profile page supports:
  - tenant and role badges
  - claim list filter
  - claim copy action

## Operational Settings

- `APP_SERVICE_PORTAL_URL`
- `APP_REGISTRATION_PORTAL_URL`
- `APP_SERVICE_NAME`
- `APP_SERVICE_SUBSCRIPTION_ID`
- `APP_SERVICE_RESOURCE_GROUP`

If the portal URL settings are blank, the app builds:

- a direct App Service portal URL from the App Service ARM resource ID components
- a direct App Registration portal URL from `AAD_CLIENT_ID`

The App Service link prefers built-in App Service metadata first:

- `WEBSITE_SITE_NAME`
- `WEBSITE_RESOURCE_GROUP`
- `WEBSITE_OWNER_NAME` (subscription segment)

Pipeline-provided `APP_SERVICE_*` settings are a fallback when those platform values are unavailable.

## Deployment Architecture

The repository supports both GitHub Actions and Azure DevOps deployment automation. The main GitHub Actions workflow and the Azure DevOps ZIP-deploy pipeline both build one ZIP package and deploy it to a branch-specific primary Linux App Service plus an optional secondary target. The alternate `run_from_package.yml` pipeline keeps the package-mounted deployment path, including its optional third target. The current default path uses Azure CLI ZIP deploy plus App Service Oryx build automation, not `WEBSITE_RUN_FROM_PACKAGE`.

1. Resolve branch context to `prod`, `dev`, or `sbx`
2. Build one ZIP package as `app.zip`
3. Upload the package as a workflow or pipeline artifact
4. Run deployment prechecks for authentication and target configuration
5. Check the primary target and optional secondary target before deployment
6. Skip optional targets when their name is blank or the App Service is not found
7. Set Linux runtime and startup command for `gunicorn ... app:app`
8. Delete `WEBSITE_RUN_FROM_PACKAGE` and `PYTHONPATH` if present
9. Enable `SCM_DO_BUILD_DURING_DEPLOYMENT=true` and `ENABLE_ORYX_BUILD=true`
10. Deploy eligible targets with `az webapp deploy --type zip`
11. Optionally publish clean repository snapshots to a GitHub stage repo and an Azure DevOps mirror repo from the GitHub Actions workflow

For a side-by-side explanation of all supported deployment styles, see `docs/DEPLOYMENT_METHODS.md`.

## Security Considerations

- For production, always set explicit `FLASK_SECRET_KEY`.
- Do not commit real secrets in `.env`.
- Easy Auth principal header must be trusted only when running behind App Service Authentication.
- Session-stored token should be treated as sensitive runtime data.
