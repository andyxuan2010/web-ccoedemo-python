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
- `ProxyFix` is enabled only on App Service or when `TRUST_PROXY_HEADERS=true`.
- Session config:
  - `SESSION_COOKIE_HTTPONLY = True`
  - `SESSION_COOKIE_SAMESITE = Lax`
  - `SESSION_COOKIE_SECURE = True` when running on App Service
  - `PERMANENT_SESSION_LIFETIME = 30 minutes`
- Dynamic responses use `Cache-Control: no-store`.
- Responses set `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and
  `Permissions-Policy`; App Service responses also set HSTS.

### Authentication Modes

1. `MSAL mode`
- Start at `/login/msal`
- Build auth flow via `initiate_auth_code_flow(...)`
- Callback at `AAD_REDIRECT_PATH` (default `/auth/callback`)
- Exchange code for token using `acquire_token_by_auth_code_flow(...)`
- Store only `id_token_claims` in the signed session cookie; bearer access tokens are
  not persisted because this demo does not call downstream APIs

2. `Easy Auth mode`
- Start at `/login/easyauth`
- Redirect to App Service `/.auth/login/aad`
- App reads `X-MS-CLIENT-PRINCIPAL` only on App Service or when
  `TRUST_EASY_AUTH_HEADERS=true` is explicitly set for controlled testing
- Decode Base64 principal JSON and normalize claims to a dictionary

## Route Map

- `/`: Home page with mode selection cards
- `/health`: Minimal, dependency-free JSON readiness endpoint (`/healthz` remains an alias)
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

The repository supports both GitHub Actions and Azure DevOps deployment automation. The GitHub workflow builds a self-contained ZIP with vendored dependencies and mounts it with `WEBSITE_RUN_FROM_PACKAGE=1`; it targets a required primary Linux App Service plus optional secondary and third targets. The main Azure DevOps pipeline deploys a source ZIP to branch-specific primary and optional secondary targets and lets App Service/Oryx install dependencies. The alternate `run_from_package.yml` pipeline retains a second package-mounted Azure DevOps path.

1. Resolve branch context (`main` for GitHub Actions; `main`, `dev`, or `sbx` for Azure DevOps validation)
2. Build one ZIP package as `app.zip`
3. Upload the package as a workflow or pipeline artifact
4. Run deployment prechecks for authentication and target configuration
5. Check the configured deployment targets before deployment
6. Skip optional targets when their name is blank or the App Service is not found
7. Set Linux runtime and startup command for `gunicorn ... app:app`
8. Configure package-mounted settings for GitHub Actions, or Oryx build settings for the main Azure DevOps path
9. Verify that `FLASK_SECRET_KEY` is already provisioned for GitHub-managed targets
10. Deploy eligible targets with `az webapp deploy --type zip` and verify `/health`
11. Optionally publish clean repository snapshots to a GitHub stage repo and an Azure DevOps mirror repo from the GitHub Actions workflow

For a side-by-side explanation of all supported deployment styles, see `docs/DEPLOYMENT_METHODS.md`.

## Security Considerations

- App Service startup fails unless `FLASK_SECRET_KEY` is explicitly configured.
- Do not commit real secrets in `.env`.
- Easy Auth and forwarded proxy headers are trusted only at an explicit platform boundary.
- The MSAL authorization flow is removed from the session as soon as the callback starts,
  preventing callback replay with the same flow state.
- See `SECURITY.md` for CI/CD, GitOps, dependency, and platform control guidance.
