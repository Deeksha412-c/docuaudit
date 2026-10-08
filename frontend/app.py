import streamlit as st
import requests
import time

API_BASE = "http://localhost:8000"

st.title("DocuAudit — Invoice Processing")

uploaded = st.file_uploader("Upload an invoice (PDF)", type=["pdf"])

if uploaded and st.button("Process invoice"):
    files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
    resp = requests.post(f"{API_BASE}/documents", files=files).json()
    doc_id = resp["doc_id"]
    st.info(f"Uploaded. Document ID: {doc_id}")

    progress = st.empty()
    result = None
    for _ in range(60):  # poll up to ~2 minutes
        r = requests.get(f"{API_BASE}/documents/{doc_id}").json()
        progress.write(f"Status: {r['status']}")
        if r["status"] in ("complete", "failed"):
            result = r
            break
        time.sleep(2)

    if result and result["status"] == "complete":
        st.subheader("Extracted fields")
        st.table(result["extraction"])

        st.subheader("Compliance")
        st.json(result["compliance"])

        st.subheader("Faithfulness audit")
        st.json(result["audit"])
    elif result and result["status"] == "failed":
        st.error("Processing failed — check the worker logs.")

st.divider()
st.subheader("All documents")
docs = requests.get(f"{API_BASE}/documents").json()
st.table(docs)