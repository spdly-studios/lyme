# Installation

## Requirements

Lyme requires Python 3.11 or newer. Its numerical stack includes PyArrow, pandas,
NumPy, SciPy, scikit-learn, statsmodels, NetworkX, Pint, and python-dateutil. A standard
CPython installation is recommended.

Check the interpreter before installing:

```bash
python --version
python -m pip --version
```

## Install for use

From the repository root:

```bash
python -m pip install .
```

This installs one `lyme` package and creates one `lyme` console command.
The UOC, KSE, and OMS stages live inside the unified package.

Use a virtual environment to isolate dependencies:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate`
on POSIX systems, then install the package.

## Install for development

```bash
python -m pip install -e ".[dev]"
```

The development extra includes Ruff, build, and Twine. Editable mode
loads package code from `src/`, so source changes take effect without reinstalling.

## Verify installation

```bash
python -c "from lyme import Canonicalizer, KnowledgeSynthesisEngine, OperationalModelSynthesizer; print('Lyme ready')"
lyme --help
lyme uoc --help
lyme kse --help
lyme oms --help
```

From a source checkout, run the complete example:

```bash
python examples/pipeline.py
```

Expected output reports 5,000 observations and writes generated files under
`artifacts/pipeline/`. Exact discovery counts can vary with dependency versions.

## Upgrading and uninstalling

```bash
python -m pip install --upgrade .
python -m pip uninstall lyme
```

Package imports use `lyme`; the distribution name used by pip is `lyme`.
