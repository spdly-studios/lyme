# Release process

## Versioning

The project is currently `0.x` alpha software. Use semantic version intent: patch for
compatible fixes, minor for compatible features, and clearly documented minor/major changes
for breaking public APIs. Keep the distribution version and exposed package versions aligned.

## Pre-release checklist

1. Confirm the release scope and migration notes.
2. Update distribution version metadata and user-facing changelog/release notes.
3. Run lint, compile, and end-to-end example checks.
4. Build both source and wheel distributions in a clean environment.
5. Inspect archive contents for tests, caches, artifacts, credentials, and private data.
6. Validate metadata and README rendering with Twine.
7. Install the wheel into a fresh environment and rerun import/CLI smoke tests.

## Build and validate

```bash
python -m build
python -m twine check dist/*
```

The source distribution should include package sources, type markers, README, license, and
build metadata. It should exclude artifacts, caches, and local environments according
to `MANIFEST.in` and package discovery configuration.

## Clean-environment smoke test

```bash
python -m venv release-venv
# activate the environment
python -m pip install dist/lyme-<version>-py3-none-any.whl
python -c "import lyme; from lyme import Canonicalizer, KnowledgeSynthesisEngine, OperationalModelSynthesizer"
lyme --help
lyme uoc --help
lyme kse --help
lyme oms --help
```

## Publication

The repository includes a GitHub Actions workflow at
`.github/workflows/release.yml` that builds the package on every tag push matching `v*`
and publishes the exact built artifacts to PyPI with trusted publishing.

Recommended release flow:

1. Update the version in `pyproject.toml`.
2. Create a git tag such as `v0.1.0`.
3. Push the tag to GitHub.
4. Let GitHub Actions build the source and wheel distributions.
5. Confirm the publish job uploads the same artifacts to PyPI.

If you want a staged release first, keep the workflow as-is but point the `publish` job to
TestPyPI in a separate branch or manually triggered workflow. Do not rebuild between staging
and production. Tag the same source revision and attach checksums or release notes.

Never commit or print repository tokens. Use trusted publishing or scoped, short-lived
credentials supplied by the CI secret manager.
