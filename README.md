# NTU Academic-Procedure Chatbot

Vietnamese chatbot grounded on an OWL ontology of academic procedures.
PhoBERT is fine-tuned for **token-level Named Entity Recognition** to detect
mentions of ontology classes in user queries; recognised spans are then
disambiguated against ontology individuals (and their `hasAlias` / `rdfs:label`
literals) via **RapidFuzz**, and per-class **SPARQL** queries over the
**owlready2** world fetch the data that is rendered into a templated reply.

## Architecture

```
user query
    │
    ▼
[ greeting heuristic ]   →  optional greeting block
    │
    ▼
[ PhoBERT NER ]          →  spans tagged with one of 5 ontology classes
    │
    ▼
[ RapidFuzz ]            →  best individual per (span, class)  (skips low score)
    │
    ▼
[ SPARQL ]               →  per-class fetcher returns a structured record
    │
    ▼
[ Renderer ]             →  per-class Vietnamese template; blocks concatenated
```

Composition rule for the final reply:
* greeting *(if detected)* + ontology blocks, when at least one entity matches;
* greeting *(if detected)* alone, otherwise the *out-of-domain* fallback.

## Layout (src-layout)

```
resources/                    static assets shipped with the package
  Ontology_AcademicProcedure_v6.owx
  Ontology_AcademicProcedure_v6.xml
  label_map.json
src/ontchatbot/
  config.py                   paths, model and training hyper-parameters
  pipeline.py                 end-to-end answer() function
  ontology/
    loader.py                 owlready2 load + label-map utilities
    fuzzy.py                  rapidfuzz index per class (label + aliases)
    queries.py                per-class SPARQL fetchers
    response.py               reply templates + composition rule
  data/
    templates.py              dataset-time templates and surface-noise fns
    build_dataset.py          synthetic train/test JSONL generator
  ner/
    preprocessing.py          Vietnamese cleanup + word segmentation
    dataset.py                HF Dataset + sub-word ↔ word label alignment
    train.py                  fine-tuning loop (seqeval metrics, BF16 on CUDA)
    evaluate.py               entity-level benchmark on the test split
    inference.py              text → entity spans
  api/server.py               FastAPI server (serves web/index.html)
  viz/training_curves.py      train/val loss + accuracy + F1 plots
tests/                        pytest suite (42 tests; no model required)
web/index.html                chat UI wired to /chat
dataset/                      generated train.jsonl / test.jsonl
```

## Workflow

```powershell
uv sync                            # install deps (CUDA wheels via uv index)
uv run pytest                      # unit tests (no model needed, ~6 s)
uv run ont-build-dataset           # regenerate dataset/{train,test}.jsonl
uv run ont-train                   # fine-tune PhoBERT NER → models/phobert-ner
uv run ont-evaluate                # entity-level benchmark on the test split
uv run ont-serve --reload          # start the chatbot at http://127.0.0.1:8000
```

`ont-build-dataset` is deterministic (`--seed`); rerun whenever the ontology
changes. The dataset emits one JSONL line per sample: `{"tokens": [...], "ner_tags": [...]}`.
Multi-entity samples are produced by *stitching* two single-entity sentences
with a Vietnamese connector — covering hard cases like *"hp k65 như nào, k67 nữa"*.

## Metrics

Training curves (`out/training/training_curves.png`) plot train loss, val loss,
val accuracy and val F1 (macro). Evaluation (`out/evaluation/`) emits
`test_metrics.json` (token accuracy, entity-level precision/recall/F1
micro & macro) and the seqeval `classification_report.txt`.
