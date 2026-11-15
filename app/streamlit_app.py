"""Streamlit demo UI. Run: streamlit run app/streamlit_app.py"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st  # noqa: E402

from hr_assistant.leave import db  # noqa: E402
from hr_assistant.pipeline import Assistant  # noqa: E402
from hr_assistant.policies import item_index  # noqa: E402
from hr_assistant.retriever import Retriever  # noqa: E402

st.set_page_config(page_title="Nordlight HR Assistant", page_icon="💼", layout="wide")


@st.cache_resource
def get_conn():
    conn = db.connect(check_same_thread=False)
    db.init_db(conn, seed=False)
    if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        db.init_db(conn, seed=True)
    return conn


@st.cache_resource
def get_retriever(mode: str):
    return Retriever(mode=mode)


conn = get_conn()
employees = [dict(r) for r in conn.execute("SELECT id, name, role, contract_type FROM employees ORDER BY id")]

with st.sidebar:
    st.header("Session")
    emp = st.selectbox("Logged in as", employees, format_func=lambda e: f"{e['id']}. {e['name']} ({e['role']}, {e['contract_type']})")
    today = st.date_input("Today", value=date.today())
    mode = st.selectbox("Retrieval mode", ["hybrid", "bm25", "dense"])
    use_suff = st.toggle("Sufficiency check", value=True)
    use_ver = st.toggle("Source verifier", value=True)
    if st.button("Reset database"):
        db.init_db(conn, seed=True)
        st.session_state.clear()
        st.rerun()

key = (emp["id"], today.isoformat(), mode, use_suff, use_ver)
if st.session_state.get("key") != key:
    st.session_state.key = key
    st.session_state.assistant = Assistant(conn, emp["id"], today, get_retriever(mode),
                                           use_sufficiency=use_suff, use_verifier=use_ver)
    st.session_state.history = []
assistant: Assistant = st.session_state.assistant

st.title("Nordlight HR Assistant")
col_chat, col_data = st.columns([3, 2])

with col_data:
    st.subheader("My leave data (from DB)")
    st.json(assistant.tools.get_leave_balance())
    reqs = assistant.tools.list_my_requests()
    if reqs:
        cols = ("id", "leave_type", "start_date", "end_date", "working_days", "status", "decision_reason")
        st.dataframe([{k: r[k] for k in cols} for r in reqs], hide_index=True)
    else:
        st.caption("No requests yet.")

with col_chat:
    for turn in st.session_state.history:
        with st.chat_message(turn["role"]):
            st.write(turn["text"])
            if turn.get("citations"):
                idx = item_index(assistant.retriever.chunks)
                with st.expander("Sources"):
                    for c in turn["citations"]:
                        st.markdown(f"**{c}** — {idx.get(c, '?')}")
            if turn.get("trace"):
                with st.expander(f"Trace ({turn['kind']})"):
                    st.code(json.dumps(turn["trace"], ensure_ascii=False, indent=2, default=str), language="json")

    if prompt := st.chat_input("Ask about HR policies or request leave..."):
        st.session_state.history.append({"role": "user", "text": prompt})
        with st.spinner("Thinking..."):
            resp = assistant.handle(prompt)
        st.session_state.history.append({"role": "assistant", "text": resp.text, "citations": resp.citations,
                                         "trace": resp.trace, "kind": resp.kind})
        st.rerun()
