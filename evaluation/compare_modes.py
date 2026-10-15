"""Run the development set once per language-model mode and compare the results.

    python compare_modes.py              strict, veto and off
    python compare_modes.py strict off   only the modes you name
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "backend"))
sys.path.append(HERE)

import run_eval
from metrics import score_results

MODES = sys.argv[1:] or ["strict", "veto", "off"]
DATASET = os.path.join(HERE, "golden_dataset")

with open(os.path.join(DATASET, "golden.json")) as f:
    golden = json.load(f)

rows = []
for mode in MODES:
    os.environ["DOCUAUDIT_NLI_MODE"] = mode
    print(f"\n=== language-model check: {mode} ===", flush=True)
    predictions = run_eval.predict_all(golden, os.path.join(DATASET, "invoices"))
    report = score_results(golden, predictions)
    to_review = sum(1 for p in predictions.values() if p.get("needs_review"))
    wrong = [m for m in report["mistakes"] if m["verified"] is True]
    rows.append((mode, report["summary"], to_review, wrong))

print("\n" + "=" * 74)
print(f"{'mode':8}{'field_f1':>10}{'faithfulness':>15}{'verified_precision':>21}{'sent to review':>18}")
for mode, s, to_review, wrong in rows:
    print(f"{mode:8}{s['field_f1']:>10}{s['faithfulness']:>15}{s['verified_precision']:>21}"
          f"{to_review:>12} of {len(golden)}")

for mode, s, to_review, wrong in rows:
    if wrong:
        print(f"\nWrong values that were verified in mode '{mode}':")
        for m in wrong:
            print(f"  {m['doc_id']}  {m['field']}: expected {m['gold']!r}, got {m['predicted']!r}")
