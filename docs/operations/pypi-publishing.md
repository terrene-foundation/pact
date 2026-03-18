# PyPI Trusted Publisher Setup

The CARE Platform uses PyPI trusted publishing (OIDC) to publish packages to PyPI and TestPyPI without long-lived API tokens. The GitHub Actions workflow at `.github/workflows/publish.yml` handles the entire build-and-publish pipeline.

---

## Prerequisites

- Repository: `terrene-foundation/care` on GitHub
- PyPI account with access to the `care-platform` project
- GitHub repository admin access (for environment creation)

---

## Step 1: Configure PyPI Trusted Publisher

Trusted publishing uses OpenID Connect (OIDC) so that GitHub Actions can authenticate to PyPI without storing any secrets.

### On PyPI (production)

1. Go to [https://pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
2. Under **Add a new pending publisher** (for first-time setup) or on the project's publishing settings:
   - **PyPI project name**: `care-platform`
   - **Owner**: `terrene-foundation`
   - **Repository name**: `care`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Click **Add**

### On TestPyPI

1. Go to [https://test.pypi.org/manage/account/publishing/](https://test.pypi.org/manage/account/publishing/)
2. Same fields as above, but:
   - **Environment name**: `testpypi`
3. Click **Add**

---

## Step 2: Create GitHub Environments

The publish workflow requires two GitHub environments that act as deployment gates.

### Create the `pypi` environment

1. Go to **Settings > Environments** in the GitHub repository
2. Click **New environment**
3. Name: `pypi`
4. Recommended protection rules:
   - **Required reviewers**: Add at least one maintainer who must approve before publishing to production PyPI
   - **Deployment branches**: Restrict to `main` branch only
5. Click **Save protection rules**

### Create the `testpypi` environment

1. Click **New environment**
2. Name: `testpypi`
3. Protection rules:
   - **Required reviewers**: Optional (TestPyPI is for dry runs)
   - **Deployment branches**: Any branch (allows testing from feature branches)
4. Click **Save protection rules**

No secrets need to be added to either environment. Trusted publishing uses OIDC tokens generated at runtime by GitHub Actions.

---

## Step 3: How Releases Work

### Production Release (PyPI)

Publishing to production PyPI is triggered by creating a GitHub release:

1. Go to **Releases > Draft a new release** in the repository
2. Create a new tag matching the version in `pyproject.toml` (e.g., `v0.1.0`)
3. Write release notes describing what changed
4. Click **Publish release**

This triggers the publish workflow, which:

1. Builds the sdist and wheel (`python -m build`)
2. Validates the package (`twine check dist/*`)
3. Publishes to PyPI via `pypa/gh-action-pypi-publish@release/v1`
4. Builds and pushes a Docker container image to `ghcr.io/terrene-foundation/care-platform`

The `pypi` environment's required reviewers (if configured) must approve before the publish step runs.

### TestPyPI Dry Run

To test the publishing pipeline without affecting production:

1. Go to **Actions > Publish** in the repository
2. Click **Run workflow**
3. Select the branch to build from
4. Set **Publish target** to `testpypi`
5. Click **Run workflow**

This builds the package and publishes to TestPyPI. You can verify the result at `https://test.pypi.org/project/care-platform/`.

To install from TestPyPI for verification:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ care-platform
```

The `--extra-index-url` flag ensures that dependencies not on TestPyPI are still resolved from production PyPI.

---

## Workflow Reference

The publish workflow (`.github/workflows/publish.yml`) requires these permissions:

```yaml
permissions:
  contents: read # Read repository contents
  id-token: write # Required for OIDC trusted publishing
  packages: write # Required for GitHub Container Registry
```

### Jobs

| Job                | Trigger                              | Environment | What It Does                                                 |
| ------------------ | ------------------------------------ | ----------- | ------------------------------------------------------------ |
| `build`            | Always                               | None        | Build sdist + wheel, validate with twine, upload as artifact |
| `publish-testpypi` | Manual dispatch with target=testpypi | `testpypi`  | Download artifact, publish to TestPyPI                       |
| `publish-pypi`     | GitHub release published             | `pypi`      | Download artifact, publish to PyPI                           |
| `container`        | GitHub release published             | None        | Build and push Docker image to ghcr.io                       |

---

## Troubleshooting

### "Trusted publisher not configured"

The OIDC publisher on PyPI/TestPyPI must match exactly:

- Owner: `terrene-foundation` (case-sensitive)
- Repository: `care` (not `care-platform`)
- Workflow: `publish.yml` (not the full path)
- Environment: `pypi` or `testpypi` (must match the GitHub environment name)

### "Environment not found"

The GitHub environments `pypi` and `testpypi` must exist before the workflow runs. Create them in **Settings > Environments**.

### Version Conflicts

PyPI does not allow re-uploading the same version. If a version was already published (even to TestPyPI), bump the version in `pyproject.toml` before retrying. For TestPyPI dry runs, use pre-release versions (e.g., `0.1.0rc1`).

### Container Registry Authentication

The container job uses `GITHUB_TOKEN` (automatically provided) to authenticate with `ghcr.io`. No additional secrets are needed. The image is tagged with both the version number and `latest`.
