import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "backend"))
sys.path.append(HERE)

from metrics import score_results

GOLDEN = os.path.join(HERE, "golden_dataset", "golden.json")
INVOICES = os.path.join(HERE, "golden_dataset", "invoices")

# Minimum acceptable scores. After your first run on the harder set, look at the mistakes,
# then set each value just below what you measured, so any later drop fails the build.
BASELINE = {
    "field_f1": 0.95,
    "faithfulness": 0.92,
    "verified_precision": 1.0,     # safety metric: one wrong verified value should fail the build
    "flag_accuracy": 0.95,
    "absent_fields_flagged": 1.0,
}


def predict_all(golden):
    from app.graph.pipeline import pipeline
    from app.agents.ingestion import ingest_invoice, full_text
    from app.agents.retrieval import index_invoice
    import app.db.queries as queries

    # keep the evaluation independent of whatever invoices are stored in the database
    queries.previously_seen_invoice_numbers = lambda db, doc_id, fields: set()

    predictions = {}
    for item in golden:
        pdf = os.path.join(INVOICES, f"{item['doc_id']}.pdf")
        text = full_text(ingest_invoice(pdf))
        index_invoice(item["doc_id"], [text])
        predictions[item["doc_id"]] = pipeline.invoke({"doc_id": item["doc_id"], "source_text": text})
        print(f"processed {item['doc_id']}", flush=True)
    return predictions


def run():
    with open(GOLDEN) as f:
        golden = json.load(f)

    report = score_results(golden, predict_all(golden))
    summary = report["summary"]

    print("\nPer-field F1:", report["per_field"])
    print("Scorecard:", json.dumps(summary, indent=2))

    if report["mistakes"]:
        print(f"\nMistakes ({len(report['mistakes'])}):")
        for m in report["mistakes"]:
            if m["verified"] is None:
                note = ""
            else:
                note = "   <-- VERIFIED BUT WRONG" if m["verified"] else "   (caught by the auditor)"
            print(f"  {m['doc_id']}  {m['field']}: expected {m['gold']!r}, got {m['predicted']!r}{note}")

    failed = [k for k, v in BASELINE.items() if summary.get(k, 1.0) < v]
    if failed:
        print("\nREGRESSION GATE FAILED on:", failed)
        sys.exit(1)
    print("\nRegression gate passed.")


if __name__ == "__main__":
    run()