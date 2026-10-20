import html
import os
import time

import requests
import streamlit as st

from ui_helpers import field_rows, flag_label, render_pages, risk_pill, status_pill

API_BASE = os.environ.get("DOCUAUDIT_API", "http://localhost:8000")
FINISHED = ("complete", "needs_review", "failed")

st.set_page_config(page_title="DocuAudit", layout="wide")

st.markdown("""
<style>
header[data-testid="stHeader"], footer, #MainMenu {display: none;}
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1100px;}
html, body, [class*="css"] {font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;}
h1 {font-size: 1.6rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0;}
.muted {color: #6b7280; font-size: 0.88rem;}
.meta {display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 6px 0 4px 0;}
.pill {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.76rem;
       font-weight: 500; border: 1px solid; white-space: nowrap;}
.pill.ok {color: #146c43; background: #e9f6ef; border-color: #bfe3cf;}
.pill.warn {color: #8a5a00; background: #fff5de; border-color: #f0dba8;}
.pill.bad {color: #a12622; background: #fdeceb; border-color: #f3c4c1;}
.pill.muted {color: #4b5563; background: #f3f4f6; border-color: #e0e3e8;}
.callout {border-left: 3px solid #e0a82e; background: #fffaf0; padding: 10px 14px;
          margin: 12px 0 18px 0; font-size: 0.92rem; color: #3b3320;}
.row {display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
      padding: 11px 0; border-bottom: 1px solid #eceef2;}
.label {color: #6b7280; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em;}
.value {font-size: 1.02rem; font-weight: 500; margin-top: 1px;}
.value.off {color: #9aa1ad; font-weight: 400;}
.guess {color: #8b93a1; font-size: 0.8rem; margin-top: 2px;}
.legend {color: #6b7280; font-size: 0.8rem; margin-top: 6px;}
.dot {display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin: 0 4px 0 10px;}
.dot.g {background: #21a35c; margin-left: 0;}
.dot.a {background: #d98a1a;}
.ev {margin: 0 0 14px 0;}
.ev code {display: block; background: #f6f7f9; border: 1px solid #eceef2; border-radius: 6px;
          padding: 6px 10px; font-size: 0.84rem; margin-top: 3px; color: #1c1f26;}
</style>
""", unsafe_allow_html=True)


def esc(text):
    return html.escape(str(text))


def pill(text, kind):
    return f'<span class="pill {kind}">{esc(text)}</span>'


def api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def process(uploaded):
    try:
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        response = requests.post(f"{API_BASE}/documents", files=files, timeout=30).json()
        doc_id = response["doc_id"]
    except Exception:
        st.error(f"Could not reach the API at {API_BASE}. Is Docker running?")
        return

    result = None
    with st.spinner("Reading and checking the invoice. The first one after a restart takes longer."):
        for _ in range(90):
            r = api_get(f"/documents/{doc_id}")
            if r and r.get("status") in FINISHED:
                result = r
                break
            time.sleep(2)

    if result is None:
        st.info("Still processing. It will appear under All documents when it finishes.")
        return
    st.session_state["doc"] = {"result": result, "pdf": uploaded.getvalue(), "name": uploaded.name}


def render_result(doc):
    result = doc["result"]
    rows = field_rows(result)
    status = result.get("status")
    compliance = result.get("compliance") or {}

    pills = [pill(*status_pill(status))]
    if compliance.get("risk_level"):
        pills.append(pill(*risk_pill(compliance["risk_level"])))
    verified = sum(1 for r in rows if r["verified"])
    st.markdown(
        f'<div class="meta"><span class="muted">{esc(doc["name"])}</span>{"".join(pills)}'
        f'<span class="muted">{verified} of {len(rows)} fields verified</span></div>',
        unsafe_allow_html=True,
    )

    if status == "failed":
        st.error("Processing failed. Check the worker logs.")
        return

    unverified = [r["label"] for r in rows if not r["verified"]]
    if status == "needs_review" and unverified:
        st.markdown(
            f'<div class="callout">A person should check this invoice. Could not verify: '
            f'{esc(", ".join(unverified).lower())}.</div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns([1, 1], gap="large")
    with left:
        try:
            for image in render_pages(doc["pdf"], rows):
                st.image(image)
            st.markdown(
                '<div class="legend"><span class="dot g"></span>verified'
                '<span class="dot a"></span>not verified</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown('<p class="muted">Preview not available.</p>', unsafe_allow_html=True)

    with right:
        for r in rows:
            if r["verified"]:
                body = f'<div class="value">{esc(r["value"])}</div>'
                badge = pill("Verified", "ok")
            else:
                guess = f'<div class="guess">Guess: {esc(r["value"])}. {esc(r["note"])}</div>' if r["value"] \
                    else f'<div class="guess">{esc(r["note"])}</div>'
                body = f'<div class="value off">Not verified</div>{guess}'
                badge = pill("Review", "warn")
            st.markdown(
                f'<div class="row"><div><div class="label">{esc(r["label"])}</div>{body}</div>{badge}</div>',
                unsafe_allow_html=True,
            )


def table_of(documents):
    return [
        {"File": d.get("filename"), "Status": status_pill(d.get("status"))[0], "ID": str(d.get("doc_id", ""))[:8]}
        for d in documents
    ]


st.markdown("# DocuAudit")
st.markdown(
    '<p class="muted">Every extracted field is checked against its source line before it is accepted.</p>',
    unsafe_allow_html=True,
)

uploaded = st.file_uploader("Invoice PDF", type=["pdf"], label_visibility="collapsed")
if uploaded is not None and st.button("Process invoice", type="primary"):
    process(uploaded)

doc = st.session_state.get("doc")
if doc:
    render_result(doc)

st.divider()

documents = api_get("/documents") or []
queue = [d for d in documents if d.get("status") == "needs_review"]
names = (["Compliance", "Evidence"] if doc else []) + [f"Review queue ({len(queue)})", "All documents"]
tabs = st.tabs(names)
i = 0

if doc:
    compliance = doc["result"].get("compliance") or {}
    with tabs[0]:
        flags = compliance.get("flags") or []
        if flags:
            st.markdown(" ".join(pill(flag_label(f), "warn") for f in flags), unsafe_allow_html=True)
        else:
            st.markdown('<p class="muted">No issues found.</p>', unsafe_allow_html=True)
        names_found = sorted({e.get("text", "") for e in (compliance.get("pii_entities") or []) if e.get("text")})
        if names_found:
            st.markdown(
                f'<p class="muted">Names or places detected: {esc(", ".join(names_found))}</p>',
                unsafe_allow_html=True,
            )
    with tabs[1]:
        for r in field_rows(doc["result"]):
            detail = r["evidence"] if r["verified"] and r["evidence"] else (r["note"] or "")
            st.markdown(
                f'<div class="ev"><div class="label">{esc(r["label"])}</div><code>{esc(detail)}</code></div>',
                unsafe_allow_html=True,
            )
    i = 2

with tabs[i]:
    if queue:
        st.dataframe(table_of(queue), hide_index=True)
    else:
        st.markdown('<p class="muted">Nothing is waiting for review.</p>', unsafe_allow_html=True)

with tabs[i + 1]:
    if documents:
        st.dataframe(table_of(documents[:20]), hide_index=True)
    else:
        st.markdown('<p class="muted">No documents yet, or the API is not reachable.</p>', unsafe_allow_html=True)
