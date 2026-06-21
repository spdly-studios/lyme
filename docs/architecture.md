# Lyme architecture

## System pipeline

```text
CSV / JSON / JSONL / KV / text logs
                 |
                 v
        UOC Canonicalizer
  parser -> normalizers -> registry -> Arrow store
                 |
                 v
       aligned state matrix
                 |
                 v
    KSE KnowledgeSynthesisEngine
 correlation -> temporal -> causal -> rules -> modes -> transitions
                 |
                 v
           SystemModel
                 |
                 v
  OMS OperationalModelSynthesizer
 subsystems -> influence -> state machine -> equations
                 |
                 v
 OperationalTheory + reports + DigitalTwin
```

## UOC: observation canonicalization

The canonicalizer selects a parser, converts parser output into `RawObservation` values,
normalizes timestamps and units, infers or enforces types, registers variables, and appends
typed observations to an Apache Arrow store. The registry is the mapping between user-facing
variable names and compact integer IDs.

Parsers stream records from CSV, JSON, key-value, and text sources. The store separates
float, integer, string, and boolean value columns. Exporters can retain long-form records,
align observations into a wide state matrix, or emit sparse coordinates.

Alignment is deliberately an export/handoff concern. The canonical store preserves the
observations received; KSE receives an aligned view produced either in memory by
`load_from_uoc` or through a state-matrix file.

## KSE: knowledge synthesis

KSE separates numeric variables from reference columns and runs six analysis stages:

1. Pearson, Spearman, and mutual-information findings.
2. Cross-correlation and event-trigger relationships.
3. Candidate-limited Granger tests.
4. Decision-tree threshold rules.
5. Operational-mode clustering.
6. Mode-transition analysis.

`KnowledgeAssembler` merges overlapping evidence, assigns confidence/evidence levels,
builds a knowledge graph, detects contradictions, and returns one `SystemModel`. Analyzer
outputs are hypotheses derived from the supplied observations; they do not establish
physical causality by themselves.

## OMS: operational model synthesis

OMS consolidates likely variable aliases, groups variables into subsystems, traces directed
influence chains and cycles, produces a state machine, and fits empirical equations. When an
aligned DataFrame is supplied, it fits from observations; otherwise it uses operational-mode
centroids as a lower-information fallback.

The result is an `OperationalTheory`. It can be exported as Markdown or JSON, converted into
a standalone twin script, or passed directly to `oms.DigitalTwin` for embedded simulation.
The twin keeps lag history, applies exogenous inputs, evaluates fitted equations, and checks
state-transition triggers on each `step`.

## Process boundaries

The preferred application architecture is an in-memory pipeline. This retains the complete
`SystemModel`, preserves registry metadata, and avoids serialization drift. The three console
commands support batch systems where each stage runs as a separate process. Their shared
files are an interchange format, not the primary object API.

Generated reports and models belong under `artifacts/` (or an application-owned data store),
never inside `src/`. Package source is immutable at runtime.

## Package boundaries

```text
src/lyme/uoc/        ingestion and canonical representation
src/lyme/kse/        statistical analysis and knowledge assembly
src/lyme/oms/        operational theory and simulation
```

The package-root exports documented in `API.md` form the supported integration surface.
Internal analyzers and normalizers remain independently testable but may evolve without the
same compatibility guarantee.
