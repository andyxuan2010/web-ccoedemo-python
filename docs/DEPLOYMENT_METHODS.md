# Deployment Methods

This application can be deployed to Azure App Service in four main ways:

1. `azure-pipelines.yml`
2. `run_from_package`
3. `Deployment Center`
4. `ACR/custom container`

They all move code to App Service, but they differ significantly in where build happens, how startup is configured, how repeatable the deployment is, and how easy the method is to troubleshoot.

## Language support

The same four broad deployment methods are commonly available across Python, Node.js, and .NET App Service workloads, but support details differ by runtime.

| Runtime | `azure-pipelines.yml` | `run_from_package` | `Deployment Center` | `ACR/custom container` | Recommended default |
| --- | --- | --- | --- | --- | --- |
| Python | Yes | Generally not recommended for App Service Python | Yes | Yes | `azure-pipelines.yml` |
| Node.js | Yes | Yes | Yes | Yes | `azure-pipelines.yml` |
| .NET | Yes | Yes | Yes | Yes | `azure-pipelines.yml` |

Notes:

- Python on App Service is the most opinionated case here. Microsoft explicitly documents that Run From Package is not supported for Python apps on App Service.
- Node.js and .NET are both good candidates for all four methods, depending on whether you want platform-managed build behavior, immutable packages, or full container control.
- `ACR/custom container` is available for all three runtimes when you want to own the runtime image directly.

Official references:

- ZIP deploy:
  - https://learn.microsoft.com/en-us/azure/app-service/deploy-zip
- App Service deployment best practices:
  - https://learn.microsoft.com/en-us/azure/app-service/deploy-best-practices
- Run From Package:
  - https://learn.microsoft.com/en-us/azure/app-service/deploy-run-package
- Deployment Center / continuous deployment:
  - https://learn.microsoft.com/en-us/azure/app-service/deploy-continuous-deployment
- Custom containers on App Service:
  - https://learn.microsoft.com/en-us/azure/app-service/configure-custom-container
- CI/CD for custom containers:
  - https://learn.microsoft.com/en-us/azure/app-service/deploy-ci-cd-custom-container

## Methods at a glance

| Method | Main idea | Build location | Startup control | Artifact style | Best fit |
| --- | --- | --- | --- | --- | --- |
| `azure-pipelines.yml` | Deploy ZIP, let App Service/Oryx build it | App Service during deploy | Explicit, pipeline-managed | Source ZIP | Standard Python App Service deployment |
| `run_from_package` | Build package first, mount it read-only | Pipeline/runner before deploy | Explicit, pipeline-managed | Prebuilt ZIP package | Sealed artifact promotion and immutable package workflows |
| `Deployment Center` | App Service pulls from repo and deploys from portal-connected source | App Service after repo sync | App Service config or auto-detect | Git branch contents | Quick setup and portal-managed deployment |
| `ACR/custom container` | Build and push a container image, then have App Service run that image | Pipeline/runner before deploy | Container entrypoint and App Service container settings | OCI container image | Full runtime control and portable app packaging |

## Side-by-side comparison

| Topic | `azure-pipelines.yml` | `run_from_package` | `Deployment Center` | `ACR/custom container` |
| --- | --- | --- | --- |
| Deployment trigger | Azure DevOps pipeline run | Azure DevOps pipeline run | Portal sync or connected source trigger | Pipeline run or container image update |
| Source of truth | YAML pipeline in repo | YAML pipeline in repo | Mix of repo and App Service portal settings | Dockerfile, image build, registry config, and pipeline |
| Package contents | App code and static content | App code plus preinstalled Python dependencies | Raw repo contents | Full container filesystem |
| Dependency installation | Oryx installs from `requirements.txt` on App Service | Pipeline installs dependencies before deploy | Oryx may install dependencies if build automation is enabled | Installed during image build |
| App setting pattern | `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, `ENABLE_ORYX_BUILD=true` | `WEBSITE_RUN_FROM_PACKAGE=1`, `PYTHONPATH=...` | Depends on portal configuration | Container registry/image settings and optional app settings |
| Startup command | Explicitly configured in pipeline | Explicitly configured in pipeline | Must be manually configured or auto-detected | Usually Docker `CMD`/`ENTRYPOINT`, optionally overridden by App Service |
| Mutability at runtime | Normal App Service app content layout | Mounted package is read-only | Normal App Service app content layout | Container image is immutable; writable behavior depends on container/App Service mount points |
| Multi-app deployment | Easy to script in one pipeline | Easy to script in one pipeline | Harder to keep consistent across multiple apps | Easy if multiple apps consume the same image tag strategy |
| Drift risk | Low | Low to medium | High | Low to medium |
| Troubleshooting surface | Pipeline logs plus App Service logs | Pipeline logs plus App Service logs | Portal settings, build logs, and runtime logs | Dockerfile, image build logs, registry, container logs, and App Service logs |
| Python support fit | Strongest fit for this repo | More fragile for Python App Service | Acceptable for light scenarios, but less controlled | Strong when you need custom OS/runtime control |

## 1. `azure-pipelines.yml`

This is the pipeline-driven method where the pipeline uploads a ZIP, sets the runtime/startup settings, and lets App Service build the Python app during deployment.

### How it works

1. The pipeline packages the app into `app.zip`.
2. The pipeline resolves the App Service target and checks SCM/Kudu connectivity.
3. The pipeline configures the Linux Python runtime and Gunicorn startup command.
4. The pipeline removes `WEBSITE_RUN_FROM_PACKAGE` and `PYTHONPATH` if they exist.
5. The pipeline enables build automation:
   - `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
   - `ENABLE_ORYX_BUILD=true`
6. The pipeline deploys the ZIP with `az webapp deploy --type zip`.
7. Oryx installs dependencies from `requirements.txt` on App Service.

### Operational model

- The ZIP is mainly source content, not a fully baked runtime package.
- App Service handles Python dependency installation.
- Startup behavior is stable because the pipeline sets it explicitly.
- This is usually the most natural model for Python on Linux App Service.

### Pros

- Good fit for Python App Service expectations.
- Clear and repeatable deployment flow.
- Easy to standardize across dev, sbx, and prod targets.
- Keeps platform configuration close to the deployment logic.
- Easier to troubleshoot than portal-driven sync because the pipeline shows every deployment step.

### Cons

- Requires SCM/Kudu reachability from the runner.
- Build happens at deploy time, so deployment depends on App Service build behavior.
- Runtime package is not fully sealed before deployment.

### Best when

- You want the most supportable Python App Service deployment pattern.
- You want repo-controlled deployment behavior.
- You want one pipeline to deploy consistently to multiple App Services.

## 2. `run_from_package`

This is the immutable package approach, where the pipeline builds a ZIP package that includes the application and Python dependencies, then configures App Service to run directly from that mounted package.

### How it works

1. The pipeline resolves Python on the build runner.
2. The pipeline installs dependencies into `.python_packages/lib/site-packages`.
3. The pipeline copies app code, templates, and static files into a package directory.
4. The pipeline archives that content into `app.zip`.
5. The deploy stage sets:
   - `WEBSITE_RUN_FROM_PACKAGE=1`
   - `PYTHONPATH=/home/site/wwwroot/.python_packages/lib/site-packages`
6. The pipeline sets the Gunicorn startup command.
7. App Service mounts the ZIP package and runs the app from that package.

### Operational model

- The package is intended to be self-contained.
- Runtime content is mounted read-only.
- Dependency installation is shifted left into the pipeline.
- App Service should not need an Oryx build for normal success.

### Pros

- Strong artifact immutability story.
- Build and runtime contents are more tightly coupled.
- Useful when you want a more release-artifact-oriented deployment model.
- Can reduce uncertainty from on-platform dependency installation.

### Cons

- More fragile for Python on App Service than ZIP deploy with Oryx build.
- Pipeline build environment matters more because dependencies are prepared before deployment.
- Read-only package layout can create runtime assumptions that differ from standard App Service behavior.
- Python packaging issues on the runner can break the build earlier.
- This method needs careful `PYTHONPATH` and startup handling.

### Best when

- You specifically want immutable package semantics.
- You want to promote one prepared package across environments.
- You accept more packaging complexity in exchange for tighter artifact control.

## 3. `Deployment Center`

This is the portal-managed path where App Service is connected directly to a source repository or branch and deployment is driven through App Service Deployment Center.

### How it works

1. App Service is connected to a Git source through the portal.
2. A sync or commit causes App Service to fetch the current branch contents.
3. Build automation may run depending on the App Service settings.
4. The runtime attempts to start the application using configured or detected startup behavior.

### Operational model

- Deployment configuration lives partly outside the repo.
- App Service settings become a larger part of the deployment behavior.
- It is possible for the same repo state to behave differently across apps if portal settings differ.

### Pros

- Quick to set up from the Azure portal.
- No Azure DevOps packaging pipeline required.
- Good for demos, simple experiments, or small proof-of-concept deployments.

### Cons

- Higher configuration drift risk.
- Harder to guarantee consistency across environments.
- Startup command and build settings are easier to forget or misconfigure.
- Troubleshooting usually spans portal config, source sync logs, and runtime logs.
- Less suitable when you want deployment behavior fully captured in version-controlled YAML.

### Best when

- You want the simplest portal-led setup.
- You are doing lightweight validation rather than disciplined multi-environment delivery.
- You are comfortable managing part of the deployment behavior outside the repo.

## 4. `ACR/custom container`

This is the container-based path where the application is packaged as a Docker image, pushed to Azure Container Registry (ACR), and then run by App Service as a custom container.

### How it works

1. A Docker image is built for the Python app.
2. Dependencies and any required OS packages are installed during the image build.
3. The image is pushed to Azure Container Registry.
4. App Service is configured to pull that image from ACR.
5. App Service starts the container using its configured image and startup behavior.

### Operational model

- The application and runtime are packaged together in the image.
- The image is portable across environments that support containers.
- Runtime behavior is strongly influenced by the Dockerfile, image base, and container entrypoint.
- App Service becomes a container host instead of a Python-code build host.

### Pros

- Maximum runtime control.
- Good for apps that need native Linux packages, custom system libraries, or exact runtime parity.
- The same image can be reused outside App Service.
- Strong artifact reproducibility when image build inputs are controlled.

### Cons

- More operational overhead than code-based deployment methods.
- You must maintain the Dockerfile, base image, image patching, and registry lifecycle.
- Container logging, debugging, and startup troubleshooting add another layer of complexity.
- Image size and image pull time can affect deployment speed.

### Best when

- You need system-level dependencies or custom runtime behavior.
- You want one portable image across App Service and other container-capable platforms.
- You are comfortable owning the container lifecycle, not just the app code.

## Pros and cons summary

| Method | Main pros | Main cons |
| --- | --- | --- |
| `azure-pipelines.yml` | Supportable Python fit, repeatable, repo-controlled, easy multi-target automation | Depends on App Service build step, requires SCM access, build happens during deploy |
| `run_from_package` | Immutable package model, explicit artifact, dependency bundle prepared before deployment | More packaging complexity, more runner sensitivity, less natural fit for Python App Service |
| `Deployment Center` | Fast setup, low ceremony, no separate pipeline required | Higher drift risk, less reproducible, more portal dependency, easier to misconfigure |
| `ACR/custom container` | Maximum runtime control, portable image, best fit for custom dependencies | Highest operational complexity, image maintenance overhead, slower and more layered troubleshooting |

## Recommendation for this repo

Recommended default: `azure-pipelines.yml`

Reasons:

- It is the best operational fit for a Python App Service workload like this one.
- It keeps deployment behavior under source control.
- It handles startup configuration explicitly.
- It scales better across multiple target apps and environments.
- It is easier to support over time than a portal-managed Deployment Center flow.

Use `run_from_package` only when immutable package behavior is a deliberate requirement.

Use `Deployment Center` only when simplicity matters more than reproducibility and strict environment consistency.

Use `ACR/custom container` when runtime control is more important than deployment simplicity.
