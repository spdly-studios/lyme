#!/usr/bin/env python3
"""Command-Line Interface (CLI) for the Universal Observation Canonicalizer (UOC).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    AlignmentStrategy,
    Canonicalizer,
    ExportConfig,
    MissingStrategy,
    UOCConfig,
)


def main() -> None:
    # Reconfigure console output to UTF-8 to prevent encoding crashes on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Lyme - Universal Observation Canonicalizer (UOC) CLI"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="examples/data/spacecraft_telemetry.csv",
        help="Path to the raw telemetry log file to ingest",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output_processed",
        help="Directory to save the canonicalized outputs",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional TOML configuration file",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "json", "kv", "text"),
        help="Input format override; inferred when omitted",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Internal Arrow store flushing batch size",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_file.exists():
        print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print(f"1. Initializing UOC Canonicalizer...")
    
    config = UOCConfig.from_toml(args.config) if args.config else UOCConfig()
    config.batch_size = args.batch_size
    uoc = Canonicalizer(config)
    print("   Canonicalizer initialized successfully.")

    print("\n==================================================")
    print(f"2. Ingesting Input Log: {input_file}...")
    
    # Process & Ingest the input logs
    result = uoc.ingest(input_file, format_name=args.format)
    print(f"   ✓ Ingestion Complete!")
    print(f"   - Processed {result.total_records} records.")
    print(f"   - Identified {result.variable_count} unique variables.")

    print("\n==================================================")
    print("3. Inspecting the Variable Registry...")
    print(f"{'ID':<4} | {'Variable Name':<18} | {'Inferred Type':<15} | {'Unit'}")
    print("-" * 55)
    for var in sorted(uoc.registry, key=lambda v: v.id):
        print(f"{var.id:<4} | {var.name:<18} | {var.dtype.value:<15} | {var.unit}")

    print("\n==================================================")
    print("4. Exporting Normalized Logs...")

    # Path targets
    raw_obs_csv = output_dir / "canonical_triples.csv"
    state_matrix_csv = output_dir / "aligned_state_matrix.csv"
    sparse_coo_csv = output_dir / "sparse_coordinates.csv"

    # Export Mode A: Raw canonical triples (timestamp, variable_id, value)
    uoc.export("observation", raw_obs_csv)
    print(f"   ✓ Raw Observations saved: {raw_obs_csv}")

    # Export Mode B: Aligned State Matrix (Wide-layout table)
    matrix_cfg = ExportConfig(
        alignment_strategy=AlignmentStrategy.FORWARD_FILL,
        missing_strategy=MissingStrategy.LEAVE,
    )
    uoc.export("state_matrix", state_matrix_csv, matrix_cfg)
    print(f"   ✓ Wide Aligned State Matrix saved: {state_matrix_csv}")

    # Export Mode C: Sparse Coordinate Format (COO)
    uoc.export("sparse", sparse_coo_csv)
    print(f"   ✓ Sparse representation saved: {sparse_coo_csv}")

    print("\n==================================================")
    print("Processing pipeline completed successfully!")


if __name__ == "__main__":
    main()
