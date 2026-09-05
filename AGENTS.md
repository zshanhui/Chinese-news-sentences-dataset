# AGENTS.md

Guidance for AI coding agents (Codex, Kimi, Claude, …) working in this repository.

## What this repo is

A Chinese-news **sentence dataset** plus **Jupyter notebooks** that analyse it.
Notebooks are not hand-written: each one is generated from a plain-Python
*cell spec* by a generic builder, then executed with Jupyter. **Never edit the
`.ipynb` JSON by hand** — edit the spec, rebuild, re-execute.

## Layout

```
datasets/25k-chinese-news-sentences.csv   # the data (25,000 sentences, 1,207 articles)
notebooks/<name>.ipynb                    # executed deliverables (committed WITH outputs)
notebooks/specs/<name>.py                 # cell specs — the editable source of truth
outputs/*.csv                             # analysis artifacts (committed)
build_notebook.py                         # generic .ipynb builder (engine, do not specialize)
AGENTS.md                                 # this file
LICENSE
```

Worked example to copy from: `notebooks/specs/dshv4-sentence-analysis.py` →
`notebooks/dshv4-sentence-analysis.ipynb`.

## Environment

- macOS with `uv` available. Project venv already exists at `.venv/` (Python 3.12).
  To recreate it:
  ```bash
  uv venv .venv --python 3.12
  uv pip install --python .venv/bin/python pandas matplotlib jieba jupyter
  ```
  (If a sandbox blocks writes to `~/.cache/uv`, prefix `UV_CACHE_DIR="$PWD/.uv-cache"`.)
- Always run Python through the venv: `.venv/bin/python`, `.venv/bin/jupyter`.
- If matplotlib warns that `~/.matplotlib` is unwritable, set `MPLCONFIGDIR="$PWD/.mplconfig"`.

## The builder contract

`build_notebook.py` is generic. A **cell spec** is a `.py` file that defines:

```python
NB_PATH = "notebooks/my-notebook.ipynb"   # optional; default: notebooks/<spec-stem>.ipynb

CELLS = [
    ("markdown", """# Title

intro markdown…"""),
    ("code", """import pandas as pd
…"""),
    # …more cells…
]
# optional: KERNELSPEC = {"display_name": "Python 3"}  # merged over defaults
```

Each entry is `("markdown" | "code", source_string)`. Write sources as
triple-quoted strings. The builder only assembles the `.ipynb` skeleton
(outputs empty) — see the workflow below.

### Workflow: create / edit a notebook

Run from the repository root:

```bash
# 1. build the skeleton from the spec
.venv/bin/python build_notebook.py notebooks/specs/my-notebook.py
#    (add -o some/other.ipynb to override the output path)

# 2. execute it so outputs/charts are embedded (required before commit/view)
MPLCONFIGDIR="$PWD/.mplconfig" .venv/bin/jupyter nbconvert \
    --to notebook --execute --inplace notebooks/my-notebook.ipynb

# 3. verify: no error outputs, charts present, cells actually executed
.venv/bin/python - <<'EOF'
import nbformat
nb = nbformat.read("notebooks/my-notebook.ipynb", as_version=4)
errs = [o for c in nb.cells if c.cell_type == "code"
        for o in c.get("outputs", []) if o.get("output_type") == "error"]
executed = sum(1 for c in nb.cells if c.cell_type == "code" and c.get("execution_count"))
imgs = sum(1 for c in nb.cells if c.cell_type == "code"
           for o in c.get("outputs", []) if "image/png" in o.get("data", {}))
print(f"cells executed: {executed} | errors: {len(errs)} | png charts: {imgs}")
assert not errs
EOF
```

Python API (for scripts that generate specs programmatically):

```python
from build_notebook import build_notebook, cells_from_spec, validate_cells
cells, nb_path, kernelspec = cells_from_spec("notebooks/specs/x.py")
build_notebook("notebooks/x.ipynb", cells, kernelspec=kernelspec)
```

## Cell-authoring conventions (learned the hard way)

1. **Data-path robustness — mandatory.** When `nbconvert --execute` runs a
   notebook, the kernel's working directory is the notebook's *own directory*
   (i.e. `notebooks/`), not the repo root — but the same notebook may also be
   run from the repo root in Jupyter. Any cell that opens data must tolerate
   both. Use this preamble pattern:

   ```python
   DATA_PATH = "datasets/some.csv"
   if not os.path.exists(DATA_PATH):
       DATA_PATH = os.path.join("..", DATA_PATH)   # kernel cwd == notebooks/
   BASE = os.path.dirname(os.path.abspath(DATA_PATH))
   ```

2. **Write generated artifacts to `<repo-root>/outputs/`**, never next to the
   data. Derive the repo root from `BASE`:

   ```python
   project_root = os.path.dirname(BASE) if os.path.basename(BASE) == "datasets" else BASE
   out_dir = os.path.join(project_root, "outputs")
   os.makedirs(out_dir, exist_ok=True)
   ```

3. **Chinese text in matplotlib charts.** Register a system CJK font before
   plotting, or Chinese labels render as boxes. The preamble in
   `dshv4-sentence-analysis.py` scans `/System/Library/Fonts` etc. for
   PingFang/Heiti/Hiragino/Noto/Arial Unicode and calls
   `matplotlib.font_manager.fontManager.addfont(...)`; copy that cell. Check
   the notebook logs for “Glyph … missing from font” warnings after executing.

4. **jieba.** `import jieba`, `jieba.posseg` for POS-tagged segmentation
   (`pseg.cut`). For domain proper nouns use `jieba.add_word("…")` before
   segmenting. Numbers/punctuation come back as tokens — filter them.

5. **Encoding.** All files are UTF-8. Write Chinese markdown/print text freely.

6. **Execution is not idempotent in place:** always use `--execute --inplace`;
   without `--inplace`, `nbconvert` may write the executed file under a
   different name. Re-run the whole notebook from a clean build if cell code
   changed.

## Git conventions

- Commit both the spec AND its executed notebook when you change analysis
  content (they must stay in sync), plus any changed `outputs/` CSVs.
- `.gitignore` excludes `.venv/`, `.uv-cache/`, `.mplconfig/`, `.ipython/`,
  `.jupyter-*/`, `__pycache__/`, `.ipynb_checkpoints/` — never commit those.
- Short, human-readable commit messages (imperative, ≤ ~70 chars).

## Hints

- The existing notebook is the reference for style: markdown narrative headers
  (`## 1. …`), Chinese labels on plots, a closing “小结与局限” markdown section.
- If a human has the Jupyter server open (http://127.0.0.1:8888), it serves the
  repo root; refreshed notebooks appear without a server restart.
