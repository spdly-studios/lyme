# Lyme API and data contracts

Imports from `lyme` and its stage namespaces are the supported public API. Parser, analyzer, normalizer,
and assembler modules are implementation details unless documented here.

## Pipeline contracts

UOC turns file records into canonical observations and a variable registry. KSE consumes
an aligned state matrix with a `timestamp` column or timestamp-named index. OMS consumes
the resulting in-memory `SystemModel` and, preferably, the same aligned DataFrame.

For one-process applications, use `kse.load_from_uoc(store, registry)`. This preserves
registry metadata and avoids a file round trip. File-based CLIs are intended for separate
batch processes.

KSE sorts rows by timestamp. A column participates in numeric analysis when at least 80%
of its non-null values are numerically coercible. Non-numeric columns remain in `raw_df`.

## UOC

### Core operations

- `Canonicalizer(config=None)` creates a registry and Arrow-backed store.
- `ingest(source, format_name=None)` accepts a path or open text stream.
- `export(mode, output, config=None)` writes `observation`, `state_matrix`, or `sparse`.

Explicit formats are `csv`, `json`, `kv`, and `text`. Multiple ingestion calls append to
the same store. `IngestionResult` reports `total_records` and `variable_count`.

### `UOCConfig`

| Field | Default | Purpose |
|---|---:|---|
| `timestamp_column` | `None` | Timestamp field; auto-detected when absent |
| `timestamp_format` | `None` | Optional `strptime` format |
| `default_quality` | `MEASURED` | Ingested observation quality |
| `batch_size` | `10000` | Arrow flush size |
| `missing_strategy` | `LEAVE` | Default missing-value behavior |
| `alignment_strategy` | `FORWARD_FILL` | Multi-rate alignment |
| `type_overrides` | `{}` | Variable name to `DataType` |
| `unit_overrides` | `{}` | Variable name to Pint target unit |
| `parser_config` | defaults | Parser settings |
| `default_missing_value` | `None` | Fill value for `DEFAULT` |

`UOCConfig.from_toml(path)` reads `[general]`, `[parser]`, `[type_overrides]`, and
`[unit_overrides]` sections:

```toml
[general]
batch_size = 20000
alignment_strategy = "forward_fill"
missing_strategy = "leave"

[parser]
timestamp_column = "recorded_at"
delimiter = ","
encoding = "utf-8"

[type_overrides]
temperature = "float"

[unit_overrides]
temperature = "degC"
```

`ExportConfig.variables` limits output to variable IDs; `time_range=(start, end)` limits
timestamps. Alignment choices are exact, nearest, forward-fill, and interpolation.

## KSE

### Loading and analysis

- `load_csv(path)`, `load_parquet(path)`, and `load_dataframe(df)`
- `load_from_uoc(store, registry, alignment_strategy="forward_fill")`
- `KnowledgeSynthesisEngine(config).analyze(ingestion)`
- `KnowledgeSynthesisEngine(config).analyze_dataframe(df)`

The ingestion result exposes `numeric_df`, `raw_df`, `variable_metadata`, `source_path`,
and timestamp/variable counts.

`KSEConfig` contains nested configuration groups:

| Group | Controls |
|---|---|
| `correlation` | Pearson, Spearman, MI, p-value, coverage thresholds |
| `temporal` | lag window, cross-correlation, trigger detection |
| `causal` | Granger lag, p-value, maximum tested pairs |
| `threshold` | decision-tree depth, leaf size, support, precision |
| `mode` | cluster size, maximum K, prevalence, mode features |

`SystemModel` contains findings, relationships, rules, modes, transitions, a knowledge
graph, contradictions, variable names, timestamp count, and metadata. Export it with the
four classes in `kse.exporters`: `MarkdownReportExporter`, `GraphJSONExporter`,
`RelationshipsJSONExporter`, and `RulesJSONExporter`.

## OMS

`OperationalModelSynthesizer(config).synthesize(model, df=None, mode_labels=None)` returns
an `OperationalTheory`. Pass the aligned DataFrame whenever possible; without it, equation
fitting falls back to mode centroids.

`OMSConfig` controls minimum influence confidence, equation p-value and R-squared,
polynomial degree, subsystem clustering, verbosity, and metadata.

The theory exposes consolidated variables, subsystems, influence chains, feedback loops,
a state machine, equations, explanations, and resolved contradictions. Export it with
`MarkdownTheoryExporter`, `JSONTheoryExporter`, or `DigitalTwinPythonExporter`.

Construct `DigitalTwin(theory.variable_names, theory.equations, theory.state_machine)`.
Use `reset(initial_values=None)` to initialize it and `step(inputs)` to apply exogenous
inputs, evaluate equations and transitions, and receive the next state.

## Production guidance

- Pin dependencies in the consuming deployment lockfile.
- Configure ambiguous units and types explicitly.
- Validate inferred relationships and equations with domain experts.
- Lag values are steps unless sampling intervals give them physical time meaning.
- Persist reports for audit, but pass models in memory inside applications.
- Do not execute generated twins from untrusted model directories.
