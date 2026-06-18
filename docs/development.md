# Developer guide

## Repository layout

```text
src/cognis_os/       unified production package and CLI
  uoc/               canonicalization stage
  kse/               discovery stage
  oms/               synthesis stage
examples/      supported end-to-end example and sample inputs
docs/          user and maintainer documentation
artifacts/     ignored generated output
```

The project uses a `src` layout. Do not add import-path hacks or repository wrapper scripts.
Install editable mode for local development.

## Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

## Quality checks

```bash
python -m ruff check src examples
python -m compileall -q src examples
python examples/pipeline.py
```

The final command is a contract test for documented API composition. Generated files belong
under `artifacts/` and should not be committed.

## Design rules

- Keep package-root imports backward compatible when possible.
- Keep UOC domain-independent; application-specific schema belongs in configuration.
- Preserve raw evidence and metadata through handoffs.
- Avoid silently converting analysis failures into confident findings.
- Use dataclasses for configuration and model records unless behavior requires a class.
- Keep CLI code thin; business logic belongs in importable APIs.
- Do not make source code depend on sample files or the repository working directory.

## Adding an input parser

Implement `BaseParser.parse` and `can_parse`, yield `RawObservation`, register the parser in
`Canonicalizer`, and validate sniffing and explicit formats. Streaming sources must be closed only
when the parser opened them.

## Adding an analyzer

Implement the analyzer contract, return `AnalyzerResult`, add configuration fields, wire it
into `KnowledgeSynthesisEngine`, and define how its evidence merges in the assembler. Test
empty, missing, constant, short, and valid datasets.

## Adding an exporter

Exporters should accept model objects and `Path`/stream destinations where the surrounding
package does. Create parent directories only when that behavior is consistent with existing
exporters. Test encoding, empty outputs, NumPy values, and serialization round trips.

## Compatibility and documentation

When public signatures, defaults, filenames, or CLI flags change, update `README.md`,
`docs/API.md`, the relevant guide, and the end-to-end example in the same change.
