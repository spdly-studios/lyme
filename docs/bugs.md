# Bug policy and triage

Use [troubleshooting.md](troubleshooting.md) first to distinguish configuration, data-quality,
and environment problems from package defects. A bug is reproducible behavior that violates a
documented contract, produces an incorrect result, crashes on supported input, or exposes a
security or data-integrity risk.

## Severity

- **Critical:** code execution, credential/private-data exposure, irreversible corruption, or
  broadly incorrect models presented as valid.
- **High:** supported workflows crash, silently lose observations, corrupt handoff files, or
  produce structurally invalid models without a practical workaround.
- **Medium:** incorrect behavior with a workaround, a broken non-default format, or significant
  performance regression.
- **Low:** misleading messages, documentation defects, minor portability problems, or polish.

Statistically weak results caused by insufficient data are not automatically bugs. They become
bugs when confidence, validation, or failure behavior contradicts the documented contract.

## Report template

```text
Title:
Component: UOC / KSE / OMS / CLI / packaging / documentation
Version or source revision:
Python, OS, and architecture:
Installation method:

Minimal sanitized input:
Configuration:
Exact command or code:

Expected behavior:
Actual behavior:
Traceback and warnings:

Does python examples/pipeline.py pass?
Regression from a known version?
```

Attach data only when it is safe to share. A minimal inline fixture is preferable to a large
archive. Preserve ordering, missingness, types, and unit strings needed to reproduce the issue.

## Triage procedure

Maintainers should reproduce in a clean supported environment, identify the owning component,
classify severity, and reduce the report to a regression test. Confirm whether the behavior is
a code defect, unsupported input, numerical limitation, dependency regression, or documentation
gap. Security-sensitive reports must move to a private channel.

## Fix requirements

A bug fix should include a test that fails on the affected behavior, the smallest scoped code
change, updated documentation when the contract changes, and a note about compatibility or
model-output differences. Critical data-integrity fixes should also add an end-to-end assertion.

## Closing reports

Close a report when the fix is verified, the behavior matches documented design, the issue is
an upstream dependency problem with a tracked reference, or reproduction information remains
unavailable after a reasonable request. State the reason and any workaround; do not silently
close reports whose statistical expectations need clarification.
