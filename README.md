# \# DocuAudit — Invoice Edition

# 

# A multi-agent pipeline that extracts structured data from native-text invoice PDFs, checks it against compliance rules, and independently verifies every extracted field against its source line before returning it.

# 

# \## Why this exists

# 

# Single-LLM document pipelines can hallucinate, and they give you no way to trace an answer back to the page. DocuAudit separates \*\*extraction\*\* from \*\*verification\*\*: one agent extracts, a different agent checks each field against the exact line of text that should support it. Every field in the output carries its evidence.

# 

# \## How it works

# 

# ```

# Upload PDF → FastAPI → Celery worker → LangGraph pipeline → PostgreSQL

# &#x20;                                         │

# &#x20;             Ingestion → Retrieval → Extraction → Compliance → Auditor

# ```

# 

# | Agent | Job |

# |---|---|

# | Ingestion | Reads the PDF text (PyMuPDF) |

# | Retrieval | Embeds the text (bge-small) and stores/retrieves it in Qdrant |

# | Extraction | Fills a fixed invoice schema using extractive QA (RoBERTa-SQuAD2) |

# | Compliance | PII detection (BERT-NER) plus rules: totals must reconcile, amount threshold, and duplicate invoice numbers (same vendor, checked against previously processed invoices in PostgreSQL) |

# | Auditor | Checks each field against its source line with an NLI model (DeBERTa); unsupported fields are flagged |

# 

# Uploads return immediately with a `doc\_id`. Processing runs in a background worker, and the client polls for the result.

# 

# \## Results

# 

# | Metric | Score |

# |---|---|

# | Field F1 (7 fields) | 1.00 |

# | Faithfulness rate | 1.00 |

# 

# Measured on a small synthetic set of 5 invoices that share one layout. Treat this as a regression baseline, not a claim about real-world accuracy. The evaluation harness fails the build if F1 drops below 0.80 or faithfulness below 0.85.

# 

# \## Run it

# 

# Requires Docker Desktop.

# 

# ```bash

# docker compose up --build -d

# ```

# 

# \- API docs: http://localhost:8000/docs

# \- UI: `cd frontend \&\& streamlit run app.py`

# \- Evaluation: `python evaluation/run\_eval.py`

# \- Tests: `pytest tests/`

# 

# \## API

# 

# | Method | Path | Purpose |

# |---|---|---|

# | POST | `/documents` | Upload a PDF; returns `doc\_id` and status `pending` |

# | GET | `/documents/{doc\_id}` | Status, extracted fields, compliance flags, per-field audit with evidence |

# | GET | `/documents` | List all documents |

# 

# \## Design decisions

# 

# \- \*\*Per-field verification, not one document-level score.\*\* A single "grounded: yes/no" hides which field is wrong. Each field is checked against only the lines that contain its value, which also catches wrong-field mistakes.

# \- \*\*Fixed schema over open-ended QA.\*\* Invoices are structurally regular, so a fixed schema is easier to test and grade.

# \- \*\*Async processing.\*\* The pipeline chains several model calls, which would block a request/response cycle.

# \- \*\*Shared upload volume.\*\* API and worker run in separate containers, so uploads land in a shared volume and the path is stored with the document.

# \- \*\*Deliberate scope.\*\* Native-text invoices only. OCR, table QA and layout-aware retrieval were left out on purpose; they matter for scanned documents.

# \- \*\**Duplicates are keyed on vendor plus invoice number.** Different vendors can reuse the same number, so the number alone would give false alarms.

# 

## Limitations and roadmap

- The evaluation set is small and synthetic; harder layouts and label variations are next.
- The duplicate lookup scans stored results in Python, which is fine at this scale. At larger volumes it should become an indexed database query.
- The auditor flags unsupported fields but does not yet retry extraction or route them to a review queue.
- Retrieval is trivial for one-page invoices; it matters more for longer documents.

# 

# \## Stack

# 

# Python 3.11 · FastAPI · Celery + Redis · LangGraph · Hugging Face Transformers · Qdrant · PostgreSQL · Streamlit · Docker Compose · GitHub Actions

