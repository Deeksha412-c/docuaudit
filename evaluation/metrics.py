def _norm(s) -> str:
    s = str(s).lower().replace("$", "").replace(",", "").strip()
    return s.rstrip(".")

def compute_f1(pred: str, gold: str) -> float:
    pred_tokens, gold_tokens = set(_norm(pred).split()), set(_norm(gold).split())
    if not pred_tokens or not gold_tokens:
        return 0.0
    overlap = pred_tokens & gold_tokens
    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(gold_tokens)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)