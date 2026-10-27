import html
import os
import time

import streamlit as st

from api_client import Api, ApiError, Unauthorized
from ui_helpers import field_rows, flag_label, format_time, render_pages, risk_pill, status_pill

API_BASE = os.environ.get("DOCUAUDIT_API", "http://localhost:8000")
FINISHED = ("complete", "needs_review", "failed")

st.set_page_config(page_title="DocuAudit", layout="wide")

st.markdown("""
<style>
header[data-testid="stHeader"], footer, #MainMenu {display: none;}
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1120px;}
html, body, [class*="css"] {font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;}
h1, h2, h3 {letter-spacing: -0.01em;}
.brand {font-size: 1.15rem; font-weight: 650; letter-spacing: -0.01em; display: flex; align-items: center; gap: 10px;}
.logo {width: 22px; height: 22px; border-radius: 6px; background: #2f5bea; display: inline-block;}
.who {color: #6b7280; font-size: 0.86rem; text-align: right; padding-top: 6px;}
.auth-title {font-size: 1.5rem; font-weight: 650; letter-spacing: -0.02em; margin: 8px 0 2px 0;}
.muted {color: #6b7280; font-size: 0.88rem;}
.section {font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
          color: #6b7280; margin: 26px 0 10px 0;}
.meta {display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 4px 0 14px 0;}
.pill {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.76rem;
       font-weight: 500; border: 1px solid; white-space: nowrap;}
.pill.ok {color: #146c43; background: #e9f6ef; border-color: #bfe3cf;}
.pill.warn {color: #8a5a00; background: #fff5de; border-color: #f0dba8;}
.pill.bad {color: #a12622; background: #fdeceb; border-color: #f3c4c1;}
.pill.muted {color: #4b5563; background: #f3f4f6; border-color: #e0e3e8;}
.kpis {display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 4px 0 18px 0;}
.kpi {border: 1px solid #e6e8ee; border-radius: 12px; padding: 14px 16px; background: #fff;}
.kpi-label {color: #6b7280; font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.05em;}
.kpi-value {font-size: 1.35rem; font-weight: 600; margin-top: 4px; letter-spacing: -0.01em;}
.kpi-value.ok {color: #146c43;} .kpi-value.warn {color: #8a5a00;} .kpi-value.bad {color: #a12622;}
.callout {border-left: 3px solid #e0a82e; background: #fffaf0; padding: 10px 14px;
          margin: 0 0 16px 0; font-size: 0.92rem; color: #3b3320; border-radius: 0 8px 8px 0;}
.row {display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
      padding: 11px 0; border-bottom: 1px solid #eceef2;}
.label {color: #6b7280; font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.04em;}
.value {font-size: 1.02rem; font-weight: 500; margin-top: 1px;}
.value.off {color: #9aa1ad; font-weight: 400;}
.guess {color: #8b93a1; font-size: 0.8rem; margin-top: 2px;}
.legend {color: #6b7280; font-size: 0.8rem; margin-top: 6px;}
.dot {display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin: 0 4px 0 10px;}
.dot.g {background: #21a35c; margin-left: 0;} .dot.a {background: #d98a1a;}
.ev {margin: 0 0 14px 0;}
.ev code {display: block; background: #f6f7f9; border: 1px solid #eceef2; border-radius: 6px;
          padding: 6px 10px; font-size: 0.84rem; margin-top: 3px; color: #1c1f26;}
.hist-name {font-weight: 500; padding-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.hist-time {color: #6b7280; font-size: 0.84rem; padding-top: 8px;}
.hist-pill {padding-top: 7px;}
</style>
""", unsafe_allow_html=True)


def esc(text):
    return html.escape(str(text))


def pill(text, kind):
    return f'<span class="pill {kind}">{esc(text)}</span>'


def api():
    return Api(API_BASE, st.session_state.get("token"))


def sign_out(notice=None):
    for key in ("token", "user", "doc"):
        st.session_state.pop(key, None)
    if notice:
        st.session_state["notice"] = notice
    st.rerun()


def start_session(data):
    st.session_state["token"] = data["access_token"]
    st.session_state["user"] = data["user"]
    st.rerun()


# ---------------------------------------------------------------- sign in and sign up
def auth_page():
    _, centre, _ = st.columns([1, 1.25, 1])
    with centre:
        st.markdown('<div class="brand"><span class="logo"></span>DocuAudit</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-title">Welcome</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="muted">Sign in to extract invoices and see how every value was checked.</p>',
            unsafe_allow_html=True,
        )
        notice = st.session_state.pop("notice", None)
        if notice:
            st.info(notice)

        with st.container(border=True):
            sign_in, create = st.tabs(["Sign in", "Create account"])

            with sign_in:
                with st.form("login_form"):
                    email = st.text_input("Email", key="login_email")
                    password = st.text_input("Password", type="password", key="login_password")
                    submitted = st.form_submit_button("Sign in", type="primary")
                if submitted:
                    if not email or not password:
                        st.error("Enter your email and password.")
                    else:
                        try:
                            start_session(Api(API_BASE).login(email, password))
                        except ApiError as error:
                            st.error(error.message)

            with create:
                with st.form("signup_form"):
                    name = st.text_input("Name (optional)", key="signup_name")
                    new_email = st.text_input("Email", key="signup_email")
                    new_password = st.text_input("Password", type="password", key="signup_password",
                                                 help="At least 8 characters.")
                    confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
                    submitted = st.form_submit_button("Create account", type="primary")
                if submitted:
                    if not new_email or not new_password:
                        st.error("Enter an email and a password.")
                    elif new_password != confirm:
                        st.error("The two passwords do not match.")
                    else:
                        try:
                            start_session(Api(API_BASE).signup(new_email, new_password, name))
                        except ApiError as error:
                            st.error(error.message)


# ---------------------------------------------------------------- the signed-in app
def top_bar():
    brand, who, button = st.columns([4, 5, 1.4])
    brand.markdown('<div class="brand"><span class="logo"></span>DocuAudit</div>', unsafe_allow_html=True)
    user = st.session_state.get("user") or {}
    who.markdown(f'<div class="who">{esc(user.get("name") or user.get("email", ""))}</div>', unsafe_allow_html=True)
    if button.button("Sign out"):
        sign_out()
    st.markdown('<hr style="margin: 10px 0 8px 0; border: none; border-top: 1px solid #eceef2;">',
                unsafe_allow_html=True)


def process(uploaded):
    try:
        doc_id = api().upload(uploaded.name, uploaded.getvalue())["doc_id"]
    except Unauthorized:
        sign_out("Your session has expired. Please sign in again.")
        return
    except ApiError as error:
        st.error(error.message)
        return

    result = None
    with st.spinner("Reading and checking the invoice. The first one after a restart takes longer."):
        for _ in range(90):
            try:
                r = api().document(doc_id)
            except Unauthorized:
                sign_out("Your session has expired. Please sign in again.")
                return
            except ApiError:
                r = None
            if r and r.get("status") in FINISHED:
                result = r
                break
            time.sleep(2)

    if result is None:
        st.info("Still processing. It will appear in your documents when it finishes.")
        return
    st.session_state["doc"] = {"result": result, "pdf": uploaded.getvalue(), "name": uploaded.name}


def open_document(entry):
    try:
        result = api().document(entry["doc_id"])
        try:
            pdf = api().file(entry["doc_id"])
        except ApiError:
            pdf = None
    except Unauthorized:
        sign_out("Your session has expired. Please sign in again.")
        return
    except ApiError as error:
        st.error(error.message)
        return
    st.session_state["doc"] = {"result": result, "pdf": pdf, "name": entry.get("filename", "")}
    st.rerun()


def kpi_cards(status, rows, compliance):
    verified = sum(1 for r in rows if r["verified"])
    status_text, status_kind = status_pill(status)
    risk_text, risk_kind = risk_pill(compliance.get("risk_level", "low"))
    flags = len(compliance.get("flags") or [])
    cards = [
        ("Status", status_text, status_kind),
        ("Fields verified", f"{verified} / {len(rows)}", "ok" if verified == len(rows) else "warn"),
        ("Risk", risk_text.replace(" risk", ""), risk_kind),
        ("Flags", str(flags), "ok" if flags == 0 else "warn"),
    ]
    body = "".join(
        f'<div class="kpi"><div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value {kind if kind in ("ok", "warn", "bad") else ""}">{esc(value)}</div></div>'
        for label, value, kind in cards
    )
    st.markdown(f'<div class="kpis">{body}</div>', unsafe_allow_html=True)


def render_result(doc):
    result = doc["result"]
    status = result.get("status")
    st.markdown(f'<div class="section">Result</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="meta"><span class="value">{esc(doc["name"])}</span></div>', unsafe_allow_html=True)

    if status in ("pending", "processing"):
        st.info("This invoice is still being processed. Open it again in a moment.")
        return
    if status == "failed":
        st.error("Processing failed. Check the worker logs.")
        return

    rows = field_rows(result)
    compliance = result.get("compliance") or {}
    kpi_cards(status, rows, compliance)

    unverified = [r["label"] for r in rows if not r["verified"]]
    if status == "needs_review" and unverified:
        st.markdown(
            f'<div class="callout">A person should check this invoice. Could not verify: '
            f'{esc(", ".join(unverified).lower())}.</div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns([1, 1], gap="large")
    with left:
        if doc.get("pdf"):
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
        else:
            st.markdown('<p class="muted">Preview not available.</p>', unsafe_allow_html=True)

    with right:
        for r in rows:
            if r["verified"]:
                body = f'<div class="value">{esc(r["value"])}</div>'
                badge = pill("Verified", "ok")
            else:
                guess = (f'<div class="guess">Guess: {esc(r["value"])}. {esc(r["note"])}</div>' if r["value"]
                         else f'<div class="guess">{esc(r["note"])}</div>')
                body = f'<div class="value off">Not verified</div>{guess}'
                badge = pill("Review", "warn")
            st.markdown(
                f'<div class="row"><div><div class="label">{esc(r["label"])}</div>{body}</div>{badge}</div>',
                unsafe_allow_html=True,
            )


def history_list(documents, prefix):
    for d in documents[:20]:
        name, state, when, action = st.columns([4, 2, 2.2, 1.2])
        name.markdown(f'<div class="hist-name">{esc(d.get("filename", ""))}</div>', unsafe_allow_html=True)
        state.markdown(f'<div class="hist-pill">{pill(*status_pill(d.get("status")))}</div>', unsafe_allow_html=True)
        when.markdown(f'<div class="hist-time">{esc(format_time(d.get("uploaded_at")))}</div>', unsafe_allow_html=True)
        if action.button("Open", key=f"{prefix}_{d['doc_id']}"):
            open_document(d)


def main_page():
    top_bar()

    st.markdown('<div class="section">New invoice</div>', unsafe_allow_html=True)
    with st.container(border=True):
        uploaded = st.file_uploader("Invoice PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded is not None and st.button("Process invoice", type="primary"):
            process(uploaded)

    doc = st.session_state.get("doc")
    if doc:
        render_result(doc)

    try:
        documents = api().documents()
    except Unauthorized:
        sign_out("Your session has expired. Please sign in again.")
        return
    except ApiError as error:
        documents = []
        st.error(error.message)

    queue = [d for d in documents if d.get("status") == "needs_review"]
    st.markdown('<div class="section">Details</div>', unsafe_allow_html=True)
    names = (["Compliance", "Evidence"] if doc and doc["result"].get("status") in ("complete", "needs_review") else []) \
        + [f"Review queue ({len(queue)})", "All documents"]
    tabs = st.tabs(names)
    i = 0

    if len(names) == 4:
        compliance = doc["result"].get("compliance") or {}
        with tabs[0]:
            flags = compliance.get("flags") or []
            if flags:
                st.markdown(" ".join(pill(flag_label(f), "warn") for f in flags), unsafe_allow_html=True)
            else:
                st.markdown('<p class="muted">No issues found.</p>', unsafe_allow_html=True)
            found = sorted({e.get("text", "") for e in (compliance.get("pii_entities") or []) if e.get("text")})
            if found:
                st.markdown(f'<p class="muted">Names or places detected: {esc(", ".join(found))}</p>',
                            unsafe_allow_html=True)
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
            history_list(queue, "queue")
        else:
            st.markdown('<p class="muted">Nothing is waiting for review.</p>', unsafe_allow_html=True)

    with tabs[i + 1]:
        if documents:
            history_list(documents, "all")
        else:
            st.markdown('<p class="muted">No invoices yet. Upload one above.</p>', unsafe_allow_html=True)


if st.session_state.get("token"):
    main_page()
else:
    auth_page()
