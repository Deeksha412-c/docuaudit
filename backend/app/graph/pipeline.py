from langgraph.graph import StateGraph, END
from typing import TypedDict

# One repair round only: the repair step already tries every alternative question and
# every focused line in a single pass, so a second round would produce the same candidates.
MAX_REPAIR_ROUNDS = 1


class InvoiceState(TypedDict, total=False):
    doc_id: str
    source_text: str
    fields: dict
    compliance: dict
    audit: dict
    repair_rounds: int
    needs_review: bool


def retrieval_node(state: InvoiceState):
    from app.agents.retrieval import retrieve
    chunks = retrieve("invoice details", state["doc_id"], k=3)
    text = "\n".join(chunks) if chunks else state["source_text"]
    return {"source_text": text}


def extraction_node(state: InvoiceState):
    from app.agents.extraction import extract_invoice_fields
    return {"fields": extract_invoice_fields(state["source_text"])}


def compliance_node(state: InvoiceState):
    from app.agents.compliance import scan_invoice_compliance
    from app.db.session import SessionLocal
    from app.db.queries import previously_seen_invoice_numbers

    try:
        db = SessionLocal()
        try:
            seen = previously_seen_invoice_numbers(db, state["doc_id"], state["fields"])
        finally:
            db.close()
    except Exception as e:
        print(f"Warning: duplicate lookup skipped ({e})")
        seen = set()

    return {"compliance": scan_invoice_compliance(
        state["source_text"], state["fields"], seen_invoice_numbers=seen)}


def audit_node(state: InvoiceState):
    from app.agents.auditor import audit_fields
    return {"audit": audit_fields(state["fields"], state["source_text"])}


def route_after_audit(state: InvoiceState):
    unsupported = [f for f, r in state["audit"]["per_field"].items() if not r["supported"]]
    if unsupported and state.get("repair_rounds", 0) < MAX_REPAIR_ROUNDS:
        return "repair"
    return "finalize"


def repair_node(state: InvoiceState):
    """Try alternative answers for every field the auditor rejected; keep one only if it verifies."""
    from app.agents.extraction import candidate_values
    from app.agents.auditor import audit_fields

    fields = dict(state["fields"])
    for field, result in state["audit"]["per_field"].items():
        if result["supported"]:
            continue
        for candidate in candidate_values(field, state["source_text"], exclude=fields.get(field, "")):
            check = audit_fields({field: candidate}, state["source_text"])
            if check["per_field"][field]["supported"]:
                fields[field] = candidate
                break
    return {"fields": fields, "repair_rounds": state.get("repair_rounds", 0) + 1}


def finalize_node(state: InvoiceState):
    return {"needs_review": state["audit"]["faithfulness_rate"] < 1.0}


graph = StateGraph(InvoiceState)
graph.add_node("retrieval", retrieval_node)
graph.add_node("extraction", extraction_node)
graph.add_node("compliance", compliance_node)
graph.add_node("audit", audit_node)
graph.add_node("repair", repair_node)
graph.add_node("finalize", finalize_node)

graph.set_entry_point("retrieval")
graph.add_edge("retrieval", "extraction")
graph.add_edge("extraction", "compliance")
graph.add_edge("compliance", "audit")
graph.add_conditional_edges("audit", route_after_audit, {"repair": "repair", "finalize": "finalize"})
graph.add_edge("repair", "compliance")
graph.add_edge("finalize", END)

pipeline = graph.compile()