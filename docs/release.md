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
python -m pip install dist/cognis_os-<version>-py3-none-any.whl
python -c "import cognis_os; from cognis_os import Canonicalizer, KnowledgeSynthesisEngine, OperationalModelSynthesizer"
cognis-os --help
cognis-os uoc --help
cognis-os kse --help
cognis-os oms --help
```

## Publication

Publish first to a staging index when available, verify installation by distribution name,
then publish the exact already-validated artifacts to the production index. Do not rebuild
between staging and production. Tag the same source revision and attach checksums/release notes.

Never commit or print repository tokens. Use trusted publishing or scoped, short-lived
credentials supplied by the CI secret manager.
