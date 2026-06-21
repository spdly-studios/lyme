# Configuration reference

## UOC configuration

Configure UOC in Python with `UOCConfig`, or load equivalent values from TOML with
`UOCConfig.from_toml(path)`. The CLI `--batch-size` value overrides the loaded TOML batch
size.

### General settings

| Setting | Type | Default | Notes |
|---|---|---:|---|
| `timestamp_column` | string or null | null | Auto-detected when omitted |
| `timestamp_format` | string or null | null | Python `strptime` syntax |
| `default_quality` | `Quality` | measured | Assigned to ingested observations |
| `batch_size` | integer | 10000 | Larger batches trade memory for throughput |
| `missing_strategy` | enum | leave | Applied during aligned export |
| `alignment_strategy` | enum | forward_fill | Multi-rate alignment behavior |
| `default_missing_value` | any | null | Used only by default-fill strategy |

### Parser settings

`ParserConfig` supports `timestamp_column`, `timestamp_format`, `delimiter`,
`kv_separator`, `kv_delimiter`, `text_patterns`, and `encoding`. Custom text patterns must
contain named `variable` and `value` groups; `timestamp` and `unit` groups are optional.

### Type and unit overrides

Type names are `boolean`, `integer`, `float`, `string`, `categorical`, and `timestamp`.
Unit targets use Pint names such as `volt`, `degC`, or `meter / second`. Overrides are keyed
by the exact normalized variable name.

### Export settings

`ExportConfig` controls `missing_strategy`, `alignment_strategy`,
`default_missing_value`, selected variable IDs, an inclusive timestamp range, and output
format. Use `ExportConfig(format="parquet")` when writing Parquet; a `.parquet` filename
alone does not change the configured format.

## KSE configuration

```python
from lyme.kse import CorrelationConfig, KSEConfig, ModeConfig

config = KSEConfig(
    correlation=CorrelationConfig(pearson_threshold=0.7, min_data_coverage=0.8),
    mode=ModeConfig(kmeans_max_k=5, min_mode_prevalence=0.05),
    min_confidence_report=0.5,
    verbose=False,
)
```

Lower statistical thresholds increase sensitivity and false positives. Larger lag windows
and pair limits can increase runtime sharply. Tune on representative data and preserve the
chosen configuration with every generated model.

### Defaults

| Group | Field | Default |
|---|---|---:|
| correlation | Pearson / Spearman / MI | 0.5 / 0.5 / 0.2 |
| correlation | p-value / minimum coverage | 0.05 / 0.5 |
| temporal | maximum lag / cross-correlation | 50 / 0.4 |
| temporal | trigger z-score / minimum samples | 2.5 / 3 |
| causal | maximum lag / p-value / maximum pairs | 10 / 0.05 / 100 |
| threshold | depth / leaf size / conditions | 4 / 10 / 3 |
| threshold | support / precision | 0.05 / 0.6 |
| mode | minimum cluster / samples / maximum K | 5 / 3 / 8 |
| mode | minimum prevalence / feature count | 0.02 / 4 |

## OMS configuration

```python
from lyme.oms import OMSConfig

config = OMSConfig(
    min_influence_confidence=0.6,
    equation_significance_pval=0.01,
    min_r2_score=0.5,
    subsystem_max_clusters=4,
    verbose=False,
)
```

Increasing `min_r2_score` and reducing `equation_significance_pval` retain fewer, stronger
equations. `max_poly_degree` currently defaults to 2. Subsystem clustering uses a distance
threshold based on association strength; test changes against expected domain groupings.

## Environment and secrets

Lyme itself requires no credentials. Do not put data-store passwords or API tokens in
UOC TOML files. Keep deployment secrets in the host application's secret manager and pass
only paths/data streams into Lyme.
