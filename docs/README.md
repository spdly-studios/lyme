# Lyme documentation

This directory documents Lyme version 0.1.x. Start with the user guides if you
want to run the package; use the maintainer guides when changing or releasing it.

## User documentation

- [Installation](installation.md): requirements, clean installation, editable setup, and verification.
- [Usage guide](usage.md): complete UOC to KSE to OMS workflows, inputs, outputs, and twins.
- [Command-line reference](cli.md): all installed commands, options, and batch examples.
- [Configuration](configuration.md): UOC TOML, Python configuration objects, thresholds, and tuning.
- [API and data contracts](API.md): supported public imports, handoff types, and model fields.
- [Troubleshooting and bugs](troubleshooting.md): common failures, limitations, diagnostics, and reports.
- [Bug policy and triage](bugs.md): bug severity, report template, regression handling, and closure rules.

## Maintainer documentation

- [Architecture](architecture.md): component boundaries, processing stages, and runtime flow.
- [Development](development.md): repository setup, quality checks, and change patterns.
- [Contributing](contributing.md): contribution standards, review checklist, and commit scope.
- [Release process](release.md): versioning, build validation, artifacts, and publication checklist.

## Which interface should I use?

Use the unified `lyme` Python API for applications and services. It passes the complete in-memory model
between components and avoids serialization loss. Use the three console commands for
shell pipelines or batch stages that intentionally exchange files.

Generated data belongs in `artifacts/` or an application-owned directory. It should not
be added to `src/`, `examples/data/`, or a source distribution.
