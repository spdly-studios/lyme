# Troubleshooting and bug reporting

## Installation failures

Confirm Python 3.11+, update pip, and retry in a fresh virtual environment. Numerical
dependencies may require platform-specific wheels. Include Python, OS, architecture, and the
complete pip error when reporting failures.

## Command not found

The console scripts are created only after installation. Activate the correct environment and
check `python -m pip show lyme`. As a diagnostic, invoke `python -m uoc.cli --help` using
the same interpreter.

## Input is parsed incorrectly

Pass `--format` or `format_name` explicitly, configure the timestamp column and delimiters,
and inspect `Canonicalizer.registry`. For streams without filename extensions, automatic
sniffing has less context. Reduce the input to a few representative records for a bug report.

## Wrong types or units

Use `type_overrides` and `unit_overrides`. Ensure Pint understands the source and target unit
and that dimensions are compatible. Variable names are exact keys. Preserve the raw value,
inferred type/unit, expected result, and configuration in the report.

## KSE ignores a column

KSE requires at least 80% of non-null values in a column to be numerically coercible. Inspect
`ingestion.raw_df`, `ingestion.numeric_df`, null counts, and unexpected strings. Completely
empty columns can be numeric but provide no useful evidence.

## Few or no findings

Check record count, coverage, constant columns, sampling order, and configured thresholds.
Short series cannot support large lag windows or robust Granger tests. Lowering thresholds can
increase false positives; diagnose data quality before tuning.

## OMS derives no equations

Pass the aligned DataFrame used by KSE, verify predictor columns are numeric, and review
`min_r2_score` and significance settings. Metadata-only synthesis relies on mode centroids
and may not have enough independent observations for a valid equation.

## Digital twin output is unexpected

Confirm input keys match `theory.variable_names`, examine equation coefficients and lag steps,
reset between scenarios, and validate initial state centroids. Unknown input names are ignored.
Generated twins are empirical simulators, not guaranteed physical models.

## Warnings seen in constrained environments

Joblib may warn when it cannot detect physical CPU cores and will fall back to logical cores.
This does not normally change correctness.

## Known limitations

- The distribution is alpha and has no long-term API compatibility guarantee yet.
- Causal analysis is observational and can be confounded.
- Lag interpretation depends on sampling intervals.
- KSE's numeric-column decision uses a fixed 80% coercion rule.
- The OMS file-based CLI reconstructs a model from exported JSON; the in-memory API retains
  a richer and safer contract.
- Generated standalone twin code must be treated as executable code.
- Large variable counts can make pairwise analysis expensive despite pair limits.

## Filing a useful bug report

Include:

1. Lyme version or source revision.
2. Python, OS, architecture, and dependency versions.
3. The smallest sanitized input that reproduces the problem.
4. Exact command or Python snippet and configuration.
5. Expected and actual behavior.
6. Full traceback, warnings, and relevant logs as text.
7. Whether `examples/pipeline.py` passes.

Do not attach secrets or sensitive telemetry. Replace proprietary names and values while
preserving data types, missingness, ordering, and the condition that triggers the bug.

## Diagnostic commands

```bash
python --version
python -m pip show lyme
python -m pip freeze
python examples/pipeline.py
```
