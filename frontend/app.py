import streamlit as st
import requests
import time

API_BASE = "http://localhost:8000"
FINISHED = ("complete", "needs_review", "failed")

st.title("DocuAudit — Invoice Processing")

uploaded = st.file_uploader("Upload an invoice (PDF)", type=["pdf"])

if uploaded and st.button("Process invoice"):
    files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
    resp = requests.post(f"{API_BASE}/documents", files=files).json()
    doc_id = resp["doc_id"]
    st.info(f"Uploaded. Document ID: {doc_id}")

    progress = st.empty()
    result = None
    for _ in range(90):  # poll for up to ~3 minutes
        r = requests.get(f"{API_BASE}/documents/{doc_id}").json()
        progress.write(f"Status: {r['status']}")
        if r["status"] in FINISHED:
            result = r
            break
        time.sleep(2)

    if result and result["status"] in ("complete", "needs_review"):
        if result["status"] == "needs_review":
            unverified = [f for f, v in result["audit"]["per_field"].items() if not v["supported"]]
            st.warning("Needs review. These fields could not be verified against the invoice: "
                       + ", ".join(unverified))

        st.subheader("Extracted fields")
        st.table(result["extraction"])

        st.subheader("Compliance")
        st.json(result["compliance"])

        st.subheader("Faithfulness audit")
        st.json(result["audit"])
    elif result and result["status"] == "failed":
        st.error("Processing failed. Check the worker logs.")
    else:
        st.warning("Still processing. Check the tables below in a moment.")

st.divider()
docs = requests.get(f"{API_BASE}/documents").json()

st.subheader("Review queue")
waiting = [d for d in docs if d["status"] == "needs_review"]
if waiting:
    st.table(waiting)
else:
    st.write("Nothing is waiting for review.")

st.subheader("All documents")
st.table(docs)