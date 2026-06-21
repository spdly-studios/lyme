"""Unified Lyme command-line entry point."""

from __future__ import annotations

import sys
from collections.abc import Callable

from .kse.cli import main as kse_main
from .oms.cli import main as oms_main
from .uoc.cli import main as uoc_main


def main() -> None:
    commands: dict[str, Callable[[], None]] = {
        "uoc": uoc_main,
        "kse": kse_main,
        "oms": oms_main,
    }
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(
            "usage: lyme {uoc,kse,oms} [options]\n\n"
            "Lyme unified observation-to-digital-twin pipeline\n\n"
            "stages:\n"
            "  uoc  canonicalize observations\n"
            "  kse  synthesize operational knowledge\n"
            "  oms  build an operational model and digital twin\n\n"
            "Run 'lyme <stage> --help' for stage-specific options."
        )
        return

    stage = sys.argv[1]
    if stage not in commands:
        print(f"lyme: unknown stage '{stage}'", file=sys.stderr)
        print("Choose one of: uoc, kse, oms", file=sys.stderr)
        raise SystemExit(2)

    sys.argv = [f"lyme {stage}", *sys.argv[2:]]
    commands[stage]()


if __name__ == "__main__":
    main()
