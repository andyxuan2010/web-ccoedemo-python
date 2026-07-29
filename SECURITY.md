# Security

## Runtime Boundaries

- Set `FLASK_SECRET_KEY` to a high-entropy secret in App Service settings. The app
  refuses to start on App Service when it is absent.
- Store `AAD_CLIENT_SECRET` in App Service settings or Key Vault references, never in
  source control.
- Easy Auth identity headers are accepted only when App Service metadata is present or
  `TRUST_EASY_AUTH_HEADERS=true` is deliberately enabled.
- Forwarded proxy headers are accepted only on App Service or when
  `TRUST_PROXY_HEADERS=true` is deliberately enabled.
- The app stores identity claims, not MSAL bearer access tokens, in Flask's signed
  client-side session cookie.

## CI/CD And GitOps Controls

- GitHub Actions permissions are read-only by default and elevated per job.
- Azure deployment uses GitHub OIDC and short-lived tokens. Configure a federated
  credential for each protected GitHub Environment and scope its Azure role to the
  intended App Service resources.
- Third-party GitHub Actions and pre-commit hooks are pinned to full commit SHAs.
- Python dependencies are exact-pinned and scanned with pip-audit.
- Dependabot monitors Python and GitHub Actions dependencies.
- Azure DevOps deployment stages use explicit source-branch gates.
- Protect `main`, `dev`, and `sbx` with pull request review and successful build
  policies. Restrict environment/service-connection access to their matching branches.
- Protect the external Azure DevOps `IaC/template` repository, restrict its pipeline
  permissions, and replace `refs/heads/main` with a reviewed immutable tag or commit
  when one is available.
- Enable GitHub secret scanning, push protection, and code scanning in repository
  settings where the organization plan supports them.

Microsoft recommends OIDC for App Service GitHub Actions deployments:
<https://learn.microsoft.com/azure/app-service/deploy-github-actions>.

GitHub recommends least-privilege workflow permissions and full-length action SHAs:
<https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions>.

Azure DevOps documents protected repository resources and pipeline permissions:
<https://learn.microsoft.com/azure/devops/pipelines/process/repository-resource>.

## Reporting

Report suspected vulnerabilities privately to the repository owners through the
organization's approved security channel. Do not include credentials, tokens, personal
data, or exploit details in a public issue.
