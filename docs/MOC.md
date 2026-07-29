# Documentation Map

This page is the map of content for the repository documentation set. Use it as the starting point when you want to understand the app, its delivery pipelines, or the supported deployment patterns.

## Start Here

- `README.md`: high-level repository entry point, scope, key files, and deployment summary

## Core Documents

- `docs/ARCHITECTURE.md`: application structure, authentication modes, runtime behavior, and deployment architecture
- `docs/PIPELINES.md`: repository-managed CI/CD paths, including GitHub Actions and both Azure DevOps pipeline options
- `docs/DEPLOYMENT_METHODS.md`: side-by-side comparison of deployment approaches supported or referenced in this repo
- `docs/VALIDATION.md`: repository scan, environment checks, and validation notes

## Suggested Reading Paths

### Understand the App

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/VALIDATION.md`

### Understand CI/CD

1. `README.md`
2. `docs/PIPELINES.md`
3. `docs/DEPLOYMENT_METHODS.md`

### Choose a Deployment Pattern

1. `README.md`
2. `docs/DEPLOYMENT_METHODS.md`
3. `docs/PIPELINES.md`

## Notes

- `docs/PIPELINES.md` focuses on the YAML pipelines that exist in this repository.
- `docs/DEPLOYMENT_METHODS.md` is broader and includes platform-managed options outside repo YAML, such as Deployment Center and custom containers.
- `run_from_package.yml` remains documented as an alternate path rather than the current default deployment model.
