import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "backend"))
sys.path.append(HERE)

from metrics import score_results

# python run_eval.py           -> development set (golden_dataset), with the regression gate
# python run_eval.py heldout   -> held-out set: a measurement only, no gate. Never tune on it.
DATASET = sys.argv[1] if len(sys.argv) > 1 else "golden_dataset"
GOLDEN = os.path.join(HERE, DATASET, "golden.json")
INVOICES = os.path.join(HERE, DATASET, "invoices")

# Minimum acceptable scores on the development set. A single wrong verified value fails the build.
BASELINE = {
    "field_f1": 0.95,
    "faithfulness": 0.92,
    "verified_precision": 1.0,
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

    predictions = predict_all(golden)
    report = score_results(golden, predictions)
    summary = report["summary"]
    to_review = sum(1 for p in predictions.values() if p.get("needs_review"))

    print(f"\nDataset: {DATASET} ({len(golden)} invoices)")
    print("Per-field F1:", report["per_field"])
    print("Scorecard:", json.dumps(summary, indent=2))
    print(f"Invoices sent to review: {to_review} of {len(golden)}")

    unverified = [(doc_id, f, r) for doc_id, p in predictions.items()
                  for f, r in p["audit"]["per_field"].items() if not r["supported"]]
    if unverified:
        print(f"\nNot auto-verified ({len(unverified)}):")
        for doc_id, f, r in unverified:
            why = r.get("reason") or f"language model not convinced (confidence {r.get('confidence')})"
            print(f"  {doc_id}  {f}: {predictions[doc_id]['fields'].get(f)!r} -> {why}")

    if report["mistakes"]:
        print(f"\nMistakes ({len(report['mistakes'])}):")
        for m in report["mistakes"]:
            if m["verified"] is None:
                note = ""
            else:
                note = "   <-- VERIFIED BUT WRONG" if m["verified"] else "   (caught by the auditor)"
            print(f"  {m['doc_id']}  {m['field']}: expected {m['gold']!r}, got {m['predicted']!r}{note}")

    if DATASET != "golden_dataset":
        print("\nThis is a measurement, so the regression gate is not applied.")
        return

    failed = [k for k, v in BASELINE.items() if summary.get(k, 1.0) < v]
    if failed:
        print("\nREGRESSION GATE FAILED on:", failed)
        sys.exit(1)
    print("\nRegression gate passed.")


if __name__ == "__main__":
    run()
