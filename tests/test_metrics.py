import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "evaluation"))
from metrics import compute_f1

def test_compute_f1_exact_match():
    assert compute_f1("INV-2026-0143", "INV-2026-0143") == 1.0

def test_compute_f1_no_overlap():
    assert compute_f1("apples", "oranges") == 0.0

def test_compute_f1_empty_prediction():
    assert compute_f1("", "some value") == 0.0