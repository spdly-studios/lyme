#!/usr/bin/env python3
"""Command-Line Interface (CLI) for the Knowledge Synthesis Engine (KSE)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import KnowledgeSynthesisEngine
from .config import KSEConfig
from .exporters import (
    GraphJSONExporter,
    MarkdownReportExporter,
    RelationshipsJSONExporter,
    RulesJSONExporter,
)
from .ingestion import load_csv, load_parquet


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Lyme - Knowledge Synthesis Engine (KSE) CLI")
    parser.add_argument(
        "--input",
        type=str,
        default="output_processed/aligned_state_matrix.csv",
        help="Path to the aligned state matrix CSV/Parquet file from Component 1 (UOC)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output_processed",
        help="Directory to save KSE synthesised knowledge files",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(
            f"Error: Input file '{input_path}' not found.\n"
            f"Please run Component 1 canonicalizer first:\n"
            f"  lyme uoc\n",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print("1. Loading aligned telemetry observations...")
    if input_path.suffix.lower() == ".parquet":
        ingest_res = load_parquet(input_path)
    else:
        ingest_res = load_csv(input_path)
    print(f"   ✓ Ingested {ingest_res.n_timestamps} states containing {ingest_res.n_numeric_variables} variables.")

    print("\n==================================================")
    print("2. Synthesizing system model and operational rules...")
    config = KSEConfig(verbose=True)
    engine = KnowledgeSynthesisEngine(config)
    model = engine.analyze(ingest_res)

    print("\n==================================================")
    print("3. Exporting synthesised operational knowledge...")

    report_file = output_dir / "kse_report.md"
    graph_file = output_dir / "kse_graph.json"
    rules_file = output_dir / "kse_rules.json"
    rel_file = output_dir / "kse_relationships.json"

    MarkdownReportExporter().export(model, report_file)
    print(f"   ✓ Markdown Report saved to:       {report_file}")

    GraphJSONExporter().export(model, graph_file)
    print(f"   ✓ Knowledge Graph saved to:       {graph_file}")

    RulesJSONExporter().export(model, rules_file)
    print(f"   ✓ Rule set saved to:              {rules_file}")

    RelationshipsJSONExporter().export(model, rel_file)
    print(f"   ✓ Relationships database saved to: {rel_file}")

    print("\n==================================================")
    print("Knowledge Synthesis completed successfully!")
    print("Please view the Markdown report for human-readable findings.")


if __name__ == "__main__":
    main()
