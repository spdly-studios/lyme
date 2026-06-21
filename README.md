# Lyme

Lyme is a Python toolkit that turns heterogeneous time-series observations
into an interpretable operational model and executable digital twin. It contains
one package with three pipeline stages:

1. **UOC** (`lyme.uoc`) parses, types, normalizes, aligns, and exports observations.
2. **KSE** (`lyme.kse`) discovers correlations, lagged influence, rules, modes, and transitions.
3. **OMS** (`lyme.oms`) synthesizes subsystems, influence chains, state machines, equations,
   reports, and a digital twin.

The project is currently alpha software. Discovered relationships and equations are
empirical models, not proof of physical causality. Validate outputs before operational use.

## Requirements and installation

- Python 3.11 or newer
- Supported inputs: CSV/TSV, JSON/JSONL, key-value logs, and free-text logs

Install the package from the repository root:

```bash
python -m pip install .
```

For editable development with packaging and lint tools:

```bash
python -m pip install -e ".[dev]"
```

Installing the package creates one command: `lyme`. Its `uoc`, `kse`, and `oms`
subcommands run the internal pipeline stages.

## Fastest complete example

Run the verified API example after installation:

```bash
python examples/pipeline.py
```

It reads `examples/data/synthetic_system.csv` and writes generated reports and models
under `artifacts/pipeline/`. The `artifacts/` directory is intentionally excluded from
source distributions and version control.

## End-to-end Python API

The preferred production integration keeps the model in memory between components:

```python
from pathlib import Path

from lyme import DigitalTwin, KSEConfig, KnowledgeSynthesisEngine
from lyme import OMSConfig, OperationalModelSynthesizer, UOCConfig, Canonicalizer
from lyme.kse import load_from_uoc
from lyme.uoc import DataType

canonicalizer = Canonicalizer(
    UOCConfig(
        type_overrides={"temperature": DataType.FLOAT},
        unit_overrides={"temperature": "degC"},
    )
)
canonicalizer.ingest(Path("telemetry.csv"), format_name="csv")

ingestion = load_from_uoc(canonicalizer.store, canonicalizer.registry)
model = KnowledgeSynthesisEngine(KSEConfig(verbose=False)).analyze(ingestion)

frame = ingestion.raw_df.reset_index()
theory = OperationalModelSynthesizer(OMSConfig(verbose=False)).synthesize(model, df=frame)

twin = DigitalTwin(
    variable_names=theory.variable_names,
    equations=theory.equations,
    state_machine=theory.state_machine,
)
next_state = twin.step({"motor_speed": 500.0})
```

Use `load_from_uoc` when all components run in one process. Use `load_csv`,
`load_parquet`, or `KnowledgeSynthesisEngine.analyze_dataframe` when your application
already has an aligned state matrix.

## Command-line pipeline

The commands exchange files through one output directory:

```bash
lyme uoc --input telemetry.csv --output-dir artifacts/run
lyme kse --input artifacts/run/aligned_state_matrix.csv --output-dir artifacts/run
lyme oms --input-dir artifacts/run --matrix artifacts/run/aligned_state_matrix.csv --output-dir artifacts/run
```

Run any command with `--help` for its current options. The CLI is convenient for batch
jobs; the Python API is preferred when embedding Lyme in an application because it
avoids reconstructing the KSE model from exported JSON.

## UOC: canonicalizing observations

### Configuration

```python
from lyme.uoc import (
    AlignmentStrategy,
    Canonicalizer,
    DataType,
    ExportConfig,
    MissingStrategy,
    ParserConfig,
    UOCConfig,
)

config = UOCConfig(
    batch_size=10_000,
    type_overrides={"rpm": DataType.FLOAT},
    unit_overrides={"temperature": "degC", "voltage": "volt"},
    parser_config=ParserConfig(timestamp_column="recorded_at", delimiter=","),
)
canonicalizer = Canonicalizer(config)
```

`type_overrides` prevents ambiguous input from changing a variable's inferred type.
`unit_overrides` defines the target unit used by Pint. Unit strings must be valid Pint
units. Parser settings can also be loaded with `UOCConfig.from_toml(path)`.

### Ingestion

```python
result = canonicalizer.ingest(Path("data.csv"))             # infer from extension/content
result = canonicalizer.ingest(Path("events.jsonl"), "json")
result = canonicalizer.ingest(Path("machine.log"), "kv")
```

Valid explicit format names are `csv`, `json`, `kv`, and `text`. A source may also be an
open text stream. Multiple calls append observations to the same store and registry.
`IngestionResult` reports `total_records` and `variable_count`.

### Registry and exports

```python
for variable in canonicalizer.registry:
    print(variable.id, variable.name, variable.dtype, variable.unit, variable.source)

canonicalizer.export("observation", Path("observations.parquet"))
canonicalizer.export(
    "state_matrix",
    Path("state_matrix.csv"),
    ExportConfig(
        alignment_strategy=AlignmentStrategy.FORWARD_FILL,
        missing_strategy=MissingStrategy.LEAVE,
    ),
)
canonicalizer.export("sparse", Path("coordinates.csv"))
```

Export modes are:

- `observation`: canonical long-form records; CSV or Parquet selected by extension/config.
- `state_matrix`: one row per timestamp and one column per variable.
- `sparse`: non-null coordinate records for sparse datasets.

Alignment choices are `EXACT`, `NEAREST`, `FORWARD_FILL`, and `INTERPOLATE`. Missing
value choices are `LEAVE`, `FORWARD_FILL`, `INTERPOLATE`, and `DEFAULT`.

## KSE: discovering operational knowledge

KSE requires an aligned table with a `timestamp` column or a timestamp-named index.
Columns with at least 80% numerically coercible non-null values participate in numeric
analysis; other columns remain available in `raw_df` but are not analyzed.

```python
import pandas as pd
from lyme.kse import KnowledgeSynthesisEngine, KSEConfig, load_csv, load_dataframe, load_parquet

ingestion = load_csv("state_matrix.csv")
# ingestion = load_parquet("state_matrix.parquet")
# ingestion = load_dataframe(pd.DataFrame(...))

engine = KnowledgeSynthesisEngine(KSEConfig(verbose=False))
model = engine.analyze(ingestion)
# Or: model = engine.analyze_dataframe(pd.DataFrame(...))
```

`SystemModel` contains `findings`, `relationships`, `rules`, `modes`,
`mode_transitions`, `graph`, `contradictions`, and source metadata.

Export results with:

```python
from lyme.kse.exporters import (
    GraphJSONExporter,
    MarkdownReportExporter,
    RelationshipsJSONExporter,
    RulesJSONExporter,
)

MarkdownReportExporter().export(model, "knowledge_report.md")
GraphJSONExporter().export(model, "knowledge_graph.json")
RelationshipsJSONExporter().export(model, "relationships.json")
RulesJSONExporter().export(model, "rules.json")
```

Thresholds for correlation, temporal analysis, Granger analysis, decision-tree rules,
and clustering are configured through `KSEConfig` and its nested config objects. See
`docs/API.md` for the complete configuration map.

## OMS: theory and digital twin

OMS consumes the in-memory `SystemModel`. Passing the aligned DataFrame is strongly
recommended because equation fitting and transition inference have more evidence than
the metadata-only fallback.

```python
from lyme.oms import (
    DigitalTwin,
    DigitalTwinPythonExporter,
    JSONTheoryExporter,
    MarkdownTheoryExporter,
    OperationalModelSynthesizer,
)

theory = OperationalModelSynthesizer().synthesize(model, df=aligned_frame)
MarkdownTheoryExporter().export(theory, Path("operational_theory.md"))
JSONTheoryExporter().export(theory, Path("operational_theory.json"))
DigitalTwinPythonExporter().export(theory, Path("digital_twin.py"))

twin = DigitalTwin(theory.variable_names, theory.equations, theory.state_machine)
twin.reset({"motor_speed": 100.0})
state = twin.step({"motor_speed": 150.0})
```

`OperationalTheory` exposes consolidated variables, subsystems, influence chains,
feedback loops, a state machine, fitted equations, explanations, and resolved
contradictions. The generated `digital_twin.py` is standalone, while `oms.DigitalTwin`
is the embeddable runtime class.

## Repository layout

```text
src/lyme/          Unified production package
  uoc/             Observation parsing, normalization, alignment, and export
  kse/             Knowledge analysis, assembly, graph construction, and export
  oms/             Operational synthesis, reporting, equations, and twin runtime
examples/      Production API example and sample input data
docs/          Architecture, API, and operational guidance
artifacts/     Ignored generated outputs
```

## Validation and release

```bash
python -m ruff check src examples
python -m build
python -m twine check dist/*
```

For a no-local-build release, push a `v*` tag to GitHub and let
`.github/workflows/release.yml` build and publish the package from Actions using
trusted publishing.

See the [documentation index](docs/README.md) for installation, usage, CLI,
configuration, API, developer, contributing, troubleshooting, and release guides.

## License

MIT. See [LICENSE](LICENSE).
