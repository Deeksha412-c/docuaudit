import json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "backend"))
sys.path.append(HERE)

from metrics import compute_f1
from app.graph.pipeline import pipeline as invoice_pipeline
from app.agents.ingestion import ingest_invoice, full_text
from app.agents.retrieval import index_invoice

BASELINE = {"field_f1": 0.80, "faithfulness": 0.85}
GOLDEN = os.path.join(HERE, "golden_dataset", "golden.json")
INVOICES = os.path.join(HERE, "golden_dataset", "invoices")

def run():
    with open(GOLDEN) as f:
        golden = json.load(f)

    field_scores, faith_scores = [], []
    per_field = {}
    for item in golden:
        pdf = os.path.join(INVOICES, f"{item['doc_id']}.pdf")
        text = full_text(ingest_invoice(pdf))
        index_invoice(item["doc_id"], [text])
        pred = invoice_pipeline.invoke({"doc_id": item["doc_id"], "source_text": text})

        for field, gold_val in item["gold_fields"].items():
            s = compute_f1(pred["fields"].get(field, ""), gold_val)
            field_scores.append(s)
            per_field.setdefault(field, []).append(s)
        faith_scores.append(pred["audit"]["faithfulness_rate"])

    scorecard = {
        "field_f1": round(sum(field_scores) / len(field_scores), 3),
        "faithfulness": round(sum(faith_scores) / len(faith_scores), 3),
    }
    print("Per-field F1:", {k: round(sum(v) / len(v), 3) for k, v in per_field.items()})
    print("Scorecard:", json.dumps(scorecard, indent=2))

    failed = [k for k in BASELINE if scorecard[k] < BASELINE[k]]
    if failed:
        print("REGRESSION GATE FAILED on:", failed)
        sys.exit(1)
    print("Regression gate passed.")

if __name__ == "__main__":
    run()