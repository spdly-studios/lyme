# Usage guide

## Choosing a workflow

The preferred workflow is an in-memory Python pipeline:

```text
input files -> Canonicalizer -> load_from_uoc -> KnowledgeSynthesisEngine
            -> OperationalModelSynthesizer -> reports / DigitalTwin
```

Choose the file-based CLI pipeline when stages run in different jobs. Choose a partial
pipeline when you only need canonicalization or discovery.

## Complete Python pipeline

```python
from pathlib import Path

from lyme.kse import KSEConfig, KnowledgeSynthesisEngine, load_from_uoc
from lyme.kse.exporters import MarkdownReportExporter
from lyme.oms import DigitalTwin, JSONTheoryExporter, OMSConfig, OperationalModelSynthesizer
from lyme.uoc import Canonicalizer, DataType, ExportConfig, UOCConfig

output = Path("artifacts/run")
output.mkdir(parents=True, exist_ok=True)

uoc = Canonicalizer(UOCConfig(
    type_overrides={"temperature": DataType.FLOAT},
    unit_overrides={"temperature": "degC"},
))
stats = uoc.ingest(Path("telemetry.csv"), format_name="csv")
uoc.export("observation", output / "observations.parquet", ExportConfig(format="parquet"))
uoc.export("state_matrix", output / "state_matrix.csv")

ingestion = load_from_uoc(uoc.store, uoc.registry)
model = KnowledgeSynthesisEngine(KSEConfig(verbose=False)).analyze(ingestion)
MarkdownReportExporter().export(model, output / "knowledge.md")

aligned = ingestion.raw_df.reset_index()
theory = OperationalModelSynthesizer(OMSConfig(verbose=False)).synthesize(model, df=aligned)
JSONTheoryExporter().export(theory, output / "theory.json")

twin = DigitalTwin(theory.variable_names, theory.equations, theory.state_machine)
next_state = twin.step({"motor_speed": 500.0})
```

## UOC input formats

### CSV and TSV

Tabular inputs need a timestamp-like column. Configure a nonstandard name or delimiter
with `ParserConfig`. Every non-timestamp cell becomes an observation.

### JSON and JSONL

JSON objects, arrays, and line-delimited objects are accepted. Nested dictionaries are
flattened to dotted variable names such as `sensor.temperature`.

### Key-value logs

Records such as `time=100,temp=30.5,motor=400` are supported. Customize separators in
`ParserConfig` when input conventions differ.

### Text logs

The text parser extracts recognized timestamp/value patterns. Unmatched lines become a
`log_line` variable. Add named-group regular expressions through `text_patterns` for
domain-specific lines.

## Type and unit behavior

UOC infers boolean, integer, float, timestamp, string, and categorical data. A variable
can upgrade to a wider type when later values require it. Production pipelines should set
`type_overrides` where schema stability matters.

Units are parsed and converted with Pint. Define `unit_overrides` for a stable output unit.
Invalid or dimensionally incompatible target units fail normalization, so test unit maps
with representative data before deployment.

## UOC outputs

- `observation`: long-form canonical records, suitable for storage and audits.
- `state_matrix`: timestamp-indexed wide data used by KSE.
- `sparse`: coordinate-form non-null observations for sparse systems.

State-matrix alignment determines how asynchronous variables share a row. Exact alignment
preserves only simultaneous observations; nearest selects the closest value; forward-fill
carries the last value; interpolation estimates numeric values between known points.

## Using KSE with existing DataFrames

```python
import pandas as pd
from lyme.kse import KnowledgeSynthesisEngine, load_dataframe

df = pd.read_csv("already_aligned.csv")
model = KnowledgeSynthesisEngine().analyze(load_dataframe(df))
```

The table must have a `timestamp` column or index. KSE sorts timestamps and analyzes columns
whose non-null data is at least 80% numerically coercible. Inspect `ingestion.numeric_df`
and `ingestion.raw_df` when a column is unexpectedly excluded.

## Understanding KSE results

Findings represent statistical evidence. Relationships add direction or lag. Rules describe
threshold conditions. Modes summarize recurring operating regimes. Mode transitions describe
observed movement between regimes. Contradictions retain incompatible evidence rather than
silently discarding it.

Confidence is an evidence score produced by the implementation, not a safety guarantee.
Granger results indicate predictive precedence, not necessarily physical causation.

## OMS and twins

Always pass the aligned DataFrame to OMS when it is available. Without it, equations use
mode centroids and have less evidence. `OperationalTheory` contains subsystems, influence
chains, feedback loops, state summaries, equations, explanations, and resolved conflicts.

The embedded `DigitalTwin` maintains variable history for lagged equations. Inputs supplied
to `step()` are treated as exogenous for that step; fitted equations update other variables.
Call `reset(initial_values)` between independent simulations. Unknown input variables are
ignored, so validate input names against `theory.variable_names` in calling applications.

## Outputs and reproducibility

Persist input checksums, configuration, package/dependency versions, reports, and JSON models
for auditable runs. Clustering and learned equations can vary across numerical-library versions.
Never treat generated Python twins from untrusted sources as safe executable code.
