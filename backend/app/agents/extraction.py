# backend/app/agents/extraction.py
from transformers import AutoTokenizer, AutoModelForQuestionAnswering
import torch

_tokenizer = None
_model = None

def _get_qa():
    global _tokenizer, _model
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained("deepset/roberta-base-squad2")
        _model = AutoModelForQuestionAnswering.from_pretrained("deepset/roberta-base-squad2")
    return _tokenizer, _model

INVOICE_SCHEMA = {
    "invoice_number": "What is the invoice number?",
    "invoice_date":   "What is the invoice date?",
    "vendor_name":    "Who is the vendor or seller?",
    "due_date":       "What is the payment due date?",
    "subtotal":       "What is the subtotal amount?",
    "tax":            "What is the tax amount?",
    "total":          "What is the total amount due?",
}

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
    for field, question in INVOICE_SCHEMA.items():
        try:
            results[field] = _answer_question(tokenizer, model, question, source_text)
        except Exception:
            results[field] = ""
    return results