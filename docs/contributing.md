# Contributing

## Before starting

Search existing issues and documentation, reproduce the behavior on the latest code, and
reduce the problem to one component where possible. For large API or data-contract changes,
agree on the design before implementation.

## Contribution workflow

1. Create a focused branch from the current main branch.
2. Install editable development dependencies.
3. Add or update tests before changing behavior.
4. Implement the smallest coherent change.
5. Run tests, Ruff, compile checks, and the pipeline example.
6. Update documentation for any user-visible behavior.
7. Submit a reviewable change with purpose, approach, validation, and risks.

## Change standards

Contributions should preserve the separation between canonicalization, discovery, and model
synthesis. Avoid unrelated formatting or dependency churn. Do not commit generated artifacts,
virtual environments, caches, distribution files, proprietary telemetry, credentials, or
personally identifiable data.

Public APIs require type hints and docstrings describing inputs, outputs, and meaningful
exceptions. New configuration fields need safe defaults. Statistical behavior should state
assumptions and limitations rather than imply certainty.

## Testing checklist

- New happy path and regression tests are included.
- Empty, malformed, missing, and boundary inputs are considered.
- Randomized tests use deterministic seeds.
- Existing 30+ tests remain green.
- `examples/pipeline.py` still succeeds when integration contracts change.
- Output formats remain readable by their downstream component.

## Documentation checklist

- Examples use package APIs, not internal modules or deleted wrappers.
- Commands match current `--help` output.
- Configuration defaults match dataclasses.
- Paths are platform-neutral where practical.
- Limitations and migration notes are explicit.

## Commit and review scope

Use concise, imperative commit subjects. Keep refactors separate from behavior changes when
possible. A review description should include the problem, user impact, implementation,
tests run, and any compatibility or numerical-result changes.

## Reporting security-sensitive problems

Do not publish credentials, private datasets, or exploitable details in a public issue.
Use the repository owner's private security contact or hosting platform's private advisory
mechanism. If none exists, report only that a private contact channel is needed.
