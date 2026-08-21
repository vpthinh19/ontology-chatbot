# artifacts/ — what lives where

Git ignores this whole directory. It holds models, training output and speed
measurements produced on this machine.

| Directory | Contents | If lost |
|---|---|---|
| `adapters/` | **The four LoRA adapters** — the training output, the thing worth guarding | Four training runs on a rented machine |
| `training-results/` | Per-question scores for the four models, the run log, and `report/models.json` that the chart builders read | Scores are gone for good (the README numbers come from here); the report is regenerable |
| `serving-models/` | Adapter merged into the base model, in runnable form | Rebuildable from `adapters/`, minutes |
| `benchmarks/` | Speed measurement scripts and results (CT2, PyTorch, ONNX, AOTI) | Rerunnable |
| `figures/` | Builders for the README images | The images themselves live in `docs/images/` |
| `notes/` | Internal reports, audits, review transcripts | History only |

## Where the adapters came from

One training run, `20260819-065533`, on an L4 with 24 GiB.
`adapters/<model>/` is the adapter, `training-results/<model>/` is its own
scorecard. Split apart so the adapters are easy to find, but they belong together.

## The four serving models

| Name | What it is | When to use it |
|---|---|---|
| `merged-bf16/` | Adapter merged into the base model, still in training-library format | Source for the three below, and for PyTorch measurements |
| `t5gemma2-int8/` | Quantized, runs on CPU | Currently serving; every README number was measured on this one |
| `t5gemma2-f32/` | Full precision | The chosen GPU option |
| `t5gemma2-bf16/` | Half precision | Comparison only |

## Rebuilding the README charts

    generate_reports --models-dir artifacts/training-results \
                     --output-dir artifacts/training-results/report
    python artifacts/figures/charts.py
    python artifacts/figures/charts_end_to_end.py

The report goes here, **not** into `resources/reports/`. A test in the repo
requires that once `resources/reports/models.json` exists, the public docs must
spell out every percentage inside it — 108 of them — and the docs are meant to
stay free of per-model detail. Keeping the file here avoids that contract.

## Two things to know before touching anything

**Names are English from now on.** Directories, scripts and result files here use
English names. The image files under `docs/images/` still carry Vietnamese names
because the README links to them by name.

**Old notes mention old paths.** Files under `notes/`, and the measurement
reports inside `benchmarks/`, were written against the previous layout
(`ct2/`, `kq3/`, `do-dau-cuoi-20260819/`). They are records of that moment, so
they stay as written; only runnable scripts were updated.
