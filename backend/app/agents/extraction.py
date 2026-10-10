from transformers import AutoTokenizer, AutoModelForQuestionAnswering
import torch
from app.agents.checks import snap_to_line

_tokenizer = None
_model = None


def _get_qa():
    global _tokenizer, _model
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained("deepset/roberta-base-squad2")
        _model = AutoModelForQuestionAnswering.from_pretrained("deepset/roberta-base-squad2")
    return _tokenizer, _model


# The first question is used on the first pass. The others are tried only when the
# auditor rejects the first answer.
FIELD_QUESTIONS = {
    "invoice_number": ["What is the invoice number?", "What is the invoice ID or reference number?"],
    "invoice_date":   ["What is the invoice date?", "On what date was this invoice issued?"],
    "vendor_name":    ["Who is the vendor or seller?", "Which company issued this invoice?"],
    "due_date":       ["What is the payment due date?", "By what date must this invoice be paid?"],
    "subtotal":       ["What is the subtotal amount?", "What is the amount before tax?"],
    "tax":            ["What is the tax amount?", "How much tax is charged?"],
    "total":          ["What is the total amount due?", "What is the final amount payable?"],
}

# Words that mark the lines where each field usually lives.
FIELD_KEYWORDS = {
    "invoice_number": ["invoice number", "invoice no", "invoice #", "invoice id", "reference"],
    "invoice_date":   ["invoice date", "bill date", "date of issue", "issued", "dated", "date"],
    "vendor_name":    ["vendor", "seller", "supplier", "billed by", "from"],
    "due_date":       ["due", "pay by", "payable by"],
    "subtotal":       ["subtotal", "sub total", "sub-total", "before tax"],
    "tax":            ["tax", "vat", "gst"],
    "total":          ["total", "amount due", "amount payable", "balance due"],
}

INVOICE_SCHEMA = {field: questions[0] for field, questions in FIELD_QUESTIONS.items()}


def _answer_question(tokenizer, model, question: str, context: str) -> str:
    inputs = tokenizer(question, context, return_tensors="pt",
                       truncation="only_second", max_length=512)
    with torch.no_grad():
        out = model(**inputs)

    seq_ids = inputs.sequence_ids(0)
    start_logits = out.start_logits[0].tolist()
    end_logits = out.end_logits[0].tolist()

    best_score, best_s, best_e = float("-inf"), 0, 0
    for s, sid in enumerate(seq_ids):
        if sid != 1:          # only consider tokens from the invoice text
            continue
        for e in range(s, min(s + 30, len(seq_ids))):
            if seq_ids[e] != 1:
                continue
            score = start_logits[s] + end_logits[e]
            if score > best_score:
                best_score, best_s, best_e = score, s, e

    ids = inputs["input_ids"][0][best_s:best_e + 1]
    return tokenizer.decode(ids, skip_special_tokens=True).strip()


def extract_invoice_fields(source_text: str) -> dict:
    tokenizer, model = _get_qa()
    results = {}
    for field, questions in FIELD_QUESTIONS.items():
        try:
            value = _answer_question(tokenizer, model, questions[0], source_text)
            results[field] = snap_to_line(value, source_text)
        except Exception:
            results[field] = ""
    return results


def candidate_values(field: str, source_text: str, exclude: str = "") -> list[str]:
    """Alternative answers for one field, used when the first answer failed verification.

    1. Layout candidates: on a line that mentions the field, the value is either after the
       colon ("Due on: 2026-05-02") or, in a two-column layout, on the next line.
    2. Model candidates: the QA model on the focused lines, then on the whole invoice,
       with each alternative phrasing of the question.
    """
    keywords = FIELD_KEYWORDS.get(field, [])
    lines = [l.strip() for l in source_text.split("\n") if l.strip()]
    focused = [l for l in lines if any(k in l.lower() for k in keywords)]

    candidates = []

    def add(value):
        value = (value or "").strip()
        if value and value != exclude and value not in candidates:
            candidates.append(value)

    for i, line in enumerate(lines):
        if not any(k in line.lower() for k in keywords):
            continue
        if ":" in line:
            add(line.split(":", 1)[1])
        elif i + 1 < len(lines):
            add(lines[i + 1])

    tokenizer, model = _get_qa()
    for question in FIELD_QUESTIONS[field]:
        for context in focused + [source_text]:
            try:
                add(snap_to_line(_answer_question(tokenizer, model, question, context), source_text))
            except Exception:
                continue
    return candidates
