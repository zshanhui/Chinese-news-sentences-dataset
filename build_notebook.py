#!/usr/bin/env python
"""Generic Jupyter notebook (.ipynb) builder from a plain-Python *cell spec*.

A cell spec is any Python file (convention: notebooks/specs/<name>.py) that
defines the notebook purely as data:

    CELLS = [
        ("markdown", "# Title\\n\\nintro text…"),
        ("code",     "import pandas as pd\\n…"),
        ...
    ]

plus two optional overrides:

    NB_PATH = "notebooks/my-notebook.ipynb"   # default output location
    KERNELSPEC = {"display_name": "Python 3"}  # merged over the default

Cell sources are plain strings — write them as triple-quoted strings for
readability. `cell_type` must be "markdown" or "code".

CLI usage (run from the repository root, with the project venv):

    .venv/bin/python build_notebook.py notebooks/specs/my-notebook.py
    .venv/bin/python build_notebook.py notebooks/specs/my-notebook.py -o out/other.ipynb

Python API usage:

    from build_notebook import build_notebook
    build_notebook("notebooks/x.ipynb", [("markdown", "# X"), ("code", "1 + 1")])

NOTE: this writes an *unexecuted* skeleton (no outputs). Execute the result
before committing / viewing, e.g.:

    .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/my-notebook.ipynb

See AGENTS.md for the full workflow and conventions.
"""

import argparse
import importlib.util
import json
import os
import sys

DEFAULT_KERNELSPEC = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}

VALID_CELL_TYPES = ("markdown", "code")


# --------------------------------------------------------------------------- #
# Cell spec loading
# --------------------------------------------------------------------------- #
def cells_from_spec(spec_path):
    """Import a cell-spec .py file.

    Returns (cells, nb_path, kernelspec):
      cells      — list of (cell_type, source) pairs from the spec's CELLS
      nb_path    — spec's NB_PATH if defined, else None
      kernelspec — spec's KERNELSPEC dict if defined, else None

    Raises ValueError if the spec does not define CELLS or its shape is wrong.
    """
    spec_path = os.path.abspath(spec_path)
    if not os.path.isfile(spec_path):
        raise ValueError(f"cell spec file not found: {spec_path}")
    module_name = "cell_spec_" + os.path.splitext(os.path.basename(spec_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, spec_path)
    if spec is None:
        raise ValueError(f"cannot load spec file: {spec_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    cells = getattr(module, "CELLS", None)
    if cells is None:
        raise ValueError(f"{spec_path} does not define CELLS")
    validate_cells(cells)
    return cells, getattr(module, "NB_PATH", None), getattr(module, "KERNELSPEC", None)


def validate_cells(cells):
    """Check every entry is a ("markdown"|"code", source_string) pair."""
    if not isinstance(cells, (list, tuple)):
        raise ValueError("CELLS must be a list of (cell_type, source) pairs")
    for i, entry in enumerate(cells):
        if not (isinstance(entry, (list, tuple)) and len(entry) == 2):
            raise ValueError(f"CELLS[{i}] is not a (cell_type, source) pair")
        cell_type, source = entry
        if cell_type not in VALID_CELL_TYPES:
            raise ValueError(
                f"CELLS[{i}] has unknown cell_type {cell_type!r}; "
                f"expected one of {VALID_CELL_TYPES}")
        if not isinstance(source, str):
            raise ValueError(f"CELLS[{i}] source must be a string, got {type(source).__name__}")


# --------------------------------------------------------------------------- #
# Notebook serialization
# --------------------------------------------------------------------------- #
def build_notebook(nb_path, cells, kernelspec=None, language_version="3.12"):
    """Serialize (cell_type, source) pairs into an nbformat-4.5 .ipynb file.

    Args:
        nb_path:         destination .ipynb path
        cells:           list of ("markdown"|"code", source_string) pairs
        kernelspec:      optional dict merged over DEFAULT_KERNELSPEC
        language_version: value stored in language_info.version

    Returns the path written.
    """
    validate_cells(cells)
    out_dir = os.path.dirname(os.path.abspath(nb_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    out_cells = []
    for i, (cell_type, source) in enumerate(cells):
        out_cells.append({
            "id": f"cell-{i:02d}",  # nbformat >=5.10 requires unique cell ids
            "cell_type": cell_type,
            "metadata": {},
            "source": source.splitlines(keepends=True),
            "outputs": [] if cell_type == "code" else None,
            "execution_count": None if cell_type == "code" else None,
        })

    ks = dict(DEFAULT_KERNELSPEC)
    if kernelspec:
        ks.update(kernelspec)

    nb = {
        "cells": out_cells,
        "metadata": {
            "kernelspec": ks,
            "language_info": {"name": ks["language"], "version": language_version},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    return nb_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _default_output_path(spec_path, nb_path_from_spec):
    """-o flag wins; then the spec's NB_PATH; else notebooks/<spec-stem>.ipynb."""
    if nb_path_from_spec:
        return nb_path_from_spec
    stem = os.path.splitext(os.path.basename(spec_path))[0]
    return os.path.join("notebooks", stem + ".ipynb")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="build_notebook.py",
        description="Build an .ipynb skeleton from a Python cell-spec file.",
        epilog="Example: .venv/bin/python build_notebook.py notebooks/specs/my-notebook.py",
    )
    parser.add_argument("spec", help="path to a cell-spec .py file defining CELLS")
    parser.add_argument("-o", "--output", metavar="OUT.ipynb",
                        help="output path (defaults to the spec's NB_PATH, "
                             "else notebooks/<spec-stem>.ipynb)")
    parser.add_argument("--language-version", default="3.12",
                        help="Python version recorded in the notebook metadata")
    args = parser.parse_args(argv)

    cells, nb_path_from_spec, kernelspec = cells_from_spec(args.spec)
    out_path = args.output or _default_output_path(args.spec, nb_path_from_spec)
    build_notebook(out_path, cells, kernelspec=kernelspec,
                   language_version=args.language_version)
    print(f"written: {out_path} | cells: {len(cells)}")
    print("note: skeleton only — execute with jupyter nbconvert before use/commit.")


if __name__ == "__main__":
    main()
