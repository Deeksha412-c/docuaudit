from langgraph.graph import StateGraph, END
from typing import TypedDict

class InvoiceState(TypedDict):
    doc_id: str
    source_text: str
    fields: dict
    compliance: dict
    audit: dict

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
    return {"compliance": scan_invoice_compliance(state["source_text"], state["fields"], seen_invoice_numbers=set())}

def audit_node(state: InvoiceState):
    from app.agents.auditor import audit_fields
    return {"audit": audit_fields(state["fields"], state["source_text"])}

graph = StateGraph(InvoiceState)
graph.add_node("retrieval", retrieval_node)
graph.add_node("extraction", extraction_node)
graph.add_node("compliance", compliance_node)
graph.add_node("audit", audit_node)
graph.set_entry_point("retrieval")
graph.add_edge("retrieval", "extraction")
graph.add_edge("extraction", "compliance")
graph.add_edge("compliance", "audit")
graph.add_edge("audit", END)

pipeline = graph.compile()