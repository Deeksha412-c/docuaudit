# DocuAudit — Invoice Edition

![CI](https://github.com/Deeksha412-c/docuaudit/actions/workflows/ci.yml/badge.svg)

A multi-agent pipeline that extracts structured data from native-text invoice PDFs and does not trust its own output. Every extracted field is checked against the line it came from before it is accepted, and anything that cannot be verified goes to a review queue instead of being passed on as fact.

## Why

Single-model document pipelines can answer questions about a document, but they can also hallucinate, and they give you no way to trace an answer back to the page. DocuAudit separates **extraction** from **verification**: one stage extracts, a different stage checks each field against its source line. Every field in the output carries its evidence, and the system is measured on whether wrong values get through, not just on whether values are right.

## How it works

```
upload ─► ingestion ─► retrieval ─► extraction ─► compliance ─► audit ─┬─► complete
                                                      ▲                │
                                                      └── repair ◄─────┤  unverified fields (one round)
                                                                       └─► needs_review  (still unverified)
```

An upload returns immediately with a `doc_id` and status `pending`. A background worker runs the pipeline and the client polls for the result.

| Stage | What it does |
|---|---|
| Ingestion | Reads the PDF text with PyMuPDF |
| Retrieval | Embeds the text (`bge-small-en-v1.5`) and stores and retrieves it in Qdrant |
| Extraction | Fills a fixed invoice schema (invoice number, date, vendor, due date, subtotal, tax, total) with extractive QA (`roberta-base-squad2`); answers are kept to one line and extended to the end of that line if cut short |
| Compliance | PII detection (`bert-base-NER`) plus rules: subtotal + tax must equal the total, an amount threshold, and duplicate invoice numbers for the same vendor, checked against earlier invoices in PostgreSQL |
| Audit | Verifies each field (see below) |
| Repair | For fields the audit rejected, tries other phrasings of the question and the text after a colon or on the next line. A replacement is kept only if it passes the audit. Compliance and the audit then run again |

A document is `needs_review` if any field is still unverified, for example when an invoice has no due date.

### The audit

A field is verified only if it passes every check:

1. **Type.** A date field holds a date, an amount field holds an amount, an invoice number contains a digit, and a vendor is not just a label word.
2. **Label.** The line the value came from (plus the label on the line before it, for two-column layouts) must carry the right label for that field and none that conflicts with it. An invoice date cannot be verified as a due date, a subtotal cannot be verified as a total, a print date cannot be verified as an invoice date, and a customer reference cannot be verified as an invoice number.
3. **Language model.** A cross-encoder NLI model (`nli-deberta-v3-base`) checks the labelled line against a plain-English claim such as "The vendor is Acme Ltd." The mode is set with `DOCUAUDIT_NLI_MODE`:
   - `veto` (default): reject only on a clear contradiction
   - `strict`: require clear support
   - `off`: rules only

The rules run before the model because the first evaluation showed the model alone verified wrong values (see Results).

## Results

The evaluation set is 27 invoices with hand-labelled values, including two-column layouts, varied label wording and date and amount formats, invoices with no due date, and compliance cases (an over-threshold amount, a total that does not add up). The PDFs are synthetic, generated with a script.

`verified precision` is the number that matters most: of the values the system verified, how many were correct.

### 1. First evaluation, then fixes (17 invoices)

| Metric | First run | After fixes |
|---|---|---|
| Field F1 | 0.903 | 1.000 |
| Verified precision | 0.877 | 1.000 |
| Fields auto-verified | 0.957 | 0.957 |
| Compliance flag accuracy | 0.882 | 1.000 |
| Missing fields refused | 0 of 2 | 2 of 2 |

The first run showed the audit verifying 14 wrong values: labels extracted as values in two-column layouts, an amount accepted as a date, an invoice date accepted as a due date, and a truncated vendor name. The type and label checks and the layout-aware repair fixed these.

### 2. Held-out test (10 unseen invoices, code frozen beforehand)

| Metric | Score |
|---|---|
| Field F1 | 0.986 |
| Verified precision | 1.000 |
| Fields auto-verified | 0.913 |
| Compliance flag accuracy | 1.000 |
| Missing fields refused | 1 of 1 |
| Invoices sent to review | 4 of 10 |

No wrong value was verified. The one extraction error (a "Document No" label, where the model returned the vendor name) was rejected by the audit. The invoices sent to review were caused by label wordings and a date format the rules did not yet know, plus occasional rejections by the language model. I then fixed those and moved the 10 invoices into the 27-invoice evaluation set, so they are no longer held out.

### 3. Does the language-model check help? (27 invoices)

| Mode | Field F1 | Fields auto-verified | Verified precision | Invoices sent to review |
|---|---|---|---|---|
| strict | 0.995 | 0.952 | 1.000 | 7 of 27 |
| veto | 1.000 | 1.000 | 1.000 | 3 of 27 |
| off (rules only) | 1.000 | 1.000 | 1.000 | 3 of 27 |

The model never changed an outcome in veto mode. In strict mode it declined 8 correct values, sent 4 extra invoices to review and blocked one correct repair, with no gain in precision. The default is therefore `veto`. The 3 invoices still reviewed are the ones with no due date, which is intended.

### Current state

With the default settings, all five metrics are 1.0 on the 27 invoices. A regression gate (`evaluation/run_eval.py`) fails if any wrong value is verified or accuracy drops.

**Read these numbers with care.** The set is small (186 labelled values), synthetic, and the rules were written after seeing failures on it, so 1.0 is a development-set result, not a measure of accuracy on real invoices. The held-out run above, made before those fixes, is the better estimate of generalisation. It also means the comparison in section 3 probably understates what the language model could catch on failure modes I have not seen.

## Run it

Requires Docker Desktop.

```bash
git clone https://github.com/Deeksha412-c/docuaudit.git
cd docuaudit
docker compose up --build -d
```

The first build takes a while, and the first upload downloads the models (about 2 GB, cached afterwards).

- API docs: http://localhost:8000/docs
- UI: `cd frontend && streamlit run app.py`

To run the tests and the evaluation outside Docker you need Python 3.11:

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
docker compose up -d postgres redis qdrant

pytest tests/
python evaluation/run_eval.py                   # the 27 invoices, with the regression gate
python evaluation/compare_modes.py              # language-model modes side by side
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/documents` | Upload a PDF; returns `doc_id` and status `pending` |
| GET | `/documents/{doc_id}` | Status (`pending`, `processing`, `complete`, `needs_review`, `failed`), extracted fields, compliance flags, and per-field audit with evidence |
| GET | `/documents` | List all documents |
| GET | `/health` | Liveness check |

## Design decisions

- **Verification is separate from extraction.** Checking each field against its own source line, with the evidence returned, makes wrong values visible instead of buried in a score.
- **Rules before the model.** Deterministic checks are fast, testable and explainable, and in the evaluation they carried the safety.
- **The default came from an experiment.** The language-model mode was chosen by an ablation, not by assumption.
- **Repair once, accept only verified candidates.** Re-running the same question on the same text gives the same answer, so the repair changes the question and the context.
- **Async processing.** The pipeline chains several model calls, which would block a request. The API and the worker share an uploads volume, and the file path is stored with each document.
- **A fixed schema.** Invoices are structurally regular, so a fixed schema is easier to test and grade than open-ended QA.
- **A gate on the safety metric.** One wrong verified value fails the evaluation.

## Scope

This started as a broader proposal covering scanned and table-heavy documents, vision-language OCR, layout-aware retrieval and reranking. I narrowed it to native-text invoices so I could build one thing properly and measure it. The architecture carries over to other document types by swapping the extraction schema and the label rules.

## Limitations and next steps

- Native-text PDFs only: no OCR, scans or tables.
- The evaluation set is small and synthetic, and the rules were written after seeing failures on it. The next step is a fresh held-out set, including failures the rules do not list.
- The label check assumes labelled fields. A vendor name printed as an unlabelled heading is sent to review.
- The extracted-fields table still shows the model's value for a field it could not verify (for example a guessed due date) next to the warning.
- The review queue is a list: there is no way yet to correct a field and approve a document.
- The duplicate lookup scans stored results in Python, which is fine at this scale. At larger volumes it should be an indexed query.
- CI runs the unit tests. The evaluation gate runs locally because it needs Qdrant and model downloads.
- Retrieval is trivial for one-page invoices. It matters more for longer documents.

## Stack

Python 3.11 · FastAPI · Celery + Redis · LangGraph · Hugging Face Transformers · Qdrant · PostgreSQL · Streamlit · Docker Compose · GitHub Actions

## Repository layout

```
backend/app/
  api/            FastAPI routes
  agents/         ingestion, retrieval, extraction, compliance, auditor, checks (rule-based)
  graph/          LangGraph pipeline with the repair loop
  db/             models, session, duplicate lookup
  workers/        Celery app and task
evaluation/       metrics, run_eval.py, compare_modes.py, golden_dataset/
frontend/         Streamlit UI
tests/            unit tests
docker-compose.yml
```

![A verified invoice](docs/ui-verified.jpeg)
![An invoice sent to review](docs/ui-needs-review.jpeg)