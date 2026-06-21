"""Run the complete Lyme API pipeline on sample telemetry.

Install the project first (``pip install .``), then run:

    python examples/pipeline.py
"""

from pathlib import Path

from lyme.kse import KSEConfig, KnowledgeSynthesisEngine, load_from_uoc
from lyme.kse.exporters import (
    GraphJSONExporter,
    MarkdownReportExporter,
    RelationshipsJSONExporter,
    RulesJSONExporter,
)
from lyme.oms import (
    DigitalTwin,
    DigitalTwinPythonExporter,
    JSONTheoryExporter,
    MarkdownTheoryExporter,
    OMSConfig,
    OperationalModelSynthesizer,
)
from lyme.uoc import Canonicalizer, DataType, ExportConfig, UOCConfig


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    input_path = root / "examples" / "data" / "synthetic_system.csv"
    output_dir = root / "artifacts" / "pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Component 1: parse and normalize observations.
    canonicalizer = Canonicalizer(
        UOCConfig(
            type_overrides={
                "temp": DataType.FLOAT,
                "motor_speed": DataType.FLOAT,
                "current_draw": DataType.FLOAT,
                "battery_voltage": DataType.FLOAT,
                "pitch": DataType.FLOAT,
            }
        )
    )
    result = canonicalizer.ingest(input_path, format_name="csv")
    canonicalizer.export(
        "observation", output_dir / "observations.parquet", ExportConfig(format="parquet")
    )
    canonicalizer.export("state_matrix", output_dir / "state_matrix.csv")

    # Component 2: discover relationships, rules, and operational modes.
    ingestion = load_from_uoc(canonicalizer.store, canonicalizer.registry)
    model = KnowledgeSynthesisEngine(KSEConfig(verbose=False)).analyze(ingestion)
    MarkdownReportExporter().export(model, output_dir / "knowledge_report.md")
    GraphJSONExporter().export(model, output_dir / "knowledge_graph.json")
    RelationshipsJSONExporter().export(model, output_dir / "relationships.json")
    RulesJSONExporter().export(model, output_dir / "rules.json")

    # Component 3: synthesize an operational theory and executable twin.
    state_frame = ingestion.raw_df.reset_index()
    theory = OperationalModelSynthesizer(OMSConfig(verbose=False)).synthesize(
        model, df=state_frame
    )
    MarkdownTheoryExporter().export(theory, output_dir / "operational_theory.md")
    JSONTheoryExporter().export(theory, output_dir / "operational_theory.json")
    DigitalTwinPythonExporter().export(theory, output_dir / "digital_twin.py")

    twin = DigitalTwin(
        variable_names=theory.variable_names,
        equations=theory.equations,
        state_machine=theory.state_machine,
    )
    simulated_state = twin.step({"motor_speed": 500.0})

    print(f"Ingested {result.total_records} observations across {result.variable_count} variables.")
    print(f"Discovered {len(model.relationships)} relationships and {len(model.modes)} modes.")
    print(f"Derived {len(theory.equations)} equations; twin has {len(simulated_state)} variables.")
    print(f"Wrote production outputs to {output_dir}")


if __name__ == "__main__":
    main()
