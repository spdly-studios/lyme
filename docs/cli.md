# Unified command-line reference

Installing Lyme creates one command: `lyme`. The processing stages are
subcommands of that single product interface:

```text
lyme {uoc,kse,oms} [stage options]
```

Use `lyme --help` to list stages and `lyme <stage> --help` for detailed options.

## `lyme uoc`

```text
lyme uoc [--input PATH] [--output-dir DIR] [--config FILE]
              [--format {csv,json,kv,text}] [--batch-size N]
```

| Option | Default | Meaning |
|---|---|---|
| `--input` | sample spacecraft CSV | Raw input path |
| `--output-dir` | `output_processed` | Destination directory |
| `--config` | none | UOC TOML configuration |
| `--format` | inferred | Parser override |
| `--batch-size` | `1000` | Arrow flush batch size |

It writes `canonical_triples.csv`, `aligned_state_matrix.csv`, and
`sparse_coordinates.csv`.

## `lyme kse`

```text
lyme kse [--input PATH] [--output-dir DIR]
```

The input is a UOC-aligned CSV or Parquet state matrix. It writes `kse_report.md`,
`kse_graph.json`, `kse_rules.json`, and `kse_relationships.json`.

## `lyme oms`

```text
lyme oms [--input-dir DIR] [--matrix PATH] [--output-dir DIR]
```

The input directory contains the KSE JSON files. The matrix should be the aligned UOC
state matrix. Outputs are `oms_report.md`, `oms_model.json`, and `digital_twin.py`.

## Complete batch pipeline

```bash
lyme uoc --input telemetry.csv --config cognis.toml --output-dir artifacts/run
lyme kse --input artifacts/run/aligned_state_matrix.csv --output-dir artifacts/run
lyme oms --input-dir artifacts/run --matrix artifacts/run/aligned_state_matrix.csv --output-dir artifacts/run
```

All three stages belong to Lyme; the subcommands are pipeline operations, not separate
installed products or distributions.
